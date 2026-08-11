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

# Runtime synchronization: mirror /generated to /runtime (bind mount)
# /runtime is the host bind-mount point; this ensures the host directory
# becomes an exact copy of the image's generated assets on every startup.
mkdir -p /runtime
rsync -a --delete /generated/ /runtime/

# Re-render recoll.conf with runtime environment variables to /runtime
# This ensures the latest environment variables are used
mkdir -p /runtime/.recoll
envsubst '\${ALEX_HADDES_PATH} \${ALEX_PHONE_PATH} \${ALEX_GDRIVE_PATH} \${ALEX_GPHOTOS_PATH} \
\${CHLOE_HOME_SYNC_PATH} \${CHLOE_PHONE_PATH} \${CHLOE_GDRIVE_PATH} \${CHLOE_GPHOTOS_PATH} \
\${MBSYNC_DATA_PATH} \${WHATSAPP_DATA_PATH} \${SMS_DATA_PATH}' \
< /templates/recoll.conf.template > /runtime/.recoll/recoll.conf

# Point recoll to the synchronized config directory
export RECOLL_CONFDIR="/runtime/.recoll"

# Execute the original command
exec "$@"