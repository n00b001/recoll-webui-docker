# WhatsApp Archiver

Baileys-based WhatsApp message and media archiver for Recoll indexing.

Connects as a WhatsApp Web multi-device client, then continuously exports
incoming messages to plain-text files and downloads all attachments to
dated folders.

## How It Works

1. **First run**: scan the QR code printed to the terminal
2. Session persists to `/data/sessions/{account}/` — no re-scan on restart
3. Messages are appended to `/data/chats/{account}/{contact}.txt`
4. Media is downloaded to `/data/media/{account}/{type}/YYYY-MM/`
5. Recoll indexes the `.txt` files for full-text search

## Output Layout

```
/data/
├── sessions/default/       # Baileys auth state (persistent)
├── chats/default/
│   ├── +1234567890.txt     # one file per conversation
│   └── Group-Name.txt
└── media/default/
    ├── images/2026-08/
    │   └── 2026-08-05T14-32-01_img.jpg
    ├── audio/2026-08/
    │   └── 2026-08-05T14-35-22_audio.ogg
    ├── video/2026-08/
    └── documents/2026-08/
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `/data` | Root data directory |
| `ACCOUNT_NAME` | `default` | Label for this session (for multi-account) |
| `LOG_LEVEL` | `info` | Baileys log level |

## Docker

```bash
docker run -d \
  --name whatsapp-archiver \
  -v /path/to/whatsapp:/data \
  ghcr.io/n00b001/whatsapp-archiver:latest
```

## Multi-Account

Run multiple containers with different `ACCOUNT_NAME` and data volumes:

```yaml
whatsapp-alex:
  image: ghcr.io/n00b001/whatsapp-archiver:latest
  environment:
    ACCOUNT_NAME: alex
  volumes:
    - /path/to/whatsapp-alex:/data

whatsapp-chloe:
  image: ghcr.io/n00b001/whatsapp-archiver:latest
  environment:
    ACCOUNT_NAME: chloe
  volumes:
    - /path/to/whatsapp-chloe:/data
```

## Dependencies

- [@whiskeysockets/baileys](https://github.com/WhiskeySockets/Baileys) — WhatsApp Web multi-device SDK
- [@hapi/boom](https://github.com/hapijs/boom) — Error handling (Baileys dependency)
