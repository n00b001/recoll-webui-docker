FROM ghcr.io/jakewharton/mbsync:latest

USER root

# Install python3 for entrypoint template rendering
RUN apk add --no-cache python3

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY mbsyncrc.template /etc/mbsyncrc.template

ENTRYPOINT ["/entrypoint.sh"]
