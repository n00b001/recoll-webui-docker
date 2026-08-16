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

## Logging & Typing Rules (recoll_wrapper, applies to all new Python code)
- **Log with rich only — never `print`.** Every log record goes through
  `logging` + `rich.logging.RichHandler`; built-in `print` is banned (ruff T20).
- **Always use a proper log level.** DEBUG for audit-trail rows, INFO for
  progress/operational, WARNING for recoverable issues, ERROR for failures.
- **Colours & formatting:** terminal RichHandler uses markup + rich tracebacks;
  dynamic (tool/user-derived) strings are escaped with `rich.markup.escape`
  before logging so literal `[...]` is not parsed as markup.
- **Tables & progress bars** come from rich: diagnostics render as
  `Table`/`Panel`; long-running work shows a `Progress` bar with elapsed time,
  iteration rate (it/s) and estimated time until completion (ETA; real ETA when
  the total is known).
- **Log to BOTH console and file** — two-line pattern from
  https://github.com/Textualize/rich/discussions/1309:
  `console = Console(file=open("log.txt"))` + `RichHandler(console=console)`.
  The terminal handler stays on stderr with colours; the file mirror runs at
  DEBUG so the log is a complete audit trail. Interactive prompts (y/N) go to
  the terminal console, never into the log file.
- **No `typing.Any`** — banned by ruff TID banned-api + ANN401.
- **No ambiguous union types** — an annotation may not combine two or more
  concrete types (`int | str`, `str | int | bytes`, also inside subscripts).
  Optional style (one concrete type + `None`) is allowed. Model real ambiguity
  explicitly (subclasses, Protocol, Literal). Enforced by
  `recoll_wrapper/tests/test_type_policy.py`.
- Strict tooling for recoll_wrapper: ruff select covers A/ANN/B/BLE/C4/D/E/F/
  FLY/G/I/LOG/PERF/PIE/PL/PTH/RET/RUF/S/SIM/T20/TID/UP/W (S607 ignored only —
  host tools are PATH-resolved by design); ty runs with `all = "error"`.