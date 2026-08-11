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