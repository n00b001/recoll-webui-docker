# Project: recoll-webui-docker

## Deployment Rule: Remote-only stack
**This docker-compose stack runs on truenas.arpa (remote TrueNAS), NOT locally.**
- Only test containers run locally (use local Docker for testing/verification)
- Do NOT try to run docker commands against the remote host — no remote Docker access
- Paths in docker-compose.yml and .env are TrueNAS paths (/mnt/shuttle/share/...)
- Do NOT inspect local Docker for production state — it only shows test containers
- **All logs, errors, and container state you share are from PRODUCTION on TrueNAS — local Docker does NOT have them**

## TrueNAS Path Structure
- Base: `/mnt/shuttle/share/`
- App data: `/mnt/shuttle/share/app-data/`
- Syncthing: `/mnt/shuttle/share/syncthing/`
- User homes: `/mnt/shuttle/share/alex-home/`, `/mnt/shuttle/share/chloe-home/`

## Immich Existing Data (standalone stack)
The standalone Immich on TrueNAS uses these separate paths:
- PostgreSQL: `/mnt/shuttle/share/app-data/immich/pg_data`
- Server uploads: `/mnt/shuttle/share/app-data/immich/data`
- ML cache: `/mnt/shuttle/share/app-data/immich/cache`
- Redis: named volume `redis-data` (managed by Docker)

The current docker-compose.yml needs to be updated to mount these correctly.