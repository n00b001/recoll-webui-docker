FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3=3.10.6-1~22.04.1 \
    python3-pip=22.0.2+dfsg-1ubuntu0.7 \
    ffmpeg=7:4.4.2-0ubuntu0.22.04.2 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
    faster-whisper==1.2.1

WORKDIR /data

CMD ["python3", "-c", "print('audio worker ready')"]
