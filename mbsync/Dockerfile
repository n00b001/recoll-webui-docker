FROM ghcr.io/jakewharton/mbsync:latest

USER root

# Install python3 for entrypoint template rendering
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 && \
    rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

COPY mbsyncrc.template /etc/mbsyncrc.template

ENTRYPOINT ["/entrypoint.sh"]
