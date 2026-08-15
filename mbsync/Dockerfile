# =============================================================================
# mbsync — IMAP → Maildir Sync (isync)
# =============================================================================
# Base image provides isync (1.4.1) + s6-overlay on Alpine 3.14.
# We add gettext for envsubst template rendering, using matching v3.14 repos.
# =============================================================================

FROM ghcr.io/jakewharton/mbsync:1.4.1

# Base image runs as non-root; switch to root for apk add, then drop back
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

# Drop back to non-root user from base image (UID 1000)
USER 1000

ENTRYPOINT ["/entrypoint.sh"]
