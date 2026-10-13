"""Low-rate Linux process and host pressure measurements, without extra packages."""
import csv
import os
from pathlib import Path
import time


def snapshot(pid):
    root = Path(f"/proc/{pid}")
    # comm may contain spaces; fields after the final ')' start at state (field 3).
    stat = (root / "stat").read_text().rsplit(")", 1)[1].split()
    values = {"cpu_s": (int(stat[11]) + int(stat[12])) / os.sysconf("SC_CLK_TCK"),
              "minor_faults": int(stat[7]), "major_faults": int(stat[9])}
    status = {}
    for line in (root / "status").read_text().splitlines():
        key, _, value = line.partition(":")
        status[key] = value.strip().split()[0] if value.strip() else "0"
    for key, target in (("VmRSS", "rss_kib"), ("VmHWM", "hwm_kib"), ("Threads", "threads"),
                        ("voluntary_ctxt_switches", "main_voluntary_switches"),
                        ("nonvoluntary_ctxt_switches", "main_involuntary_switches")):
        values[target] = int(status.get(key, 0))
    for filename, wanted in (("io", {"read_bytes", "write_bytes", "rchar", "wchar"}),
                             ("smaps_rollup", {"Pss", "Private_Dirty"})):
        try:
            for line in (root / filename).read_text().splitlines():
                key, _, value = line.partition(":")
                if key in wanted:
                    values[key.lower()] = int(value.strip().split()[0])
        except (PermissionError, FileNotFoundError):
            pass
    return values


def host_snapshot():
    result = {}
    try:
        for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
            interface, data = line.split(":")
            fields = data.split()
            if interface.strip() == "lo":
                result["loopback_rx_bytes"] = int(fields[0])
                result["loopback_tx_bytes"] = int(fields[8])
        for resource in ("cpu", "memory", "io"):
            for line in Path(f"/proc/pressure/{resource}").read_text().splitlines():
                fields = line.split()
                result[f"{resource}_{fields[0]}_stall_us"] = int(fields[-1].split("=")[1])
    except (PermissionError, FileNotFoundError):
        pass
    result["load1"] = os.getloadavg()[0]
    return result


def percentile(values, quantile):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * quantile
    lower = int(position)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)


class ProcessMetrics:
    def __init__(self, pid, output):
        self.pid = pid
        self.start = time.monotonic()
        self.first = snapshot(pid)
        self.host_first = host_snapshot()
        self.samples = []
        self.stream = output.open("w")
        self.writer = None
        self.sample()

    def sample(self):
        values = snapshot(self.pid)
        values["wall_s"] = time.monotonic() - self.start
        values.update(host_snapshot())
        if self.writer is None:
            self.writer = csv.DictWriter(self.stream, fieldnames=list(values))
            self.writer.writeheader()
        self.writer.writerow(values)
        self.stream.flush()
        self.samples.append(values)

    def summary(self):
        last = self.samples[-1]
        wall = last["wall_s"]
        result = {"measurement_wall_s": wall, "logical_cpus": len(os.sched_getaffinity(0)),
                  "cpu_time_s": last["cpu_s"] - self.first["cpu_s"],
                  "peak_sampled_rss_kib": max(s["rss_kib"] for s in self.samples),
                  "kernel_peak_rss_kib": last["hwm_kib"],
                  "peak_threads": max(s["threads"] for s in self.samples)}
        result["mean_cpu_percent_one_core"] = result["cpu_time_s"] / wall * 100 if wall else None
        intervals = [(b["cpu_s"] - a["cpu_s"]) / (b["wall_s"] - a["wall_s"]) * 100
                     for a, b in zip(self.samples, self.samples[1:]) if b["wall_s"] > a["wall_s"]]
        result["sampled_cpu_percent_one_core"] = {name: percentile(intervals, q)
            for name, q in (("p50", 0.5), ("p95", 0.95), ("p99", 0.99))}
        for key in ("minor_faults", "major_faults", "read_bytes", "write_bytes", "rchar", "wchar",
                    "main_voluntary_switches", "main_involuntary_switches"):
            if key in last and key in self.first:
                result[key] = last[key] - self.first[key]
        for key in ("pss", "private_dirty"):
            if key in last:
                result[f"peak_sampled_{key}_kib"] = max(s[key] for s in self.samples)
        result["host_observations"] = {key: last[key] - value for key, value in self.host_first.items()
                                       if key in last and key != "load1"}
        result["scope"] = "Node process incl. threads; subscription-ready-to-drain. Context switches: main thread only. Host counters include unrelated activity. I/O counters are not memory bandwidth."
        return result

    def close(self):
        self.stream.close()
