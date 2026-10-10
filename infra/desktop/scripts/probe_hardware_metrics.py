"""Read hardware-counter availability without modifying kernel or system settings.

This is a capability probe, not a VINS energy/DDR benchmark. Missing counters
remain null: logical copies, cache misses and virtual batteries are not DDR/power.
"""
import argparse
import ctypes
import errno
import json
import os
from pathlib import Path
import platform
import struct
import time


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError as error:
        return {"error": str(error), "errno": error.errno}


def open_perf_event(event_type, config, pid=0, inherit=False):
    syscall = {"x86_64": 298, "aarch64": 241}.get(platform.machine())
    if syscall is None:
        raise OSError(errno.ENOSYS, "Unsupported syscall architecture")
    # perf_event_attr v0: count this process's userspace only; exclude kernel/HV.
    attr = ctypes.create_string_buffer(64)
    struct.pack_into("=IIQ", attr, 0, event_type, 64, config)
    struct.pack_into("=Q", attr, 32, 3)  # total time enabled / running
    struct.pack_into("=Q", attr, 40, (int(inherit) << 1) | (1 << 5) | (1 << 6))
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    fd = libc.syscall(ctypes.c_long(syscall), ctypes.byref(attr),
                      ctypes.c_int(pid), ctypes.c_int(-1), ctypes.c_int(-1), ctypes.c_ulong(0))
    if fd < 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number))
    return fd


def perf_probe(event_type, config):
    try:
        fd = open_perf_event(event_type, config)
    except OSError as error:
        return {"available": False, "errno": error.errno,
                "errno_name": errno.errorcode.get(error.errno), "reason": str(error)}
    try:
        checksum = sum(i * i for i in range(100000))
        value, enabled, running = struct.unpack("=QQQ", os.read(fd, 24))
        return {"available": running > 0 and value > 0, "probe_count": value,
                "time_enabled_ns": enabled, "time_running_ns": running,
                "scope": "Counter access test only, not a VINS measurement", "checksum": checksum}
    except OSError as error:
        return {"available": False, "errno": error.errno, "reason": str(error)}
    finally:
        os.close(fd)


def collect():
    pmu_root = Path("/sys/bus/event_source/devices")
    devices = sorted(pmu_root.iterdir()) if pmu_root.exists() else []
    pmus = {p.name: {"type": read(p / "type"),
                     "events": {e.name: read(e) for e in sorted((p / "events").glob("*"))}}
            for p in devices}
    memory_candidates = [name for name in pmus
                         if any(token in name.lower() for token in ("imc", "ddr", "dmc", "dfi"))]
    energy = {}
    # Class entries can be symlinks; inspect resolved trees and deduplicate paths.
    for root in (Path("/sys/class/powercap"), Path("/sys/devices/virtual/powercap")):
        if not root.exists():
            continue
        for zone in [root] + [p.resolve() for p in root.iterdir() if p.is_dir()]:
            for path in zone.rglob("energy_uj"):
                path = path.resolve()
                energy[str(path)] = {"name": read(path.parent / "name"),
                                     "energy_uj": read(path),
                                     "max_energy_range_uj": read(path.parent / "max_energy_range_uj")}
    hwmon = {}
    for device in sorted(Path("/sys/class/hwmon").glob("*")):
        hwmon[device.name] = {"name": read(device / "name"),
                             "power_inputs": {p.name: read(p) for p in device.glob("power*_input")}}
    batteries = {p.name: read(p / "uevent") for p in sorted(Path("/sys/class/power_supply").glob("*"))}
    return {"timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kernel": platform.release(), "architecture": platform.machine(),
            "wsl": "microsoft" in platform.release().lower(),
            "scope": "Read-only capability probe; no EuRoC playback or host-wide energy attribution",
            "perf_event_paranoid": read("/proc/sys/kernel/perf_event_paranoid"),
            "perf_counter_access": {"task_clock": perf_probe(1, 1),
                                    "cpu_cycles": perf_probe(0, 0),
                                    "cache_misses": perf_probe(0, 3)},
            "pmus": pmus, "memory_controller_candidates": memory_candidates,
            "rapl_energy_zones": energy, "hwmon": hwmon, "power_supplies": batteries,
            "measurement": {"ddr_read_bytes": None, "ddr_write_bytes": None,
                            "energy_j": None, "average_power_w": None},
            "limitations": ["PMU names alone do not establish usable counters or byte/event scaling.",
                            "RAPL/package or rail counters are host/device-wide, not process-only.",
                            "Virtual battery readings are not physical power measurements.",
                            "Logical copy bytes and cache misses must not substitute for DDR traffic."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = collect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "wsl": report["wsl"],
                      "memory_controller_candidates": report["memory_controller_candidates"],
                      "energy_zones": len(report["rapl_energy_zones"]),
                      "perf_access": report["perf_counter_access"],
                      "measurement": report["measurement"]}, indent=2))


if __name__ == "__main__":
    main()
