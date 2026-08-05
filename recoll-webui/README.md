# Recoll WebUI

Web interface for searching the Recoll index.

Based on [recoll-webui](https://github.com/mfonda/recoll-webui) — a Python/Bottle-based search frontend.

## What it does

- Full-text search across indexed documents, images, and audio
- Faceted filtering (date, type, path)
- Thumbnail preview for images
- Snippet highlighting

## Building

```bash
docker build -t ghcr.io/n00b001/recoll-webui:latest .
```

## Usage

Exposes port 8080. Mount the same index directory as recoll-engine:

```yaml
volumes:
  - /mnt/shuttle/share/app-data/recoll:/root
```

## Access

Once running, visit http://localhost:9080 (or whatever port you publish to).
