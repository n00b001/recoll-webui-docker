FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common && \
    add-apt-repository -y universe && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        recoll \
        libreoffice \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        poppler-utils \
        python3-mutagen \
        python3-lxml \
        tesseract-ocr \
        tesseract-ocr-eng \
        libimage-exiftool-perl \
        ffmpeg \
        catdoc \
        antiword \
        unrtf \
        unzip \
        xdg-utils \
        p7zip-full \
        file \
        mime-support \
        gettext-base \
        zstd \
        aspell \
        aspell-en \
        libpst-tools \
        ghostscript \
        texlive-extra-utils \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/libreoffice \
    && chmod 1777 /tmp/libreoffice \
    && mkdir -p /root/.recoll

# Copy template to /etc to avoid being hidden by the /root bind-mount
# declared in docker-compose.yml.
COPY recoll.conf.template /etc/recoll.conf.template

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /data

ENTRYPOINT ["/entrypoint.sh"]
