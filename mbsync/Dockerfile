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
    apk add --no-cache --force-broken-world gettext rsync

# Create template and generated directories
RUN mkdir -p /templates /generated

# Copy template to image
COPY mbsyncrc.template /templates/mbsyncrc.template

# Build-time render with defaults (runtime variables will be substituted at container startup)
RUN mkdir -p /generated && \
    envsubst < /templates/mbsyncrc.template > /generated/mbsync.rc

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]