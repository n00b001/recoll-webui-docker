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
        rsync=3.2.3-8ubuntu3 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/libreoffice \
    && chmod 1777 /tmp/libreoffice \
    && mkdir -p /root/.recoll

# Create template and generated directories
RUN mkdir -p /templates /generated

# Copy template to image
COPY recoll.conf.template /templates/recoll.conf.template

# Build-time render with defaults (runtime variables will be substituted at container startup)
# Use envsubst with only build-time known variables, leave runtime vars as-is
RUN mkdir -p /generated && \
    envsubst '${ALEX_HADDES_PATH} ${ALEX_PHONE_PATH} ${ALEX_GDRIVE_PATH} ${ALEX_GPHOTOS_PATH} \
    ${CHLOE_HOME_SYNC_PATH} ${CHLOE_PHONE_PATH} ${CHLOE_GDRIVE_PATH} ${CHLOE_GPHOTOS_PATH} \
    ${MBSYNC_DATA_PATH} ${WHATSAPP_DATA_PATH} ${SMS_DATA_PATH}' \
    < /templates/recoll.conf.template > /generated/recoll.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /data

ENTRYPOINT ["/entrypoint.sh"]
CMD ["recollindex"]