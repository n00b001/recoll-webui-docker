#!/bin/sh
set -eu

# Source environment if available (docker-compose injects vars here)
if [ -f /etc/environment ]; then
    set -a
    . /etc/environment
    set +a
fi

# Defaults for all IMAP configuration variables
export IMAP_HOST_ALEX_GMAIL="${IMAP_HOST_ALEX_GMAIL:-imap.gmail.com}"
export IMAP_PORT_ALEX_GMAIL="${IMAP_PORT_ALEX_GMAIL:-993}"
export IMAP_USER_ALEX_GMAIL="${IMAP_USER_ALEX_GMAIL:-alex@gmail.com}"

export IMAP_HOST_ALEX_IMAP="${IMAP_HOST_ALEX_IMAP:-mail.example.com}"
export IMAP_PORT_ALEX_IMAP="${IMAP_PORT_ALEX_IMAP:-993}"
export IMAP_USER_ALEX_IMAP="${IMAP_USER_ALEX_IMAP:-alex@example.com}"

export IMAP_HOST_CHLOE_OUTLOOK="${IMAP_HOST_CHLOE_OUTLOOK:-outlook.office365.com}"
export IMAP_PORT_CHLOE_OUTLOOK="${IMAP_PORT_CHLOE_OUTLOOK:-993}"
export IMAP_USER_CHLOE_OUTLOOK="${IMAP_USER_CHLOE_OUTLOOK:-chloe@outlook.com}"

export IMAP_HOST_CHLOE_IMAP="${IMAP_HOST_CHLOE_IMAP:-mail.example.com}"
export IMAP_PORT_CHLOE_IMAP="${IMAP_PORT_CHLOE_IMAP:-993}"
export IMAP_USER_CHLOE_IMAP="${IMAP_USER_CHLOE_IMAP:-chloe@example.com}"

# Render mbsync.rc from template using envsubst
mkdir -p /config
envsubst < /etc/mbsyncrc.template > /config/mbsync.rc

# Seed base Maildir dirs — isync will not create them on a fresh data volume
# ("Maildir error: cannot open store", and `Create Near` only creates
# subfolders). Derive paths from the rendered rc to stay in sync with template.
awk '$1 == "Path" { print $2 }' /config/mbsync.rc | xargs mkdir -p

# Hand off to the original s6-overlay entrypoint
exec /init "$@"
