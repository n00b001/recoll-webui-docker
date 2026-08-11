FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common \
    && add-apt-repository universe \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        recoll \
        python3-recoll \
        rsync \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /recoll-webui

# Create template and generated directories
RUN mkdir -p /templates /generated

# Copy webui application
COPY recoll-webui /recoll-webui

# No build-time templates for recoll-webui - it reads recoll.conf from shared mount
# But we create the sync structure for consistency with the specification

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "webui-standalone.py", "-a", "0.0.0.0", "-p", "8080"]