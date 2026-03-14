# Configuration Reference

All configuration is provided via environment variables. In Docker Compose deployments these are set in `docker-compose.yml` or a `.env` file. In ddev they are set in `.ddev/config.yaml` under `web_environment`. In bare-metal deployments they can be exported in a shell or placed in a `.env` file.

> **Planned enhancement:** A `pihole-wtm setup` CLI command is planned that will interactively prompt for all required values and write a `.env` file. See [Setup Script](#setup-script) below.

---

## Pi-hole Connection

### `PIHOLE_API_URL`

Base URL of the Pi-hole web interface.

**Default:** `http://pihole`

**Examples:**

```text
PIHOLE_API_URL=http://192.168.1.1
PIHOLE_API_URL=http://pihole.home.arpa
PIHOLE_API_URL=http://pihole          # Docker container name on shared network
```

Do not include a trailing slash or path — the backend appends `/api/...` automatically.

---

### `PIHOLE_API_PASSWORD`

Pi-hole web interface password. Used to obtain a session token from the Pi-hole v6 API.

**Default:** empty (works if Pi-hole has no password set)

This value is treated as a secret and will never appear in logs.

---

### `PIHOLE_API_VERSION`

Force a specific Pi-hole API version.

| Value  | Description                                        |
| ------ | -------------------------------------------------- |
| `v6`   | Pi-hole 6.x — REST API with session authentication |
| `auto` | Auto-detect (currently always uses v6 behaviour)   |

**Default:** `auto`

> **Note:** Pi-hole v5 support is not yet implemented. Only `v6` is functional. `v5` is accepted by the setting but will not work correctly.

---

## TrackerDB

### `TRACKERDB_PATH`

Path where the Ghostery TrackerDB SQLite file is stored. Downloaded automatically from GitHub Releases on startup if absent or stale. The directory must be writable by the backend process.

**Default:** `/app/data/trackerdb.db`

In Docker deployments, mount a named volume to persist the database across restarts:

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

List of allowed CORS origins for the browser frontend. Must be provided as a JSON array.

**Default:** `["http://localhost:5173", "http://localhost:5174"]`

In production, set this to the origin your frontend is actually served from:

```text
CORS_ORIGINS=["https://pihole-wtm.yourdomain.local"]
```

In a ddev environment, include the ddev site URL:

```text
CORS_ORIGINS=["https://pihole-wtm.ddev.site:5174","http://localhost:5173"]
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
PIHOLE_API_PASSWORD=your-pihole-password
PIHOLE_NETWORK=pihole_default
DASHBOARD_PORT=8080
CORS_ORIGINS=["http://your-host:8080"]
```

### Bare-metal

```bash
PIHOLE_API_URL=http://192.168.1.1
PIHOLE_API_PASSWORD=your-pihole-password
TRACKERDB_PATH=/var/lib/pihole-wtm/trackerdb.db
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=info
CORS_ORIGINS=["http://localhost:8080"]
```

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
