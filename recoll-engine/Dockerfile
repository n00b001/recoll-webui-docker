FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    recoll \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
    exiftool \
    ffmpeg \
    catdoc \
    antiword \
    unrtf \
    unzip \
    p7zip-full \
    file \
    mime-support \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/libreoffice \
    && chmod 777 /tmp/libreoffice

WORKDIR /data

CMD ["recollindex"]
