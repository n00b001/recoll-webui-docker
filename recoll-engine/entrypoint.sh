#!/bin/bash
set -euo pipefail

# Source environment if available (docker-compose injects vars here)
if [ -f /etc/environment ]; then
    set -a
    source /etc/environment
    set +a
fi

# Map host paths (from .env) to container paths for recoll.conf
# This ensures get_dirs() in recoll-webui can glob actual container paths
export ALEX_HADDES_PATH="${ALEX_HADDES_PATH:-/mnt/shuttle/share/syncthing/alex-hades-home}"
export ALEX_PHONE_PATH="${ALEX_PHONE_PATH:-/mnt/shuttle/share/syncthing/alex-phone}"
export ALEX_GDRIVE_PATH="${ALEX_GDRIVE_PATH:-/mnt/shuttle/share/alex-home/google-drive}"
export ALEX_GPHOTOS_PATH="${ALEX_GPHOTOS_PATH:-/mnt/shuttle/share/alex-home/google-photos}"
export CHLOE_HOME_SYNC_PATH="${CHLOE_HOME_SYNC_PATH:-/mnt/shuttle/share/syncthing/chloe-home}"
export CHLOE_PHONE_PATH="${CHLOE_PHONE_PATH:-/mnt/shuttle/share/syncthing/chloe-phone}"
export CHLOE_GDRIVE_PATH="${CHLOE_GDRIVE_PATH:-/mnt/shuttle/share/chloe-home/google-drive}"
export CHLOE_GPHOTOS_PATH="${CHLOE_GPHOTOS_PATH:-/mnt/shuttle/share/chloe-home/google-photos}"
export MBSYNC_DATA_PATH="${MBSYNC_DATA_PATH:-/mnt/shuttle/share/app-data/mbsync/data}"
export WHATSAPP_DATA_PATH="${WHATSAPP_DATA_PATH:-/mnt/shuttle/share/app-data/whatsapp/data}"
export SMS_DATA_PATH="${SMS_DATA_PATH:-/mnt/shuttle/share/app-data/sms-organized}"

# Now translate to container paths for recoll.conf
# The template uses env vars, but we need the container mount points
export ALEX_HADDES_PATH="/homes/alex/hades"
export ALEX_PHONE_PATH="/homes/alex/phone"
export ALEX_GDRIVE_PATH="/homes/alex/gdrive"
export ALEX_GPHOTOS_PATH="/homes/alex/gphotos"
export CHLOE_HOME_SYNC_PATH="/homes/chloe/home"
export CHLOE_PHONE_PATH="/homes/chloe/phone"
export CHLOE_GDRIVE_PATH="/homes/chloe/gdrive"
export CHLOE_GPHOTOS_PATH="/homes/chloe/gphotos"
export MBSYNC_DATA_PATH="/homes/mail"
export WHATSAPP_DATA_PATH="/homes/whatsapp"
export SMS_DATA_PATH="/homes/sms"

# Render recoll.conf from template with container paths
envsubst '${ALEX_HADDES_PATH} ${ALEX_PHONE_PATH} ${ALEX_GDRIVE_PATH} ${ALEX_GPHOTOS_PATH} \
${CHLOE_HOME_SYNC_PATH} ${CHLOE_PHONE_PATH} ${CHLOE_GDRIVE_PATH} ${CHLOE_GPHOTOS_PATH} \
${MBSYNC_DATA_PATH} ${WHATSAPP_DATA_PATH} ${SMS_DATA_PATH}' \
  < /etc/recoll.conf.template > /root/.recoll/recoll.conf

# Execute the original command
exec "$@"
