# =============================================================================
# mbsync — IMAP → Maildir Sync (isync)
# =============================================================================
# Base image provides isync (1.4.1) + s6-overlay on Alpine 3.14.
# We add gettext for envsubst template rendering, using matching v3.14 repos.
# =============================================================================

FROM ghcr.io/jakewharton/mbsync:1.4.1

# Runs as root: s6-overlay requires a root init — it chowns/chmods its
# /var/run/s6 staging area at container start and fails (EPERM) under any
# other USER. The only workload is cron + mbsync, so no privilege drop.
# hadolint ignore=DL3002
USER 0

# Install gettext for envsubst template rendering (isync + curl already present)
# Use Alpine 3.14 repos matching the base image, with --force-broken-world
# to satisfy edge-tagged world dependencies (curl@edge, isync@edge).
RUN echo 'https://dl-cdn.alpinelinux.org/alpine/v3.14/main' > /etc/apk/repositories && \
    echo 'https://dl-cdn.alpinelinux.org/alpine/v3.14/community' >> /etc/apk/repositories && \
    apk update && \
    apk add --no-cache --force-broken-world gettext=0.21-r0

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY mbsyncrc.template /etc/mbsyncrc.template

# No USER drop here: /init (s6-overlay) must stay root. Synced mail files
# are world-readable; Recoll indexes them via a read-only bind mount of /mail.
ENTRYPOINT ["/entrypoint.sh"]
