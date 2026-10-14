#!/usr/bin/env bash
set -euo pipefail
export LD_LIBRARY_PATH="$VINS_REMOTE_PAYLOAD/lib"
logs="$VINS_REMOTE_ROOT/logs"
ldd "$VINS_REMOTE_PAYLOAD/shared_probe" > "$logs/ldd.txt"
! grep -q 'not found' "$logs/ldd.txt"
"$VINS_REMOTE_PAYLOAD/shared_probe" memfd > "$logs/memfd.log" 2>&1
grep -q 'PASS memfd:' "$logs/memfd.log"
# Do not silently switch heaps/backends or change global device permissions.
device=${VINS_DMA_HEAP_DEVICE:-/dev/dma_heap/system}
stat "$device" > "$logs/heap_device.txt"
"$VINS_REMOTE_PAYLOAD/shared_probe" dma_heap "$device" > "$logs/dma_heap.log" 2>&1
grep -q 'PASS dma_heap:' "$logs/dma_heap.log"
