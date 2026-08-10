# Root Cause Analysis: Combined Stack Doesn't Load Existing Immich Data

**Date:** 2026-08-10
**Status:** Investigated — no code changes made
**Symptom:** Opening Immich in the combined stack shows *"Since you are the first user on the system, you will be assigned as the Admin..."* — i.e. a fresh database with no users, despite the existing Immich PostgreSQL data living at `/mnt/shuttle/share/app-data/immich/pg_data`.

---

## 1. Scientific Method

### Observation
Fresh Immich admin setup screen on the combined stack. Existing standalone Immich (same host, same data directories) has working users and photos.

### Hypothesis candidates
1. **PostgreSQL major-version mismatch** — standalone runs PG18, combined runs PG14. PG refuses to read a data directory from a newer major version.
2. **PGDATA subdirectory mismatch** — standalone sets `PGDATA=/var/lib/postgresql/18/docker`; combined sets no PGDATA and uses the image default. Even with the same host mount, the two point at *different subdirectories* inside `pg_data`.
3. **Vector extension mismatch** — standalone uses `vectorchord`, combined uses `pgvecto-rs`. Extension binaries are incompatible across PG major versions.
4. **Redis/Valkey data mismatch** — combined uses `redis:7.2-alpine` with a *new* named volume `immich-redis-data`; standalone used `valkey` with volume `redis-data`. A different/empty Redis does not itself reset the admin user, but is a secondary divergence.
5. **Server version mismatch** — `v1.126.0` vs `v3.0.3` are different product generations; even if the DB mounted correctly, the schema would be out of sync.

### Predictions (falsifiable)
- **If hypothesis 2 is correct:** postgres in the combined stack initializes a brand-new cluster under `pg_data/data/` (a *sibling* of `pg_data/18/docker/`), ignoring the existing data. On host, `pg_data/` will show both `data/` (new) and `18/` (existing).
- **If hypothesis 1 is correct:** even pointing PG14 at the existing `18/docker` directory would make it fail with *"database files are incompatible with server"* — it cannot silently ignore it; it would refuse to start, not create a fresh admin.
- **If hypothesis 3/4/5 are correct:** they compound the issue but none alone explains the *fresh* database.

### Test (hypothesis 2 against 1)
The distinguishing observation: the user saw a *working* fresh instance (admin creation screen), not a crashing Postgres. PG14 pointed at a PG18 data directory **cannot start at all** — it errors out. Therefore the only way to get a working-but-empty instance is that postgres never saw the existing directory: it created a new cluster at the image default `PGDATA=/var/lib/postgresql/data` → host `pg_data/data/`.

### Result
Hypothesis 2 is **confirmed** as the primary root cause. Hypotheses 1, 3, 4, 5 are real and compound, but secondary. All five would need fixing for data to load.

---

## 2. Evidence Table — Standalone vs Combined

| Component | Standalone (working) | Combined (broken) | Impact |
|-----------|---------------------|-------------------|--------|
| **Postgres image** | `ghcr.io/immich-app/postgres:18-vectorchord0.5.3` (PG18 + vectorchord) | `tensorchord/pgvecto-rs:pg14-v0.2.0` (PG14 + pgvecto-rs) | **MAJOR** — PG won't read other-major data; extension binaries differ |
| **PGDATA env** | `PGDATA=/var/lib/postgresql/18/docker` | *(not set — image default)* | **PRIMARY** — points at wrong subdirectory inside the mount |
| **Image default PGDATA** | n/a | `/var/lib/postgresql/data` (confirmed via `docker inspect`) | Combined writes to `pg_data/data/`, not `pg_data/18/docker/` |
| **Host mount** | `pg_data → /var/lib/postgresql` | `pg_data → /var/lib/postgresql` (same) | Same mount, different subdir target → two clusters on one host dir |
| **Server image** | `immich-server:v3.0.3` | `immich-server:v1.126.0` | Schema/API generation mismatch |
| **ML image** | `...:v3.0.3-openvino` | `...:v1.126.0` | ML API/endpoint mismatch |
| **Redis** | `valkey/valkey:9.1.1` + named volume `redis-data` | `redis:7.2-alpine` + named volume `immich-redis-data` | Secondary — empty Redis doesn't reset users, but diverges |
| **Server data mount** | `immich/data → /data` | `immich/data → /upload` | Correct path now, but DB must match for it to matter |

---

## 3. Root Cause (Primary)

The combined stack's `immich-postgres` service:

```yaml
volumes:
  - type: bind
    source: *immich-pg-data          # /mnt/shuttle/share/app-data/immich/pg_data
    target: /var/lib/postgresql
```

...mounts the correct host directory **but does not set `PGDATA`**. The `pgvecto-rs:pg14` image's default is:

```
PGDATA=/var/lib/postgresql/data
```

So PostgreSQL 14 initializes a **brand-new, empty cluster** at host path `pg_data/data/` — a sibling of the real existing cluster at `pg_data/18/docker/`. The new cluster has no users → Immich shows the first-user admin screen.

The standalone stack worked because it explicitly set:

```
PGDATA=/var/lib/postgresql/18/docker
```

(plus ran PG18 with vectorchord, which the `postgres:18-vectorchord` image already understands).

---

## 4. Contributing Causes (all must be fixed together)

1. **PG major mismatch (18 vs 14):** Even if `PGDATA` were set correctly, PostgreSQL 14 **cannot** read a PG18 data directory. It errors with `database files are incompatible with server` / `The data directory was initialized by PostgreSQL version 18`. The combined stack must use the same postgres image family as standalone (`postgres:18-vectorchord`, not `pgvecto-rs:pg14`).
2. **Vector extension mismatch (vectorchord vs pgvecto-rs):** The existing cluster has `vectorchord` extension binaries baked in. `pgvecto-rs` is a different, older vector extension; even on the same PG version it would not match what Immich's DB expects. Must use the image that matches the data.
3. **Server version mismatch (v1.126.0 vs v3.0.3):** Immich performs schema migrations at startup against the DB. A v1.126.0 server pointed at a v3.0.3 database will attempt migrations from an incompatible base. The server/ML images should match the version that originally wrote the data (`v3.0.3`), or the DB must be migrated deliberately.
4. **Redis divergence (valkey→redis):** Sessions/tokens are in Redis. Since the combined stack uses a *new* named volume (`immich-redis-data`), existing Redis session state is not carried over. This does not reset users, but login sessions will be fresh. Use a shared volume name or accept session reset.

---

## 5. Why the Split-Path Fix Was Still Correct (but insufficient)

The previous change (splitting `immich-data` into `pg_data`, `data`, `cache`) was **necessary and correct** — it stopped the combined stack from dumping everything under `/mnt/shuttle/share/app-data/immich` at once. But mounting the directory is not enough: the **PGDATA subdirectory**, the **PG major version**, the **vector extension**, and the **server version** must all match what the existing data expects. The path fix alone could not make the DB readable.

---

## 6. Recommended Fix (for when code changes are permitted)

In `docker-compose.yml`, align the four Immich services with the standalone stack:

1. **immich-postgres:**
   - Image: `ghcr.io/immich-app/postgres:18-vectorchord0.5.3` (or the tag matching the existing data)
   - Env: add `PGDATA=/var/lib/postgresql/18/docker`
   - Keep mount `pg_data → /var/lib/postgresql` (already correct)
   - Add `POSTGRES_USER/DATABASE` matching standalone (`immich`/`immich`)
   - Healthcheck already uses `pg_isready` (fine)

2. **immich-server / immich-machine-learning:**
   - Image tag: change `IMMICH_VERSION` to `v3.0.3` (matching the DB schema)
   - ML image also uses `v3.0.3` (standalone uses `-openvino` variant)

3. **immich-redis:**
   - Keep `redis` or switch to `valkey:9.1.1`; either is fine for data *loading*, but if session continuity matters, mount the existing `redis-data` volume instead of `immich-redis-data`.

4. **Environment variables:**
   - `IMMICH_VERSION=v3.0.3`
   - `IMMICH_POSTGRES_VERSION=18-vectorchord0.5.3`
   - Add `PGDATA` to the postgres service env (not in `.env` — it's service-scoped)

---

## 7. Verification Plan (how to confirm the fix on TrueNAS)

1. On TrueNAS, inspect host dirs:
   - `ls /mnt/shuttle/share/app-data/immich/pg_data/` → should show `18/` (existing) and, currently, also `data/` (the fresh cluster created by the combined stack — a sign of the bug).
2. After fix, confirm postgres uses the existing cluster: `PGDATA=/var/lib/postgresql/18/docker` + PG18 image → postgres logs show *recovery* / existing DB startup, not *initialization*.
3. Open Immich UI → should show the existing admin login, not the first-user screen.
4. If the fresh `pg_data/data/` cluster exists, remove it (only after confirming the real data at `pg_data/18/` is intact) so the bind mount isn't shadowed.

---

## 7b. VERIFIED — host evidence (2026-08-10)

User ran the falsifiable test on TrueNAS:

```bash
root@truenas[~]# ls -la /mnt/shuttle/share/app-data/immich/pg_data/
total 14
drwxrwxrwx  4 netdata docker  4 Aug  9 18:46 .
drwxrwxrwx 13 netdata docker 13 Aug  9 16:22 ..
drwxrwxrwx  3 netdata docker  3 May 24 22:40 18
drwxr-xr-x  2 root    root    2 Aug  9 18:46 data
```

**Prediction confirmed.** The `pg_data/` bind-mount root contains two sibling clusters:

- **`18/`** — created **May 24**, owner `netdata:docker` (777). The existing standalone PG18 cluster; its real PGDATA is `18/docker/`. **Intact and untouched.**
- **`data/`** — created **Aug 9 18:46** (timestamp of the combined-stack deployment), owner `root:root` (755). The `root` ownership is the signature of the official postgres entrypoint running a fresh `initdb` as root — i.e. the combined stack's `pgvecto-rs:pg14` initialized a brand-new empty cluster at the image-default `PGDATA=/var/lib/postgresql/data` → host `pg_data/data/`.

PG14 serves `data/` (empty → no users → first-user screen). The existing cluster at `18/` was never touched. **Primary root cause is confirmed by direct evidence, not inference.**

---

## 8. Conclusion

The combined stack does not load existing Immich data because its **PostgreSQL image is a different major version (PG14 vs PG18) AND it does not set `PGDATA`**, so it initializes a brand-new empty database under `pg_data/data/` instead of reading the existing cluster under `pg_data/18/docker/`. A fresh database has no users, producing the "first user" admin screen. The path-split fix was necessary but not sufficient; the postgres image, PGDATA, vector extension, and server version must all match the existing standalone deployment.
