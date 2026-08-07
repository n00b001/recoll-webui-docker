# =============================================================================
# Audio/Video Transcription Worker — whisper.cpp
# =============================================================================
# Debian slim base with ffmpeg, curl, and the whisper.cpp CLI binary.
# Model is downloaded at container startup based on WHISPER_MODEL env var.
# =============================================================================

FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl=7.88.1-10+deb12u14 \
    ffmpeg=7:6.0.1-0+deb12u1 \
    python3-minimal=3.11.2-1+b1 \
    tini=0.19.0-1+b3 \
    && rm -rf /var/lib/apt/lists/*

# Download whisper.cpp prebuilt CLI binary
# Using the official GitHub release
RUN WHISPER_VERSION="1.7.2" && \
    curl -fsSL "https://github.com/ggerganov/whisper.cpp/releases/download/v${WHISPER_VERSION}/binaries/linux-cli.zip" \
    -o /tmp/whisper.zip && \
    mkdir -p /usr/local/bin && \
    # Extract the whisper binary (zip contains a 'whisper' executable)
    cd /tmp && unzip -o whisper.zip && \
    chmod +x /tmp/whisper && \
    mv /tmp/whisper /usr/local/bin/whisper && \
    rm -f /tmp/whisper.zip

# Create models directory (model downloaded at runtime)
RUN mkdir -p /models

WORKDIR /app

COPY transcribe.py .

ENTRYPOINT ["tini", "--"]
CMD ["python3", "transcribe.py"]
