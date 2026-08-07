# Audio Worker Implementation Plan — whisper.cpp

> Status: **Approved** | Date: 2026-08-07

## Goal

Transcribe audio/video files to plain-text `.txt` sidecar transcripts so Recoll can full-text-search audio content. Replace the current `faster-whisper` skeleton with a **whisper.cpp** pipeline.

## Why whisper.cpp

- **No Python/PyTorch** — smaller image (~100-200MB vs ~2GB)
- **CPU-first** — runs without GPU, optional Vulkan backend
- **Quantized models** — `ggml-base.bin` is ~142MB
- **Single binary CLI** — simpler Docker image

## Architecture

```
Audio/video files appear in mounted /input/ subdirs (read-only)
    ↓
recoll-audio-worker polls /input/ every N seconds
    ↓
New/changed audio file detected (MD5 hash check against state file)
    ↓
whisper.cpp CLI transcribes → /output/<mirror-path>/<filename>.txt
    ↓
Transcripts volume mounted into recoll-engine as /homes/transcripts/
    ↓
Recoll indexes .txt sidecars on next index cycle
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Model download | Runtime (container startup) | User selects model via env var, no rebuild needed |
| Model source | HuggingFace (`ggerganov/whisper.cpp/models/`) | Official ggml binaries |
| Output location | `app-data/recoll-audio/` | Separate writable volume, mounted ro into recoll-engine |
| Video files | Include (mp4, mov, mkv) | Extract audio track for transcription |
| GPU | CPU-only (Phase 1) | Simpler, sufficient with base model |

## Files to Create/Modify

### New Files

1. **`recoll-audio-worker/transcribe.py`** — Main entry point
2. **`recoll-audio-worker/.dockerignore`** — Standard exclusions
3. **`recoll-audio-worker/pyproject.toml`** — uv + ruff + pytest config
4. **`recoll-audio-worker/tests/test_transcribe.py`** — Unit tests

### Modified Files

5. **`recoll-audio-worker/Dockerfile`** — Rewrite: debian-slim + whisper.cpp binary
6. **`docker-compose.yml`** — Add `recoll-audio-worker` service + new volume + recoll-engine mount
7. **`recoll.conf`** — Add `/homes/transcripts` to `topdirs`
8. **`.github/workflows/ci.yml`** — hadolint + lint/test steps for audio-worker
9. **`recoll-audio-worker/README.md`** — Update docs

## transcribe.py Design

### Startup
1. Read env vars (`WHISPER_MODEL`, `WHISPER_LANGUAGE`, etc.)
2. Download model from `https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{model}.bin` to `/models/` via curl
3. Verify model file exists and is non-empty
4. Create output dir, load state file

### Poll Loop
1. Scan all `/input/` subdirs recursively for audio/video files
2. Extensions: `mp3`, `wav`, `m4a`, `aac`, `ogg`, `opus`, `flac`, `webm`, `mp4`, `mov`, `mkv`
3. MD5 hash check against `/output/.transcribed.json` — skip unchanged
4. For each new/changed file:
   - If not WAV mono 16kHz: `ffmpeg -i <input> -ac 1 -ar 16000 /tmp/transcode.wav`
   - `/usr/local/bin/whisper -m /models/ggml-{model}.bin -f /tmp/transcode.wav -otxt -l {language}`
   - Copy `.txt` to `/output/<mirror-path>/`
   - Update state file

### Environment Variables

| Var | Default | Purpose |
|-----|---------|---------|
| `INPUT_DIR` | `/input` | Audio source root |
| `OUTPUT_DIR` | `/output` | Transcript output root |
| `POLL_INTERVAL` | `300` | Seconds between scans |
| `WHISPER_MODEL` | `base` | Model size (`tiny`, `base`, `small`, `medium`, `large`) |
| `WHISPER_LANGUAGE` | `auto` | Language code or `auto` detect |

## Dockerfile Design

```
Base: debian:bookworm-slim
Install: ffmpeg, curl, python3-minimal, tini
Download: whisper.cpp CLI binary at build time → /usr/local/bin/whisper
/app/models/: empty — model downloaded at runtime by transcribe.py
COPY: transcribe.py → /app/
ENTRYPOINT: ["tini", "--"]
CMD: ["python3", "/app/transcribe.py"]
```

## docker-compose.yml Changes

### New Volume
```yaml
recoll-audio-data:
  # → /mnt/shuttle/share/app-data/recoll-audio
```

### New Service
```yaml
recoll-audio-worker:
  container_name: recoll-audio-worker
  build: ./recoll-audio-worker
  restart: unless-stopped
  networks: [search-infrastructure]
  deploy.resources.limits: { cpus: '4', memory: 4G }
  environment:
    POLL_INTERVAL: ${AUDIO_POLL_INTERVAL:-300}
    WHISPER_MODEL: ${WHISPER_MODEL:-base}
    WHISPER_LANGUAGE: ${WHISPER_LANGUAGE:-auto}
  volumes:
    # Read audio from all sources (read-only)
    - *alex-phone → /input/alex-phone (ro)
    - *chloe-phone → /input/chloe-phone (ro)
    - *alex-hades → /input/alex-hades (ro)
    - *chloe-home-sync → /input/chloe-home (ro)
    - *alex-gdrive → /input/alex-gdrive (ro)
    - *chloe-gdrive → /input/chloe-gdrive (ro)
    - *whatsapp-data → /input/whatsapp (ro)
    # Output
    - recoll-audio-data → /output
```

### recoll-engine Addition
```yaml
# Add to existing volumes:
- recoll-audio-data → /homes/transcripts (ro)
```

## recoll.conf Change

Add `/homes/transcripts` to `topdirs`.

## CI Changes

- Add hadolint step for `recoll-audio-worker/Dockerfile`
- Add ruff lint + pytest step (same pattern as sms-processor)

## Tests

- `file_hash()` state tracking
- Audio/video file discovery (correct extensions filtered)
- State load/save/corruption recovery
- Model download URL construction
- CLI argument parsing

## Implementation Order

1. `transcribe.py` + `tests/test_transcribe.py`
2. `Dockerfile` + `.dockerignore` + `pyproject.toml`
3. `docker-compose.yml` + `recoll.conf` updates
4. `.github/workflows/ci.yml` updates
5. `README.md` update
