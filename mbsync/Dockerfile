# =============================================================================
# mbsync — IMAP → Maildir Sync (isync)
# =============================================================================
# Base image provides isync (1.4.4-r5) + s6-overlay on Alpine 3.14.
# We add gettext for envsubst template rendering, using matching v3.14 repos.
# =============================================================================

FROM ghcr.io/jakewharton/mbsync:latest

USER root

# Install gettext for envsubst template rendering (isync + curl already present)
# Use Alpine 3.14 repos matching the base image, with --force-broken-world
# to satisfy edge-tagged world dependencies (curl@edge, isync@edge).
RUN echo 'https://dl-cdn.alpinelinux.org/alpine/v3.14/main' > /etc/apk/repositories && \
    echo 'https://dl-cdn.alpinelinux.org/alpine/v3.14/community' >> /etc/apk/repositories && \
    apk update && \
    apk add --no-cache --force-broken-world gettext

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY mbsyncrc.template /etc/mbsyncrc.template

ENTRYPOINT ["/entrypoint.sh"]
