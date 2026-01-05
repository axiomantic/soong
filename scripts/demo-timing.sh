#!/bin/bash
# Helper script for demo timing - called from VHS tape
# Usage: demo-timing.sh <marker>
#   markers: start, wait_start, wait_end, end

TIMING_FILE="/tmp/demo-timing.txt"
MARKER="$1"

case "$MARKER" in
    start)
        echo "start=$(date +%s.%N)" > "$TIMING_FILE"
        ;;
    wait_start|wait_end|end)
        echo "${MARKER}=$(date +%s.%N)" >> "$TIMING_FILE"
        ;;
    show)
        cat "$TIMING_FILE"
        ;;
    *)
        echo "Usage: $0 {start|wait_start|wait_end|end|show}"
        exit 1
        ;;
esac
