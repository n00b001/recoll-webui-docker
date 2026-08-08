FROM ghcr.io/jakewharton/mbsync:latest

USER root

# Fix broken @edge repos and install python3 for entrypoint template rendering
RUN printf "https://dl-cdn.alpinelinux.org/alpine/v3.21/main\nhttps://dl-cdn.alpinelinux.org/alpine/v3.21/community\n" > /etc/apk/repositories && \
    apk update && \
    apk add --no-cache curl isync python3

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY mbsyncrc.template /etc/mbsyncrc.template

ENTRYPOINT ["/entrypoint.sh"]
