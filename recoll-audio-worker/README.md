# Recoll Audio Worker

Transcribes audio and video files to plain-text transcripts for indexing by Recoll.

## What it does

- Polls input directories for new/changed audio and video files
- Transcribes to text using [whisper.cpp](https://github.com/ggerganov/whisper.cpp)
- Outputs `.txt` sidecar transcripts alongside source directory structure
- Recoll indexes the transcript text, making audio searchable

## Input Formats

**Audio:** MP3, WAV, M4A/AAC, OGG, Opus, FLAC
**Video:** WebM, MP4, MOV, MKV (audio track extracted)

## Pipeline

```
audio/video file → ffmpeg (normalize to WAV mono 16kHz) → whisper.cpp → .txt transcript → recoll index
```

## Configuration

| Environment Variable | Default    | Description                              |
|---------------------|------------|------------------------------------------|
| `INPUT_DIR`         | `/input`   | Root directory containing audio files    |
| `OUTPUT_DIR`        | `/output`  | Directory where transcripts are written  |
| `POLL_INTERVAL`     | `300`      | Seconds between directory scans          |
| `WHISPER_MODEL`     | `base`     | Model size: tiny, base, small, medium, large |
| `WHISPER_LANGUAGE`  | `auto`     | Language code (e.g., `en`, `fr`) or `auto` |

## Model Sizes

| Size   | Params | RAM    | Disk   | Use case              |
|--------|--------|--------|--------|-----------------------|
| tiny   | 39M    | ~1GB   | 76MB   | Fast, lower accuracy  |
| base   | 74M    | ~1GB   | 142MB  | Good balance (default)|
| small  | 244M   | ~2GB   | 466MB  | Better accuracy       |
| medium | 769M   | ~5GB   | 1.5GB  | High accuracy         |
| large  | 1550M  | ~8GB   | 2.9GB  | Best quality          |

Models are downloaded at container startup from HuggingFace.

## Building

```bash
docker build -t ghcr.io/n00b001/recoll-audio-worker:latest .
```

## Running

```bash
docker run -d \
  -v /path/to/audio:/input \
  -v /path/to/transcripts:/output \
  -e WHISPER_MODEL=base \
  -e WHISPER_LANGUAGE=auto \
  -e POLL_INTERVAL=300 \
  ghcr.io/n00b001/recoll-audio-worker:latest
```

## State

Processed files are tracked in `/output/.transcribed.json` (MD5 hash map).
Restarts resume from this state — no reprocessing of unchanged files.
