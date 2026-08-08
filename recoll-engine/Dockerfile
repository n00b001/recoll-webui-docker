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
        tesseract-ocr=4.1.1-2.1build1 \
        tesseract-ocr-eng=1:4.00~git30-7274cfa-1.1 \
        libimage-exiftool-perl=12.40+dfsg-1 \
        ffmpeg=7:4.4.2-0ubuntu0.22.04.1 \
        catdoc=1:0.95-5 \
        antiword=0.37-16 \
        unrtf=0.21.10-clean-1 \
        unzip=6.0-26ubuntu3.2 \
        p7zip-full=16.02+dfsg-8 \
        file=1:5.41-3ubuntu0.1 \
        mime-support=3.66 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/libreoffice \
    && chmod 1777 /tmp/libreoffice \
    && mkdir -p /root/.recoll

COPY recoll.conf /root/.recoll/recoll.conf

WORKDIR /data

CMD ["recollindex"]
