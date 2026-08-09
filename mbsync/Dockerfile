# =============================================================================
# mbsync — IMAP → Maildir Sync (isync)
# =============================================================================
# Base image already provides isync (1.4.4-r5) + s6-overlay.
# We only add gettext for envsubst template rendering.
# =============================================================================

FROM ghcr.io/jakewharton/mbsync:latest

USER root

# Install gettext for envsubst template rendering (isync + curl already present)
RUN apk add --no-cache gettext

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY mbsyncrc.template /etc/mbsyncrc.template

ENTRYPOINT ["/entrypoint.sh"]
