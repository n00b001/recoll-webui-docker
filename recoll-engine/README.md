# Recoll Engine

Containerized document, image, and audio search indexer based on [Recoll](https://www.recoll.org/).

## What it does

- **Full-text indexing** of documents (PDF, DOCX, ODT, XLSX, PPTX, TXT, RTF, EPUB)
- **OCR** for scanned PDFs via Tesseract
- **EXIF/IPTC/XMP extraction** for images (JPEG, PNG, TIFF, GIF)
- **Audio metadata** via ffmpeg (MP3, M4A, OGG, FLAC)
- **Compressed file support** (ZIP, 7z, RAR auto-extraction)

## Building

```bash
docker build -t ghcr.io/n00b001/recoll-engine:latest .
```

## Usage

The container runs `recollindex` by default. Data directories are mounted read-only under `/homes/`, the index lives at `/root/.recoll/xapiandb`.

### Configuration

Mount a custom `recoll.conf`:

```yaml
volumes:
  - ./recoll.conf:/root/.recoll/recoll.conf:ro
  - /path/to/data:/homes:ro
  - ./index-data:/root/.recoll
```

### Manual indexing

```bash
docker exec recoll-engine recollindex -f
```

### Incremental reindex

```bash
docker exec recoll-engine recollindex
```

## Dependencies (inside container)

| Tool | Purpose |
|------|---------|
| recoll | Core indexer |
| poppler-utils | PDF text extraction (pdftotext) |
| tesseract-ocr | OCR for scanned documents |
| exiftool | Image metadata extraction |
| ffmpeg | Audio/video metadata |
| libreoffice | Office document conversion |
| catdoc, antiword, unrtf | Legacy document formats |
| file, mime-support | MIME type detection |

## Index Location

The Xapian database is stored at `/root/.recoll/xapiandb` inside the container. Mount this path persistently to avoid rebuilding the index on restart.
