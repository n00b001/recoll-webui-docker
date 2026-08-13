FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common=0.99.22.9 && \
    add-apt-repository -y universe && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        recoll=1.31.6-1ubuntu1 \
        libreoffice=1:7.3.7-0ubuntu0.22.04.12 \
        libreoffice-writer=1:7.3.7-0ubuntu0.22.04.12 \
        libreoffice-calc=1:7.3.7-0ubuntu0.22.04.12 \
        libreoffice-impress=1:7.3.7-0ubuntu0.22.04.12 \
        poppler-utils=22.02.0-2ubuntu0.13 \
        python3-mutagen=1.45.1-2 \
        python3-lxml=4.8.0-1build1 \
        tesseract-ocr=4.1.1-2.1build1 \
        tesseract-ocr-eng=1:4.00~git30-7274cfa-1.1 \
        libimage-exiftool-perl=12.40+dfsg-1 \
        ffmpeg=7:4.4.2-0ubuntu0.22.04.1 \
        catdoc=1:0.95-5 \
        antiword=0.37-16 \
        unrtf=0.21.10-clean-1 \
        unzip=6.0-26ubuntu3.2 \
        xdg-utils=1.1.3-4.1ubuntu3~22.04.1 \
        p7zip-full=16.02+dfsg-8 \
        file=1:5.41-3ubuntu0.1 \
        mime-support=3.66 \
        gettext-base=0.21-4ubuntu4 \
        zstd=1.4.8+dfsg-3build1 \
        aspell=0.60.8-4build1 \
        aspell-en=2018.04.16-0-1 \
        pff-tools=20180714-3build1 \
        ghostscript=9.55.0~dfsg1-0ubuntu5.13 \
        texlive-extra-utils=2021.20220204-1 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/libreoffice \
    && chmod 1777 /tmp/libreoffice \
    && mkdir -p /root/.recoll

# Copy template to /etc to avoid being hidden by the /root bind-mount
# declared in docker-compose.yml.
COPY recoll-engine/recoll.conf.template /etc/recoll.conf.template

# Copy recoll_wrapper to /opt/recoll_wrapper for startup copy to config dir
COPY recoll_wrapper /opt/recoll_wrapper

COPY recoll-engine/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /data

ENTRYPOINT ["/entrypoint.sh"]