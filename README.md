# Unified Search Infrastructure

One-stop search for your entire digital life — documents, photos, emails, audio, messages.

## Vision

A single beautiful UI that instantly searches across all your data sources:

| Source | Content | Status |
|--------|---------|--------|
| **Recoll** | Documents (PDF, DOCX, ODT), images (EXIF), scanned docs (OCR) | Phase 1: Docs + Images ✅ |
| **Recoll Audio** | Audio transcription (Whisper) | Phase 2: In progress |
| **Immich** | Photos/videos with ML search (CLIP, face recognition) | Integrated |
| **MailArchiver** | Email search | Integrated |
| **WhatsApp** | Message history | Future |
| **SMS** | Text messages | Future |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Future Unified UI                        │
│  (single search box → queries all backends simultaneously)  │
└───────────────┬───────────────┬───────────────┬─────────────┘
                │               │               │
        ┌───────▼──────┐  ┌────▼──────┐  ┌────▼───────┐
        │    Recoll     │  │  Immich   │  │   Mail     │
        │  (port 9080)  │  │(port 2283)│  │ Archiver   │
        │               │  │           │  │(port 30315)│
        │  Documents    │  │  Photos   │  │  Emails    │
        │  Images + OCR │  │  Videos   │  │            │
        │  Audio (TBD)  │  │  ML Tags  │  │            │
        └───────┬───────┘  └────┬──────┘  └────┬────────┘
                │               │               │
        ┌───────▼───────────────▼───────────────▼──────────┐
        │              TrueNAS Filesystem                   │
        │  /mnt/shuttle/share/{syncthing,alex-home,chloe-   │
        │    home,app-data}                                 │
        └──────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Copy environment file and set secure passwords
cp .env.example .env
# Edit .env with secure passwords

# 2. Pull images
docker compose pull

# 3. Start everything
docker compose up -d

# 4. Check status
docker compose ps
```

## Services

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| recoll-webui | 9080 | http://localhost:9080 | Document/image search |
| immich-server | 2283 | http://localhost:2283 | Photo/video library |
| mail-archiver | 30315 | http://localhost:30315 | Email archive |

## Data Layout

### Host → Container mounts (Recoll)

| Host Path | Container Path | Content |
|-----------|----------------|---------|
| syncthing/alex-hades-home | /homes/alex/hades | Alex's home files |
| syncthing/alex-phone | /homes/alex/phone | Alex's phone backup |
| alex-home/google-drive | /homes/alex/gdrive | Alex's Google Drive |
| alex-home/google-photos | /homes/alex/gphotos | Alex's Google Photos |
| syncthing/chloe-home | /homes/chloe/home | Chloe's home files |
| syncthing/chloe-phone | /homes/chloe/phone | Chloe's phone backup |
| chloe-home/google-drive | /homes/chloe/gdrive | Chloe's Google Drive |
| chloe-home/google-photos | /homes/chloe/gphotos | Chloe's Google Photos |

### Index storage

- Recoll index: `/mnt/shuttle/share/app-data/recoll`
- Immich data: `/mnt/shuttle/share/app-data/immich`
- MailArchiver data: `/mnt/shuttle/share/app-data/mail-archiver`

## Configuration

Recoll is configured via [`recoll.conf`](recoll.conf). It covers:
- **Documents**: PDF (with OCR fallback), DOCX, ODT, XLSX, PPTX, TXT, RTF, EPUB
- **Images**: JPEG, PNG, TIFF, GIF — EXIF/IPTC/XMP metadata via exiftool
- **Audio**: MP3, M4A, OGG, FLAC — metadata via ffmpeg (transcription coming in Phase 2)
- **OCR**: Tesseract English for scanned PDFs

## Roadmap

### Phase 1 ✅ — Documents + Images
- [x] Recoll indexing for documents
- [x] EXIF extraction for images
- [x] OCR for scanned PDFs
- [x] Google Photos mounted

### Phase 2 — Audio
- [ ] Whisper transcription pipeline
- [ ] Audio worker integration
- [ ] Transcribed text indexed by Recoll

### Phase 3 — Unified UI
- [ ] Single search box querying all backends
- [ ] WhatsApp message import
- [ ] SMS import
- [ ] Semantic search across all sources

## Directory Structure

```
.
├── docker-compose.yml      # Unified compose (Recoll + Immich + MailArchiver)
├── recoll.conf             # Recoll indexing configuration
├── .env.example            # Environment variable template
├── recoll-engine/          # Recoll indexer container image
├── recoll-webui/           # Recoll web interface source
├── recoll-audio-worker/    # Audio transcription worker
└── recoll_wrapper/         # Python wrapper for Recoll indexing
```

## TrueNAS Notes

This compose file is cleaned up from TrueNAS app exports. Standard Docker users can run it directly. TrueNAS-specific init containers (permissions, postgres_upgrade) are removed — set ownership on the host instead.
