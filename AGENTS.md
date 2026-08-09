# AGENTS.md — recoll-webui-docker

## Deployment Rule: Remote-only stack
**This docker-compose stack runs on truenas.arpa (remote TrueNAS), NOT locally.**
- Only test containers run locally (use local Docker for testing/verification)
- Do NOT try to run docker commands against the remote host — no remote Docker access
- Paths in docker-compose.yml and .env are TrueNAS paths (/mnt/shuttle/share/...)
- Do NOT inspect local Docker for production state — it only shows test containers
- **All logs, errors, and container state shared are from PRODUCTION on TrueNAS — local Docker does NOT have them**

## TrueNAS Path Structure
- Base: `/mnt/shuttle/share/`
- App data: `/mnt/shuttle/share/app-data/`
- Syncthing: `/mnt/shuttle/share/syncthing/`
- User homes: `/mnt/shuttle/share/alex-home/`, `/mnt/shuttle/share/chloe-home/`

## Immich Existing Data (standalone stack on TrueNAS)
The standalone Immich on TrueNAS uses these separate paths:
- PostgreSQL: `/mnt/shuttle/share/app-data/immich/pg_data`
- Server uploads: `/mnt/shuttle/share/app-data/immich/data`
- ML cache: `/mnt/shuttle/share/app-data/immich/cache`
- Redis: named volume `redis-data` (managed by Docker)

The docker-compose.yml needs to mount these subdirectories correctly.

## PR Workflow
- Create branch for every change
- Run CI locally before pushing (linting, formatting, testing)
- Create PR and ensure PR CI is green before merging
- Never merge own PR — require review/approval
- Always use merge (not rebase) for PR merges

## Python Projects
- Use uv (not pip/python/python3 directly)
- Commands: `uv run`, `uv add`, `uv sync`, `uv lock`
- Environment: `.venv`

## ORM Rule
- ALWAYS use an ORM, never raw SQL
- Python: SQLModel with SQLAlchemy
- TypeScript: Drizzle, Prisma, Kysely