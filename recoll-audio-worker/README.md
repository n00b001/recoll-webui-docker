# Recoll Audio Worker

Generates text transcripts from audio files for indexing by Recoll.

## What it does

- Transcribes audio to text using [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- Outputs plain-text transcripts alongside source files
- Recoll indexes the transcript text, making audio searchable

## Input Formats

- MP3
- WAV
- M4A / AAC
- OGG
- FLAC
- Video files (audio track extracted)

## Pipeline

```
audio file → ffmpeg (normalize) → faster-whisper (transcribe) → .txt transcript → recoll index
```

## Building

```bash
docker build -t ghcr.io/n00b001/recoll-audio-worker:latest .
```

## Status

**Phase 2 — In progress.** The container and model are ready. Integration with the main Recoll indexing pipeline is pending.

## Future Work

- [ ] Automatic transcript generation during indexing
- [ ] Multiple language support
- [ ] Speaker diarization
- [ ] Configurable whisper model size (tiny/base/small/medium/large)
