# Adversarial Repository Review — recoll-webui-docker

## Executive Summary

Well-structured Docker Compose infrastructure for unified search across personal data, with strong CI/CD coverage (linting, testing, hadolint, secret scanning). However, there are **critical runtime bugs and security issues** — most notably a root Dockerfile that won't build on current systems, a logic bug in `recollindex.py` that always reports failure, a missing file copy in the WhatsApp archiver Dockerfile, and credentials exposed via process list.

---

## 🔴 Critical (7 findings)

### 1. Root Dockerfile won't build — Ubuntu 18.04 repos moved to old-releases

- **File:** `Dockerfile:1-13`
- **Evidence:** apt repos for 18.04 were migrated from `archive.ubuntu.com` to `old-releases.ubuntu.com` in April 2023. The Dockerfile will fail on `apt-get update` unless the sources are updated.
- **Fix:** Either update `sources.list` to point to old-releases or migrate to Ubuntu 22.04.

### 2. recollindex.py exit code logic bug — success returns exit code 1

- **File:** `recoll_wrapper/recollindex.py:392`
- **Evidence:** `exit_code = proc.returncode or 1`. When recollindex succeeds (returncode=0), `0 or 1` evaluates to `1`, so every successful run reports failure. The caller treats exit code 1 as a crash and won't delete the lock file, causing stale locks on subsequent runs.
- **Fix:** `exit_code = proc.returncode if proc.returncode == 0 else 1`

### 3. WhatsApp archiver Dockerfile doesn't COPY lib.js — container crashes

- **File:** `whatsapp-archiver/Dockerfile:12`
- **Evidence:** Only `index.js` is copied. Line 38 of `index.js` imports from `'./lib.js'`. Container will crash immediately with `ERR_MODULE_NOT_FOUND`.
- **Fix:** Add `COPY lib.js /app/lib.js` before `COPY index.js`.

### 4. mbsync PassCmd exposes IMAP password in process list

- **File:** `mbsync/mbsyncrc:21`
- **Evidence:** `PassCmd "echo $ALEX_IMAP_PASS"` spawns a shell process visible via `/proc/*/cmdline` to any user on the host with shared PID namespace.
- **Fix:** Use `PassFile "/run/secrets/imap_pass"` or pass credentials via Docker secrets mounted as files.

### 5. .hadolint config file never loaded in CI

- **File:** `.github/workflows/ci.yml:106-147`
- **Evidence:** hadolint steps use `hadolint-action@v3.10` without passing the `.hadolint` ignore file. The root-level `.hadolint` (which ignores DL3066 for `:latest`) is never loaded, so hadolint will fail on rules that should be suppressed locally.
- **Fix:** Add `file: .hadolint` or pass via `hadolint --config .hadolint` flags.

### 6. Containers running as root with no security restrictions

- **Files:** All Dockerfiles except `whatsapp-archiver/Dockerfile`, `docker-compose.yml`
- **Evidence:** No `USER` directives (except whatsapp-archiver), no `cap_drop`, `security_opt`, or `read_only` on any compose service. Recoll-engine mounts `/root` as a volume, giving root write access to host dirs.
- **Fix:** Add `USER` directives, `cap_drop: [ALL]`, and `security_opt: [no-new-privileges:true]`.

### 7. Hardcoded 777 permissions on LibreOffice temp directory

- **File:** `recoll-engine/Dockerfile:29-30`
- **Evidence:** `chmod 777 /tmp/libreoffice`. World-writable executable directory inside a root container.
- **Fix:** Use `chmod 700` with proper ownership, or `1777` (sticky bit) minimum.

---

## 🟠 High (5 findings)

### 8. Immich server healthcheck uses wrong command

- **File:** `docker-compose.yml`
- **Evidence:** `immich-machine-learning-healthcheck` checks the ML backend, not the server. Use HTTP ping instead.
- **Fix:** `test: ['CMD-SHELL', 'curl -f http://localhost:2283/api/server-info/ping || exit 1']`

### 9. Mbsync config mounted to wrong path

- **File:** `docker-compose.yml`
- **Evidence:** `.mfilter.d` is for filter scripts only; main `mbsyncrc` needs `/home/msync/.isync/`.
- **Fix:** Mount to `/home/msync/.isync/` as documented by the stefanbuck/m-sync image.

### 10. Docker images tagged only as `:latest`

- **Files:** `.github/workflows/docker.yml`, `docker-compose.yml`
- **Evidence:** No versioned tags, no rollback capability. Once a bad image is pushed, the previous version is gone.
- **Fix:** Add SHA or semver tags alongside `:latest`.

### 11. Pre-push hooks build all 5 Docker images sequentially

- **File:** `.pre-commit-config.yaml`
- **Evidence:** Blocks every `git push` for 10+ minutes. Encourages developers to bypass with `--no-verify`.
- **Fix:** Move builds to CI-only; keep fast checks (lint, test) locally.

### 12. recoll-audio-worker has no functional CMD

- **File:** `recoll-audio-worker/Dockerfile:16`
- **Evidence:** Placeholder service not referenced in docker-compose. Installs faster-whisper but CMD just prints a message and exits.
- **Fix:** Remove from build matrix or implement the audio worker.

---

## 🟡 Medium (4 findings)

### 13. Exact package version pins will break on archive rotation

- **Files:** `recoll-engine/Dockerfile`, `recoll-audio-worker/Dockerfile`
- **Evidence:** `recoll=1.31.6-1ubuntu1` format fails when Ubuntu archives rotate exact versions out.
- **Fix:** Use minimum version constraints (e.g., `recoll>=1.31.6`) or major.minor pins.

### 14. No `.dockerignore` for recoll-engine / recoll-audio-worker

- **Files:** `recoll-engine/`, `recoll-audio-worker/`
- **Evidence:** Any future large files will be sent to the Docker build context unnecessarily.
- **Fix:** Add `.dockerignore` with standard patterns (`.git`, `node_modules`, `__pycache__`, etc.).

### 15. recoll-webui binds to 0.0.0.0 without authentication

- **Files:** `Dockerfile` (root), `docker-compose.yml`
- **Evidence:** Full search index accessible on network if no reverse proxy auth is in front.
- **Fix:** Set `httpPassword` in recoll.conf or place a reverse proxy with auth in front.

### 16. WhatsApp reconnect hammers every 5 seconds

- **File:** `whatsapp-archiver/index.js:170`
- **Evidence:** `setTimeout(main, 5000)` with no exponential backoff. Risk of WhatsApp rate-limiting or account restriction under network instability.
- **Fix:** Implement exponential backoff (start at 5s, double each retry up to 5 min).

---

## 🟢 Low (3 findings)

### 17. sms-processor uses MD5 for change detection

- **File:** `sms-processor/process.py:74`
- **Evidence:** Fine for this use case (change detection of known files), but SHA-256 is better defense-in-depth.
- **Fix:** Swap to `hashlib.sha256()`. Low priority.

### 18. Hardcoded TrueNAS paths

- **Files:** `docker-compose.yml`, `recoll_wrapper/recollindex.py`
- **Evidence:** `/mnt/shuttle/share/...` is host-specific to a machine named "shuttle". Not portable.
- **Fix:** Document as host-specific or parameterize via environment variables.

### 19. sms-processor append-mode files grow indefinitely

- **File:** `sms-processor/process.py:265`
- **Evidence:** Contact markdowns opened in `"a"` mode with no rotation. Over years, single contact files could grow to hundreds of megabytes.
- **Fix:** Implement file rotation by year/month (e.g., `contact-2026.md`).

---

## Top 5 Immediate Actions

| # | Action | Effort |
|---|--------|--------|
| 1 | Fix `recollindex.py:392` exit code bug (`proc.returncode or 1`) | 1 line |
| 2 | Add `COPY lib.js` to whatsapp-archiver Dockerfile | 1 line |
| 3 | Pass `.hadolint` config to CI hadolint action | 1 field |
| 4 | Fix mbsync PassCmd → PassFile with Docker secrets | Medium |
| 5 | Migrate root Dockerfile off Ubuntu 18.04 / Python 2 | Large |

---

> All findings were verified by the lead synthesizer against actual file contents — no false alarms reported. Six specialized agents (Docker Architect, Python Expert, Node.js Expert, CI/CD Auditor, Security Reviewer, Config Consistency Checker) each read source files directly and cross-referenced their claims before synthesis.
