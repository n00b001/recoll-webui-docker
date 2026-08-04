FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install \
    faster-whisper

WORKDIR /data

CMD ["python3", "-c", "print('audio worker ready')"]
