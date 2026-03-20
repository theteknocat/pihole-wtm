# Configuration Reference

All configuration is provided via environment variables. In Docker Compose deployments these are set in `docker-compose.yml` or a `.env` file. In ddev they are set in `.ddev/config.yaml` under `web_environment`. In bare-metal deployments they can be exported in a shell or placed in a `.env` file.

> **Planned enhancement:** A `pihole-wtm setup` CLI command is planned that will interactively prompt for all required values and write a `.env` file. See [Setup Script](#setup-script) below.

---

## Pi-hole Connection

### `PIHOLE_API_URL`

Base URL of the Pi-hole web interface. **Optional** — if not set, the user is prompted to enter the URL on the login page (see [authentication.md](authentication.md) for the two-tier URL system).

**Default:** `http://pihole`

**Examples:**

```text
PIHOLE_API_URL=http://192.168.1.1
PIHOLE_API_URL=http://pihole.home.arpa
PIHOLE_API_URL=http://pihole          # Docker container name on shared network
```

Do not include a trailing slash or path — the backend appends `/api/...` automatically.

> **Note:** The Pi-hole password is entered via the login page and held in server memory only — it is never stored in environment variables, config files, or the database. Pi-hole v6 is required; Pi-hole v5 is not supported.

---

## Session

### `SESSION_TIMEOUT_HOURS`

How many hours an idle session lasts before the user must log in again. The timeout resets on each authenticated API request.

**Default:** `24`

On session expiry the sync service stops and the user is redirected to the login page. Setting a higher value is fine for a local dashboard — sessions are memory-only and cleared on server restart regardless.

---

## Local Database

### `LOCAL_DB_PATH`

Path where the local sync database (`pihole_wtm.db`) is stored. Created automatically on first run. The directory must be writable by the backend process.

**Default:** `/app/data/pihole_wtm.db`

In Docker deployments, mount a named volume to persist the database across restarts:

```yaml
volumes:
  - pihole_wtm_data:/app/data
```

---

### `SYNC_INTERVAL_SECONDS`

How often the sync service polls Pi-hole for new queries.

**Default:** `60`

Lower values mean more up-to-date data but more frequent Pi-hole API calls. Values below 10 are not recommended.

---

### `DATA_RETENTION_DAYS`

How many days of query data to keep in the local database. Queries older than this are automatically deleted each sync cycle, and domain records with no remaining queries are cleaned up.

**Default:** `7`

This matches the maximum time window available in the dashboard (7 days). Setting a higher value retains more historical data but increases database size. The dashboard will never display data beyond 7 days regardless of this setting.

---

## Disconnect.me

### `DISCONNECT_UPDATE_INTERVAL_HOURS`

How often the Disconnect.me tracking protection list is refreshed from GitHub. The list is loaded into memory on startup and re-fetched in the background when it becomes stale.

**Default:** `24`

Set to `0` to disable automatic updates (the list loaded on startup will be used indefinitely).

---

## TrackerDB

### `TRACKERDB_PATH`

Path where the Ghostery TrackerDB SQLite file is stored. Downloaded automatically from GitHub Releases on startup if absent or stale. The directory must be writable by the backend process.

**Default:** `/app/data/trackerdb.db`

In Docker deployments this shares the same named volume as `LOCAL_DB_PATH`:

```yaml
volumes:
  - pihole_wtm_data:/app/data
```

---

### `TRACKERDB_UPDATE_INTERVAL_HOURS`

How often to check for a newer TrackerDB release from Ghostery. The backend queries the GitHub Releases API and downloads a new file if a newer version is available.

**Default:** `24`

Set to `0` to disable automatic updates entirely.

---

### `TRACKERDB_RELEASE`

Pin the TrackerDB to a specific GitHub release tag instead of always fetching the latest.

**Default:** `latest`

**Example:**

```text
TRACKERDB_RELEASE=202603111257
```

Useful for reproducible deployments or if a newer release has a schema change.

---

## Application Server

### `APP_HOST`

Host address for uvicorn to bind to.

**Default:** `0.0.0.0`

---

### `APP_PORT`

Port for the uvicorn server.

**Default:** `8000`

---

### `LOG_LEVEL`

Logging verbosity for both uvicorn and the Python logging module.

| Value      | Description                           |
| ---------- | ------------------------------------- |
| `debug`    | Verbose — HTTP requests, cache events |
| `info`     | Normal operation (recommended)        |
| `warning`  | Warnings and errors only              |
| `error`    | Errors only                           |
| `critical` | Critical failures only                |

**Default:** `info`

---

### `CORS_ORIGINS`

Allowed CORS origins for the browser frontend. Provide as a comma-separated string.

**Default:** `http://localhost:5173,http://localhost:5174`

In production, set this to the origin your frontend is actually served from:

```text
CORS_ORIGINS=https://pihole-wtm.yourdomain.local
```

Multiple origins, comma-separated:

```text
CORS_ORIGINS=https://pihole-wtm.yourdomain.local,http://localhost:5173
```

---

## Docker Deployment

### `DASHBOARD_PORT`

Host port that the nginx frontend container binds to.

**Default:** `8080`

---

### `PIHOLE_NETWORK`

Name of the Docker network Pi-hole is connected to. The backend joins this network to reach Pi-hole by container name.

**Default:** `pihole_default`

```bash
docker network ls
docker inspect <pihole-container-name> | grep NetworkMode
```

---

## Example `.env` Files

### Docker Compose (recommended)

```bash
PIHOLE_API_URL=http://pihole
PIHOLE_NETWORK=pihole_default
DASHBOARD_PORT=8080
CORS_ORIGINS=http://your-host:8080
```

### Bare-metal

```bash
PIHOLE_API_URL=http://192.168.1.1
LOCAL_DB_PATH=/var/lib/pihole-wtm/pihole_wtm.db
TRACKERDB_PATH=/var/lib/pihole-wtm/trackerdb.db
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=info
CORS_ORIGINS=http://localhost:8080
```

> **Note:** The Pi-hole password is not configured here — it is entered on the login page at runtime. See [authentication.md](authentication.md) for details.

---

## Setup Script

> **Status: Planned**

A `pihole-wtm setup` command is planned for users who prefer a guided terminal experience over editing a `.env` file manually. It will:

- Prompt for each required value with sensible defaults
- Validate the Pi-hole URL and password by attempting a connection before writing anything
- Write a `.env` file (or print to stdout for piping)
- Be safe to re-run — will prompt before overwriting an existing `.env`

**Planned usage:**

```bash
# Docker
docker run --rm -v pihole_wtm_data:/app/data pihole-wtm setup

# Bare-metal
pihole-wtm setup

# Print to stdout instead of writing a file (for review or piping)
pihole-wtm setup --dry-run
```

This will be implemented as a `click` CLI command registered as a package entry point in `pyproject.toml`.
