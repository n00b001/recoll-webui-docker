# =============================================================================
# Audio/Video Transcription Worker — whisper.cpp
# =============================================================================
# Debian slim base with ffmpeg, curl, and whisper.cpp built from source.
# Model is downloaded at container startup based on WHISPER_MODEL env var.
# =============================================================================

FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install runtime + build dependencies
# hadolint ignore=DL3003
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl=7.88.1-10+deb12u15 \
    ffmpeg=7:5.1.9-0+deb12u1 \
    python3=3.11.2-1+b1 \
    python3-stdlib=3.11.2-1+b1 \
    tini=0.19.0-1+b3 \
    && ( apt-get install -y --no-install-recommends \
        build-essential=12.9 \
        ca-certificates=20230311+deb12u1 \
        git=1:2.39.5-0+deb12u3 \
        cmake=3.25.1-1 \
        && cd /tmp \
        && git clone https://github.com/ggml-org/whisper.cpp.git \
        && cd whisper.cpp \
        && git checkout v1.7.2 \
        && mkdir build && cd build \
        && cmake .. -DBUILD_SHARED_LIBS=OFF \
        -DWHISPER_SDL=OFF \
        -DWHISPER_SDL2=OFF \
        -DWHISPER_OPENMP=OFF \
        -DWHISPER_COREML=OFF \
        -DWHISPER_METAL=OFF \
        -DWHISPER_CUBLAS=OFF \
        -DWHISPER_CLBLAST=OFF \
        -DWHISPER_VULKAN=OFF \
        -DWHISPER_VULKAN=OFF \
        && make -j"$(nproc)" \
        && cp bin/main /usr/local/bin/whisper \
        && cd /tmp \
        && rm -rf /tmp/whisper.cpp \
        && apt-get purge -y build-essential git cmake \
        && apt-get autoremove -y \
    ) \
    && rm -rf /var/lib/apt/lists/*

# Create models directory (model downloaded at runtime)
RUN mkdir -p /models

WORKDIR /app

COPY transcribe.py .

ENTRYPOINT ["tini", "--"]
CMD ["python3", "transcribe.py"]
