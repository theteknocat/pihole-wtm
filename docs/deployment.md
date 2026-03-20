# Deployment Guide

pihole-wtm can be deployed in two ways depending on your setup. All modes expose the dashboard on a configurable HTTP port.

> **Pi-hole v6 is required.** pihole-wtm connects to the Pi-hole v6 REST API and is not compatible with Pi-hole v5.

---

## Mode 1: Docker Compose (Recommended)

Use this when pihole-wtm and Pi-hole run in **separate Docker containers**, or when Pi-hole is on a **different host** entirely. pihole-wtm connects to Pi-hole's HTTP API over the network and maintains its own local database.

### Docker Prerequisites

- Docker Engine + Docker Compose plugin (or Docker Desktop)
- A running Pi-hole v6 instance accessible over HTTP
- Your Pi-hole web password (if one is set)

### Docker Steps

1. Clone the repository:

   ```bash
   git clone https://github.com/your-org/pihole-wtm.git
   cd pihole-wtm
   ```

2. Configure environment:

   ```bash
   cp .env.example .env
   ```

   Edit `.env`:

   ```bash
   PIHOLE_API_URL=http://192.168.1.1     # Pi-hole address (or container name)
   DASHBOARD_PORT=8080
   CORS_ORIGINS=http://your-host:8080
   ```

   `PIHOLE_API_URL` is optional — if left unset, you'll be prompted to enter it on the login page. If Pi-hole is in Docker on the same host, use its container name and set `PIHOLE_NETWORK` to its Docker network name, then uncomment the external network block in `docker-compose.yml`.

3. Start the dashboard:

   ```bash
   docker compose up -d
   ```

4. Open `http://your-host:8080` in your browser and log in with your Pi-hole password.

### Updating

```bash
docker compose pull
docker compose up -d
```

---

## Mode 2: Bare-Metal Install

Use this when you want to run pihole-wtm directly on the host without Docker.

### Bare-Metal Prerequisites

- Python 3.12+
- Node.js 22+ and npm (for the initial frontend build)
- nginx (or another web server)
- `uv` (Python package manager): `pip install uv`

### Bare-Metal Steps

1. Clone the repository:

   ```bash
   git clone https://github.com/your-org/pihole-wtm.git
   cd pihole-wtm
   ```

2. Install backend dependencies:

   ```bash
   cd backend && uv venv && uv pip install -e . && cd ..
   ```

3. Build the frontend:

   ```bash
   cd frontend && npm install && npm run build && cd ..
   ```

   The built files are in `frontend/dist/`.

4. Create the data directory and configure environment:

   ```bash
   mkdir -p /var/lib/pihole-wtm
   ```

   Create `/etc/pihole-wtm/pihole-wtm.env`:

   ```bash
   PIHOLE_API_URL=http://192.168.1.1
   LOCAL_DB_PATH=/var/lib/pihole-wtm/pihole-wtm.db
   TRACKERDB_PATH=/var/lib/pihole-wtm/trackerdb.db
   APP_HOST=127.0.0.1
   APP_PORT=8000
   LOG_LEVEL=info
   CORS_ORIGINS=http://your-host
   ```

   The Pi-hole password is not stored in config — you enter it on the login page.

5. Configure nginx — copy `nginx.conf` to `/etc/nginx/sites-available/pihole-wtm`, set the `root` to your `frontend/dist/` path, then reload:

   ```bash
   cp nginx.conf /etc/nginx/sites-available/pihole-wtm
   ln -s /etc/nginx/sites-available/pihole-wtm /etc/nginx/sites-enabled/
   nginx -t && systemctl reload nginx
   ```

6. Create `/etc/systemd/system/pihole-wtm.service` and start the backend:

   ```ini
   [Unit]
   Description=pihole-wtm backend
   After=network.target

   [Service]
   Type=simple
   User=www-data
   EnvironmentFile=/etc/pihole-wtm/pihole-wtm.env
   WorkingDirectory=/path/to/pihole-wtm/backend
   ExecStart=/path/to/pihole-wtm/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
   Restart=on-failure
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   systemctl daemon-reload && systemctl enable --now pihole-wtm
   ```

7. Open `http://your-host` in your browser and log in with your Pi-hole password.

---

## Upgrading

For Docker deployments:

```bash
docker compose pull && docker compose up -d
```

For bare-metal deployments, `git pull` the repository, reinstall backend dependencies, rebuild the frontend, and restart the systemd service.

---

## Data Persistence

pihole-wtm maintains two files in its data directory:

- `pihole-wtm.db` — the local sync database. Contains your filtered query history and all enrichment results. **Back this up** if you want to preserve history.
- `trackerdb.db` — the Ghostery TrackerDB. Downloaded and updated automatically. Safe to delete (will be re-downloaded).

In Docker deployments, mount a named volume so these persist across container restarts:

```yaml
services:
  backend:
    volumes:
      - pihole_wtm_data:/app/data

volumes:
  pihole_wtm_data:
```
