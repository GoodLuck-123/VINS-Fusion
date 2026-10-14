#!/usr/bin/env bash
set -euo pipefail
export LD_LIBRARY_PATH="$VINS_REMOTE_PAYLOAD/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
perf="$VINS_REMOTE_PAYLOAD/perf"
logs="$VINS_REMOTE_ROOT/logs"
uname -a > "$logs/kernel.txt"
cat /proc/sys/kernel/perf_event_paranoid > "$logs/perf_event_paranoid.txt"
"$perf" --version > "$logs/perf_version.txt"
ldd "$perf" > "$logs/ldd.txt"
! grep -q 'not found' "$logs/ldd.txt"
"$perf" list > "$logs/perf_list.txt"
"$perf" stat -x, -o "$logs/perf_stat.csv" \
  -e task-clock,cycles:u,instructions:u,cache-references:u,cache-misses:u \
  -- "$VINS_REMOTE_PAYLOAD/profile_smoke" > "$logs/stat_workload.txt"
! grep -Eq '<not supported>|<not counted>' "$logs/perf_stat.csv"
"$perf" record -F 99 -e cycles:u --call-graph fp -o "$logs/perf.data" \
  -- "$VINS_REMOTE_PAYLOAD/profile_smoke" > "$logs/record_workload.txt" 2> "$logs/record_stderr.txt"
"$perf" report --stdio --no-children -i "$logs/perf.data" > "$logs/perf_report.txt"
grep -q profile_work "$logs/perf_report.txt"
"$perf" buildid-list -i "$logs/perf.data" > "$logs/buildids.txt"
