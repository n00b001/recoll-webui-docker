#!/bin/bash
# Parallel Docker build check for pre-push hook.
# Builds all images concurrently to avoid sequential wait times.
# recoll-audio-worker is excluded (non-functional CMD, F12).
set -e

ERRORS=0
PIDS=()

for ctx in . ./recoll-engine ./whatsapp-archiver ./sms-processor; do
  docker build --load "$ctx" &
  PIDS+=($!)
done

for pid in "${PIDS[@]}"; do
  wait "$pid" || ERRORS=$((ERRORS + 1))
done

exit $ERRORS
