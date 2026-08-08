#!/bin/bash
set -euo pipefail

# Source environment if available (docker-compose injects vars here)
if [ -f /etc/environment ]; then
    set -a
    source /etc/environment
    set +a
fi

# Set defaults for all path variables
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

# Render recoll.conf from template (only substitute our known vars)
envsubst '${ALEX_HADDES_PATH} ${ALEX_PHONE_PATH} ${ALEX_GDRIVE_PATH} ${ALEX_GPHOTOS_PATH} \
${CHLOE_HOME_SYNC_PATH} ${CHLOE_PHONE_PATH} ${CHLOE_GDRIVE_PATH} ${CHLOE_GPHOTOS_PATH} \
${MBSYNC_DATA_PATH} ${WHATSAPP_DATA_PATH} ${SMS_DATA_PATH}' \
  < /etc/recoll.conf.template > /root/.recoll/recoll.conf

# Execute the original command
exec "$@"
