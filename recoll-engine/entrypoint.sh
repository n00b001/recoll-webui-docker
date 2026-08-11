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

# Required path variables - must be defined in .env (no defaults)
required_vars=(
    ALEX_HADDES_PATH
    ALEX_PHONE_PATH
    ALEX_GDRIVE_PATH
    ALEX_GPHOTOS_PATH
    CHLOE_HOME_SYNC_PATH
    CHLOE_PHONE_PATH
    CHLOE_GDRIVE_PATH
    CHLOE_GPHOTOS_PATH
    MBSYNC_DATA_PATH
    WHATSAPP_DATA_PATH
    SMS_DATA_PATH
)

# Check all required variables are set
for var in "${required_vars[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: Required environment variable $var is not set. Define it in .env" >&2
        exit 1
    fi
done

# Export all required variables
for var in "${required_vars[@]}"; do
    export "$var"
done

# Render recoll.conf from template with container paths
envsubst '${ALEX_HADDES_PATH} ${ALEX_PHONE_PATH} ${ALEX_GDRIVE_PATH} ${ALEX_GPHOTOS_PATH} \
${CHLOE_HOME_SYNC_PATH} ${CHLOE_PHONE_PATH} ${CHLOE_GDRIVE_PATH} ${CHLOE_GPHOTOS_PATH} \
${MBSYNC_DATA_PATH} ${WHATSAPP_DATA_PATH} ${SMS_DATA_PATH}' \
  < /etc/recoll.conf.template > /root/.recoll/recoll.conf

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