# Consolidated Solutions Document — Adversarial Review

## 1. Executive Summary

This document consolidates findings from three specialist reviews (Python & Runtime, Docker & Infrastructure, CI/CD & Operations) and their corresponding devil's advocate challenges into a single actionable implementation plan for the `recoll-webui-docker` project.

**Key decisions shaped by adversarial review:**

- **Finding 1 (Ubuntu 18.04 migration) — REJECTED as originally proposed.** All three specialists initially recommended migrating to Ubuntu 22.04 with Python 3. Devil's advocate correctly identified that `python3-recoll` does not exist in Ubuntu 22.04 apt repositories, and the vendored bottle 0.10.11 (from 2011) uses `unicode`, `basestring`, and other Python 2-only constructs that crash immediately on Python 3. The migration is far more complex than "run 2to3."
- **Finding 6 (Non-root containers) — MODIFIED.** Original proposal was too aggressive (`cap_drop: ALL` breaks networking). Revised approach phases work: low-risk services first, then recoll-engine after testing.
- **Finding 13 (Version pins) — REJECTED.** Exact version pins are correct Docker practice for reproducible builds. The archive rotation concern only applies to EOL releases, not Ubuntu 22.04 (supported through 2027+).
- **Finding 17 (MD5 → SHA256) — REJECTED.** MD5 is adequate for change detection of trusted local files. Zero practical security benefit; one-time reprocessing cost with no real-world improvement.
- **Finding 19 (SMS file rotation) — REJECTED.** SMS text volume is negligible (~50KB/year per contact). Files will not reach meaningful sizes for decades. Monthly rotation fragments conversations unnecessarily.

**Overall risk posture:** Personal homelab on TrueNAS. Security hardening should improve posture without breaking functionality. Correctness takes priority over security theater.

---

## 2. Implementation Plan — Phased Approach

### Phase 1: Quick Wins (S effort, zero/low risk, immediate value)

| # | Finding | Effort | Risk |
|---|---------|--------|------|
| 2 | Exit code `or 1` bug | S | None |
| 3 | Missing COPY lib.js | S | None |
| 7 | chmod 777 → sticky bit | S | None |
| 9 | mbsync mount path fix | S | Low |
| 10 | Add SHA image tags | S | None |
| 12 | Remove audio worker from CI | S | None |
| 14 | Add .dockerignore files | S | None |

### Phase 2: Medium Effort (S-M effort, requires testing)

| # | Finding | Effort | Risk |
|---|---------|--------|------|
| 4 | mbsync password exposure | M | Low |
| 5 | hadolint config wiring | S | None |
| 8 | Immich healthcheck fix | S | Low |
| 11 | Pre-push hooks optimization | S | Low |
| 16 | WhatsApp exponential backoff | S | None |
| 18 | Parameterize recollindex.py paths | M | Low |

### Phase 3: Large Refactors (deferred, requires planning)

| # | Finding | Effort | Risk |
|---|---------|--------|------|
| 1 | Ubuntu 18.04 / Python 2 migration | L | High |
| 6 | Non-root container users | L | Medium |
| 15 | WebUI authentication | M | Low |

---

## 3. Final Solutions by Finding

### FINDING 1 — Root Dockerfile: Ubuntu 18.04 repos moved to old-releases

**Final Verdict: REJECT original fix. Deferred to Phase 3 with revised approach.**

**Why rejected:** The proposed Ubuntu 22.04 + Python 3 migration is catastrophically under-specified. Three independent reviewers confirmed: (1) `python3-recoll` does not exist in Ubuntu 22.04 apt repositories, (2) the vendored bottle 0.10.11 uses Python 2-only constructs (`unicode`, `basestring`, `from __future__ import with_statement`) and will crash on first request, (3) recoll-webui's C extension bindings cannot be ported with `2to3`.

**Revised approach for Phase 3:**
- **Option A (stopgap):** Redirect apt sources to `old-releases.ubuntu.com` in the Dockerfile before `apt-get update`. This preserves existing functionality while buying time.
- **Option B (proper migration):** Replace vendored bottle with a modern version (`pip install bottle>=0.12`), audit all Python 2 constructs in webui-standalone.py, and either drop the python-recoll binding (use recoll's CLI/CGI interface) or rebuild the C extension from source against recoll 1.31+.
- **Option C (abandon):** If recoll-webui is abandoned upstream, evaluate whether recoll's built-in CGI interface with nginx provides equivalent functionality without Python bindings.

**Prerequisite:** Audit `recoll-webui/` directory to confirm which endpoints are actually used and whether python-recoll bindings are essential or incidental.

---

### FINDING 2 — recollindex.py exit code bug: success returns 1

**Final Verdict: ACCEPT with simplification.**

**File:** `recoll_wrapper/recollindex.py`, line 392

**Root cause:** `exit_code = proc.returncode or 1`. Because `0` is falsy in Python, successful runs (returncode=0) evaluate to `1`. Every success reports failure.

**Final fix:** Replace with the simplest correct code:

```python
# OLD:
exit_code = proc.returncode or 1
# NEW:
exit_code = proc.returncode
```

**Why this over the original proposal:** The original proposed `proc.returncode if proc.returncode == 0 else 1`, which collapses all non-zero exit codes to `1`, losing diagnostic information (recoll may return 2 for config errors, 3 for lock conflicts, etc.). Since `subprocess.Popen` always sets `returncode` to an int after `poll()`/`wait()`, the `or 1` guard against `None` handles an impossible case.

**Verification:** Add a unit test that mocks `Popen` with `returncode=0` and asserts `exit_code == 0`.

---

### FINDING 3 — WhatsApp archiver: missing COPY lib.js

**Final Verdict: ACCEPT with broadened fix.**

**File:** `whatsapp-archiver/Dockerfile`, after line 11

**Root cause:** Only `index.js` is copied. Line 38 of `index.js` imports `'./lib.js'`. Container crashes with `ERR_MODULE_NOT_FOUND`.

**Final fix:** Use a wildcard copy instead of individual files to prevent recurrence:

```dockerfile
COPY package.json ./
COPY *.js ./
```

This handles `index.js`, `lib.js`, and any future `.js` files without requiring Dockerfile changes.

**Also add** a `.dockerignore` in `whatsapp-archiver/`:
```
node_modules
.git
*.md
```

---

### FINDING 4 — mbsync PassCmd exposes IMAP password in process list

**Final Verdict: ACCEPT with revised mechanism.**

**File:** `mbsync/mbsyncrc`, line 21

**Root cause:** `PassCmd "echo $ALEX_IMAP_PASS"` spawns a visible shell process. Password appears in `/proc/<pid>/cmdline`.

**Why Docker secrets are rejected:** The `file:` driver for Docker secrets requires Swarm mode, which is not used in this homelab compose setup. Additionally, the devil's advocate correctly noted that isync DOES support `${ENV_VAR}` expansion in config — the original claim that it does not was wrong.

**Final fix:** Use mbsync's native `Password` directive with environment variable substitution:

```
# In mbsync/mbsyncrc, replace line 21:
    Password "$ALEX_IMAP_PASS"
```

The `Password` directive reads the value directly from the process environment without spawning a subprocess, eliminating `/proc/*/cmdline` exposure. The env var is already passed via compose's `environment` block and sourced from `.env` (which is gitignored).

**Ensure:** `ALEX_IMAP_PASS` is in `.env` (gitignored), not committed as plaintext.

---

### FINDING 5 — .hadolint config file never loaded in CI

**Final Verdict: ACCEPT but low priority.**

**File:** `.github/workflows/ci.yml`, lines 106-147

**Root cause:** hadolint-action steps do not reference `.hadolint` (which ignores DL3066 `:latest` tag warning).

**Caveat from challenge:** All five hadolint steps have `no-fail: true`, so they never block CI regardless. The config file has been dead weight since creation.

**Final fix:** Add `args: --config .hadolint` to each hadolint step (note: `config-file` is not a valid parameter for hadolint-action v3.1.0; use the `args` parameter instead):

```yaml
  with:
    dockerfile: Dockerfile
    args: --config .hadolint
    output-file: hadolint-root.txt
    no-color: true
    no-fail: true
```

**Consider:** Whether to remove `no-fail: true` and actually enforce linting, or remove the hadolint steps entirely if they will always be informational.

---

### FINDING 6 — Containers running as root with no security restrictions

**Final Verdict: MODIFIED. Phased approach.**

**Why modified:** The original proposal (`cap_drop: ALL`, `USER recoll` everywhere) is too aggressive. `cap_drop: ALL` breaks networking and requires restoring many capabilities. Recoll-engine's `/root`-based volume mounts require careful migration of config, database, and cache paths.

**Phase A — Low-risk services (implement now):**

Add non-root users to `sms-processor/Dockerfile` and root `Dockerfile` (recoll-webui):

```dockerfile
# sms-processor/Dockerfile (before ENTRYPOINT):
RUN groupadd -r smsproc && useradd -r -g smsproc -d /app -m smsproc \
    && chown -R smsproc:smsproc /app
USER smsproc
```

Add `security_opt: [no-new-privileges:true]` to all compose services. This is safe — it only prevents privilege escalation, which these containers do not need.

**Phase B — Recoll-engine (deferred, requires testing):**

Before implementing:
1. Audit all volume mounts targeting `/root` in compose
2. Determine whether recoll respects `HOME` environment variable for its config path
3. Plan migration of existing xapiandb index data (currently owned by UID 0)
4. Test LibreOffice headless conversion and tesseract OCR as non-root

Use `user: "$UID:$GID"` mapping in compose to match host ownership, then migrate to dedicated container users after testing.

---

### FINDING 7 — chmod 777 on LibreOffice temp directory

**Final Verdict: ACCEPT.**

**File:** `recoll-engine/Dockerfile`, lines 29-30

**Root cause:** `chmod 777` creates world-writable, world-executable directory.

**Final fix:** Add sticky bit (standard for shared temp directories):

```dockerfile
RUN mkdir -p /tmp/libreoffice \
    && chmod 1777 /tmp/libreoffice
```

If combined with Finding 6 Phase B (non-root user), use `chmod 700` with `chown recoll:recoll` instead.

---

### FINDING 8 — Immich server healthcheck uses wrong command

**Final Verdict: ACCEPT with Node.js-based check.**

**File:** `docker-compose.yml`, lines 220-225

**Root cause:** `immich-machine-learning-healthcheck` checks the ML backend, not the server API.

**Why curl is rejected:** The immich-server image is Node.js-based and may not include `curl` or `wget`.

**Final fix:** Use a Node.js one-liner:

```yaml
healthcheck:
  test: ['CMD-SHELL', 'node -e "require(\"http\").get(\"http://localhost:3001/api/server-info/ping\", r => { process.exit(r.statusCode === 200 ? 0 : 1) })" || exit 1']
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

---

### FINDING 9 — Mbsync config mounted to wrong path

**Final Verdict: ACCEPT.**

**File:** `docker-compose.yml`, lines 324-327

**Root cause:** Config mounted to `/home/msync/.mfilter.d` (filter scripts directory). The stefanbuck/m-sync image expects config at `/home/msync/.isync/mbsyncrc`.

**Final fix:** Change mount target:

```yaml
volumes:
  - type: bind
    source: *mbsync-config
    target: /home/msync/.isync
    read_only: true
```

Also update the comment in `mbsync/mbsyncrc` line 4 to reflect the correct mount path.

---

### FINDING 10 — Docker images tagged only as :latest

**Final Verdict: ACCEPT.**

**File:** `.github/workflows/docker.yml`, line 75

**Root cause:** Only `:latest` tag pushed. No rollback capability.

**Final fix:** Add full SHA and short SHA tags:

```yaml
- name: Set short SHA
  id: slug
  run: echo "short_sha=$(echo ${{ github.sha }} | cut -c1-7)" >> "$GITHUB_OUTPUT"

- name: Build and push image
  uses: docker/build-push-action@...
  with:
    tags: |
      ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}:latest
      ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}:${{ github.sha }}
      ghcr.io/${{ github.repository_owner }}/${{ matrix.image }}:${{ steps.slug.outputs.short_sha }}
```

**Note:** Compose still references `:latest`. SHA tags enable manual rollback (`docker pull` with specific tag) but do not change default deploy behavior. For automated rollback, add a `.env.deploy` with image tag variables.

---

### FINDING 11 — Pre-push hooks build all 5 Docker images sequentially

**Final Verdict: MODIFIED.**

**File:** `.pre-commit-config.yaml`, lines 60-98

**Why deletion is rejected:** Removing all Docker build validation eliminates local safety for direct pushes to main. BuildKit cache makes unchanged-image builds nearly instant.

**Final fix:** Replace five sequential hooks with a single hook that parallelizes builds:

```yaml
- id: docker-build-check
  name: Docker build check (parallel)
  entry: .hooks/docker-build-parallel.sh
  language: script
  pass_filenames: false
  always_run: true
  stages: [push]
```

With `.hooks/docker-build-parallel.sh`:

```bash
#!/bin/bash
set -e
ERRORS=0
PIDS=()

for ctx in . ./recoll-engine ./whatsapp-archiver ./sms-processor; do
  docker build --load "$ctx" &
  PIDS+=($!)
done

for pid in "${PIDS[@]}"; do
  wait "$pid" || ERRORS=$((ERRORS + 1))
done

exit $ERRORS
```

Note: `recoll-audio-worker` is removed from this list (see Finding 12).

---

### FINDING 12 — recoll-audio-worker has no functional CMD

**Final Verdict: ACCEPT. Remove from CI entirely.**

**File:** `recoll-audio-worker/Dockerfile`, `.github/workflows/docker.yml`, `.github/workflows/ci.yml`

**Root cause:** CMD is `python3 -c "print('audio worker ready')"`. Prints a message and exits. Not referenced in compose. Installs `faster-whisper` (~300MB) for nothing.

**Final fix:**
1. Remove `recoll-audio-worker` entry from `.github/workflows/docker.yml` build matrix
2. Remove `recoll-audio-worker/Dockerfile` from CI Dockerfile existence check
3. Remove hadolint step for `recoll-audio-worker/Dockerfile`
4. Keep the directory and Dockerfile locally (add a TODO comment) for future implementation

---

### FINDING 13 — Exact package version pins break on archive rotation

**Final Verdict: REJECT.**

**All three specialists challenged this finding.** Ubuntu 22.04 is not EOL (standard support through April 2027, extended through 2032). Its packages are in active repositories and will remain there. Exact version pins provide build reproducibility — a core Docker principle.

**No action required.** When 22.04 eventually reaches EOL, migrate the base image; do not remove version pins preemptively.

---

### FINDING 14 — No .dockerignore files

**Final Verdict: ACCEPT (low priority).**

Create `.dockerignore` in `recoll-engine/` and `sms-processor/`:

```
.git
.github
*.md
__pycache__
*.pyc
*.log
node_modules
dist
build
.coverage
.pytest_cache
.dockerignore
.env
```

Note: `whatsapp-archiver/.dockerignore` already exists (confirmed 28 bytes). The primary value is preventing accidental inclusion of `.env`, `__pycache__`, and IDE files in the build context.

---

### FINDING 15 — recoll-webui without authentication

**Final Verdict: MODIFIED. Simplified for homelab use.**

**Why nginx reverse proxy is rejected:** Three-layer defense (Recoll httpPassword + restricted port binding + nginx sidecar) is enterprise overengineering for a personal TrueNAS setup behind a firewall.

**Final fix — Layer 1 only:** Add `httpPassword` to recoll's configuration:

```
# In the recoll.conf mounted in the container:
httpPassword=your-strong-password
```

If the host already has an edge reverse proxy (Traefik, Caddy, nginx) for other services, add recoll-webui as a backend. Otherwise, Recoll's built-in authentication is sufficient for LAN-only access.

**Optional:** Restrict port mapping to `127.0.0.1:9080:8080` if external LAN access is not needed.

---

### FINDING 16 — WhatsApp reconnect hammers every 5 seconds

**Final Verdict: ACCEPT with module-scoped state.**

**File:** `whatsapp-archiver/index.js`, lines 168-170

**Root cause:** Fixed `setTimeout(main, 5000)` with no backoff. Network instability creates 120 reconnects/minute.

**Why global is rejected:** Using `global.reconnectAttempt` pollutes the Node.js global namespace and can collide with Baileys or other libraries.

**Final fix:** Use a module-level variable:

```javascript
// Module scope, before main():
let reconnectAttempts = 0
const MAX_RETRY_DELAY = 300000  // 5 min cap

// In connection.update handler, connection === 'close' block:
if (shouldReconnect) {
  const baseDelay = Math.min(5000 * Math.pow(2, reconnectAttempts), MAX_RETRY_DELAY)
  const jitter = Math.random() * 1000
  reconnectAttempts++
  console.log(`[archiver] reconnecting in ${Math.round((baseDelay + jitter) / 1000)}s (attempt ${reconnectAttempts})...`)
  setTimeout(main, baseDelay + jitter)
}

// In connection === 'open' block:
reconnectAttempts = 0
```

Note: Baileys has its own internal reconnection logic. This is a second-layer fallback that only fires after Baileys exhausts its retries.

---

### FINDING 17 — SMS processor uses MD5 for change detection

**Final Verdict: REJECT.**

**All three specialists agreed:** MD5 is perfectly adequate for change detection of trusted local SMS backup XML files. The collision probability for two different XML files with identical MD5 is approximately 1 in 2^64 — effectively zero in this context. SHA-256 adds no practical security benefit and forces one-time reprocessing of all files with no real-world improvement.

**No action required.**

---

### FINDING 18 — Hardcoded TrueNAS paths

**Final Verdict: MODIFIED. Minimal scope.**

**Why full parameterization is rejected:** The compose file already uses YAML anchors (`&shuttle`, `&app-data`) defined in `x-constants` at the top, with `*alias` references throughout. Changing a path is a single edit in compose. Environment variable fallbacks add three sources of truth (`.env`, shell, `--env-file`) for a personal homelab that will never be deployed elsewhere.

**Final fix — recollindex.py only:** The Python wrapper has hardcoded paths not covered by YAML anchors:

```python
# In recoll_wrapper/recollindex.py:
import os
BASE_PATH = os.environ.get("RECOLL_BASE_PATH", "/mnt/shuttle/share")
LOG_FILE = os.path.join(BASE_PATH, "app-data/recoll/.recoll/recollindex.log")
# ... other paths use BASE_PATH instead of hardcoded strings
```

Add a documentation comment block at the top of `docker-compose.yml` noting host-specific paths.

---

### FINDING 19 — SMS append-mode files grow indefinitely

**Final Verdict: REJECT.**

**All three specialists agreed:** SMS text is extremely low volume. A very active contact generates approximately 50KB per year of markdown text. At that rate, a file reaches 1MB in roughly 20 years. The "problem" does not exist in practice. Year-based rotation fragments conversations unnecessarily and adds complexity for zero practical benefit.

**No action required.**

---

## 4. Implementation Checklist

### Phase 1 — Quick Wins (implement first, no dependencies)

- [ ] **F2:** Fix `recoll_wrapper/recollindex.py` line 392: `exit_code = proc.returncode`
- [ ] **F3:** Change `whatsapp-archiver/Dockerfile`: replace individual COPY with `COPY *.js ./`
- [ ] **F3:** Add `whatsapp-archiver/.dockerignore` (node_modules, .git, *.md)
- [ ] **F7:** Change `recoll-engine/Dockerfile` line 30: `chmod 1777 /tmp/libreoffice`
- [ ] **F9:** Change `docker-compose.yml` line 326: target `/home/msync/.isync`
- [ ] **F9:** Update comment in `mbsync/mbsyncrc` line 4
- [ ] **F10:** Add SHA tags to `.github/workflows/docker.yml`
- [ ] **F12:** Remove `recoll-audio-worker` from docker.yml matrix, ci.yml checks, and ci.yml hadolint
- [ ] **F14:** Create `recoll-engine/.dockerignore` and `sms-processor/.dockerignore`

### Phase 2 — Medium Effort (test each before merging)

- [ ] **F4:** Change `mbsync/mbsyncrc` line 21: `Password "$ALEX_IMAP_PASS"`
- [ ] **F5:** Add `args: --config .hadolint` to all 5 hadolint steps in ci.yml
- [ ] **F8:** Replace immich-server healthcheck with Node.js HTTP check
- [ ] **F11:** Replace 5 sequential pre-push hooks with parallel build script
- [ ] **F16:** Implement exponential backoff in `whatsapp-archiver/index.js`
- [ ] **F18:** Parameterize paths in `recoll_wrapper/recollindex.py` with env var fallback

### Phase 3 — Large Refactors (plan separately, test thoroughly)

- [ ] **F15:** Add `httpPassword` to recoll.conf
- [ ] **F6A:** Add non-root user to `sms-processor/Dockerfile`; add `no-new-privileges:true` to compose services
- [ ] **F1 (TBD):** Audit recoll-webui Python 2 dependencies; decide between old-releases mirror, CGI migration, or full Python 3 port
- [ ] **F6B:** Plan recoll-engine non-root migration (audit /root volume mounts, test xapiandb as non-root)

---

## 5. Rollback Strategy

### General principle
Each Phase 1 fix is small enough to revert individually via `git revert`. Phase 2 changes should be tested in a development compose environment before applying to production. Phase 3 items require a maintenance window and explicit rollback plan per item.

### Specific rollbacks

| Finding | Rollback action |
|---------|----------------|
| F2 | Revert line 392 to `proc.returncode or 1`. Low risk — the bug is trivially identifiable (recollindex always reports failure). |
| F3 | Revert to individual COPY lines. Container was already broken; this fix cannot make it worse. |
| F4 | If `Password` directive fails, revert to `PassCmd "echo $ALEX_IMAP_PASS"`. The password exposure risk remains but functionality is restored. |
| F7 | Change back to `chmod 777`. The security improvement is minor; rollback is trivial. |
| F8 | If Node.js healthcheck fails (e.g., syntax error), revert to original `immich-machine-learning-healthcheck`. Service reports unhealthy but does not crash. |
| F9 | If mbsync fails after path change, revert target to `/home/msync/.mfilter.d`. The service was already broken; this fix cannot make it worse. |
| F10 | SHA tags are additive. No rollback needed — old `:latest` behavior continues unchanged. |
| F11 | If parallel build script fails, restore original 5 sequential hooks from git history. |
| F12 | Restore audio-worker entries in docker.yml and ci.yml from git history. |
| F16 | Revert `setTimeout(main, 5000)` to fixed delay. The reconnect hammering returns but functionality is restored. |
| F6A/B | If non-root user causes permission errors, remove `USER` directive and restore root execution. Recoll-engine requires careful testing first; do not apply without verified volume ownership. |
| F15 | Remove `httpPassword` from recoll.conf. Authentication reverts to open access. |

### Emergency procedure
If multiple Phase 1 changes are applied in one commit and a problem is discovered:
1. Identify the failing service via `docker compose logs <service>`
2. Either revert the specific file change or run `git revert <commit-sha>` for a full rollback
3. Rebuild affected images: `docker compose build <service>`
4. Restart: `docker compose up -d <service>`

### Pre-implementation checklist
Before applying any phase:
1. Ensure git working tree is clean: `git status --short`
2. Create a branch: `git checkout -b fix/<finding-number>-<slug>`
3. Apply changes, test locally
4. Run linting: `uv run ruff check .`
5. Create PR, verify CI passes
6. Monitor production for 24 hours after merge
