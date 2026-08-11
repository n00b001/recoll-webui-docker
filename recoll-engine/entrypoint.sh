#!/bin/bash
set -euo pipefail

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

# Execute the original command
exec "$@"