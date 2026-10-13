"""Optional userspace CPU counters for a command and its subsequently born threads."""
import os
import struct
import subprocess
import sys

from probe_hardware_metrics import open_perf_event


class PerfCounters:
    def __init__(self, command, stdout):
        self.events = {}
        self.errors = {}
        # The Python gate execs the native executable in the same PID. Events are
        # attached before native worker threads exist, so inherit covers them.
        self.process = subprocess.Popen(
            [sys.executable, "-c", "import os,sys; sys.stdin.buffer.read(1); os.execvp(sys.argv[1],sys.argv[1:])", *command],
            stdin=subprocess.PIPE, stdout=stdout, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            for name, config in (("cpu_cycles", 0), ("instructions", 1), ("cache_references", 2), ("cache_misses", 3)):
                try:
                    self.events[name] = open_perf_event(0, config, self.process.pid, inherit=True)
                except OSError as error:
                    self.errors[name] = {"errno": error.errno, "reason": str(error)}
            self.process.stdin.write(b"x")
            self.process.stdin.flush()
            self.process.stdin.close()
        except BaseException:
            self.process.kill()
            self.process.wait()
            self.close()
            raise

    def summary(self):
        if self.process.poll() is None:
            raise RuntimeError("Read inherited totals only after all process threads exit")
        result = {"scope": "Native process and inherited threads, userspace only; includes exec/startup/teardown and a short Python gate",
                  "errors": dict(self.errors), "events": {},
                  "limitations": "CPU PMU diagnostics; cache misses are not DDR bytes; not an energy measurement. No multiplex scaling is applied."}
        for name, fd in self.events.items():
            try:
                count, enabled, running = struct.unpack("=QQQ", os.read(fd, 24))
                result["events"][name] = {"count": count, "time_enabled_ns": enabled,
                                         "time_running_ns": running,
                                         "running_fraction": running / enabled if enabled else None}
            except OSError as error:
                result["errors"][name] = {"errno": error.errno, "reason": str(error)}
        return result

    def close(self):
        for fd in self.events.values():
            os.close(fd)
        self.events.clear()
