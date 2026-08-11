#!/bin/bash
set -euo pipefail

# Validate that all required environment variables are defined in .env
# Run this before docker compose to fail fast with clear errors.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

REQUIRED_VARS=(
    # Base paths
    SHUTTLE_PATH
    APP_DATA_PATH
    SYNCTHING_PATH
    ALEX_HOME_PATH
    CHLOE_HOME_PATH

    # Recoll
    RECOLL_DATA_PATH

    # Immich
    IMMICH_PG_DATA_PATH
    IMMICH_SERVER_DATA_PATH
    IMMICH_ML_CACHE_PATH

    # mbsync
    MBSYNC_CONFIG_PATH
    MBSYNC_DATA_PATH

    # WhatsApp
    WHATSAPP_CONFIG_PATH
    WHATSAPP_DATA_PATH

    # SMS
    SMS_DATA_PATH

    # Syncthing sub-paths
    ALEX_HADDES_PATH
    ALEX_PHONE_PATH
    CHLOE_HOME_SYNC_PATH
    CHLOE_PHONE_PATH

    # Google Drive / Photos
    ALEX_GDRIVE_PATH
    ALEX_GPHOTOS_PATH
    CHLOE_GDRIVE_PATH
    CHLOE_GPHOTOS_PATH
)

ENV_FILE="$PROJECT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in all values." >&2
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

missing=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        missing+=("$var")
    fi
done

if [ ${#missing[@]} -gt 0 ]; then
    echo "ERROR: The following required environment variables are not set in .env:" >&2
    for var in "${missing[@]}"; do
        echo "  - $var" >&2
    done
    echo ""
    echo "Please edit .env and define all required variables." >&2
    exit 1
fi

echo "OK: all required environment variables are set in .env."
