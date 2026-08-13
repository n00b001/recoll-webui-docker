#!/bin/bash
set -euo pipefail

LOG_FILE="/var/log/recoll-engine.log"

# Ensure log file exists and is world-writable so docker exec can write to it
touch "$LOG_FILE"
chmod 666 "$LOG_FILE"

# Source environment if available (docker-compose injects vars here)
if [ -f /etc/environment ]; then
    set -a
    source /etc/environment
    set +a
fi

# Path variables default to fixed container mount targets. docker-compose mounts
# the .env host paths at these /homes/* targets, so recoll.conf topdirs must use
# container paths — the .env values are never injected as container env. If a var
# IS present in the container environment, it wins over the default.
export ALEX_HADDES_PATH="${ALEX_HADDES_PATH:-/homes/alex/hades}"
export ALEX_PHONE_PATH="${ALEX_PHONE_PATH:-/homes/alex/phone}"
export ALEX_GDRIVE_PATH="${ALEX_GDRIVE_PATH:-/homes/alex/gdrive}"
export ALEX_GPHOTOS_PATH="${ALEX_GPHOTOS_PATH:-/homes/alex/gphotos}"
export CHLOE_HOME_SYNC_PATH="${CHLOE_HOME_SYNC_PATH:-/homes/chloe/home}"
export CHLOE_PHONE_PATH="${CHLOE_PHONE_PATH:-/homes/chloe/phone}"
export CHLOE_GDRIVE_PATH="${CHLOE_GDRIVE_PATH:-/homes/chloe/gdrive}"
export CHLOE_GPHOTOS_PATH="${CHLOE_GPHOTOS_PATH:-/homes/chloe/gphotos}"
export MBSYNC_DATA_PATH="${MBSYNC_DATA_PATH:-/homes/mail}"
export WHATSAPP_DATA_PATH="${WHATSAPP_DATA_PATH:-/homes/whatsapp}"
export SMS_DATA_PATH="${SMS_DATA_PATH:-/homes/sms}"

# Render recoll.conf from template with container paths
envsubst '${ALEX_HADDES_PATH} ${ALEX_PHONE_PATH} ${ALEX_GDRIVE_PATH} ${ALEX_GPHOTOS_PATH} \
${CHLOE_HOME_SYNC_PATH} ${CHLOE_PHONE_PATH} ${CHLOE_GDRIVE_PATH} ${CHLOE_GPHOTOS_PATH} \
${MBSYNC_DATA_PATH} ${WHATSAPP_DATA_PATH} ${SMS_DATA_PATH}' \
  < /etc/recoll.conf.template > /root/.recoll/recoll.conf

# Copy recoll_wrapper to recoll config directory on every startup
# This ensures the wrapper scripts are always available for indexing
rsync -a --delete /opt/recoll_wrapper/ /root/.recoll/recoll_wrapper/

# If recollindex is the command, run it with output to both stdout and log file
if [[ "${1:-}" == "recollindex" ]]; then
    shift
    exec recollindex "$@" 2>&1 | tee -a "$LOG_FILE"
fi

# Default: run heartbeat and tail the log so docker logs shows everything
echo "$(date) [recoll-engine] starting heartbeat, log file: $LOG_FILE"
while true; do
    echo "$(date) [recoll-engine] alive, waiting for docker exec recollindex..."
    sleep 300
done &
# Tail the log file so docker logs captures recollindex output from docker exec
exec tail -f "$LOG_FILE"