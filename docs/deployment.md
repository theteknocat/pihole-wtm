# Deployment Guide

pihole-wtm can be deployed in three ways depending on your setup. All modes expose the dashboard on a configurable HTTP port.

---

## Mode 1: Docker Compose — Pi-hole API (Recommended for most users)

Use this when pihole-wtm and Pi-hole run in **separate Docker containers**, or when Pi-hole is on a **different host** entirely. pihole-wtm connects to Pi-hole's HTTP API over the network.

### Prerequisites

- Docker Engine + Docker Compose plugin (or Docker Desktop)
- A running Pi-hole instance accessible over HTTP
- Your Pi-hole web password (if one is set)

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/your-org/pihole-wtm.git
cd pihole-wtm
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env`:

```bash
PIHOLE_MODE=api
PIHOLE_API_URL=http://192.168.1.1     # Pi-hole address (or container name)
PIHOLE_API_PASSWORD=your_password
PIHOLE_API_VERSION=v6                  # or v5 for older Pi-hole
DASHBOARD_PORT=8080
```

If Pi-hole is running in Docker on the **same host**, use the container name instead of an IP address and join Pi-hole's Docker network. Add this to your `.env`:

```bash
PIHOLE_API_URL=http://pihole           # Pi-hole container name
PIHOLE_NETWORK=pihole_default          # Pi-hole's Docker network (check with: docker network ls)
```

Then uncomment the `pihole_network` external network block in `docker-compose.yml`.

**3. Start the dashboard**

```bash
docker compose up -d
```

**4. Access the dashboard**

Open `http://your-host:8080` in your browser.

### Updating

```bash
docker compose pull
docker compose up -d
```

---

## Mode 2: Docker Compose — Direct SQLite Access

Use this when pihole-wtm runs on the **same host** as Pi-hole (bare-metal or VM, not Docker). You mount Pi-hole's database file directly into the container for faster, richer data access.

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/your-org/pihole-wtm.git
cd pihole-wtm
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env`:

```bash
PIHOLE_MODE=sqlite
PIHOLE_SQLITE_PATH=/pihole/pihole-FTL.db   # path inside container (see volume below)
DASHBOARD_PORT=8080
```

**3. Mount the Pi-hole database (read-only)**

Edit `docker-compose.yml` and uncomment the volume mount in the `backend` service:

```yaml
services:
  backend:
    volumes:
      - trackerdb_data:/app/data
      - /etc/pihole/pihole-FTL.db:/pihole/pihole-FTL.db:ro   # ← uncomment this
```

Adjust the host path (`/etc/pihole/pihole-FTL.db`) if your Pi-hole database is in a different location.

**4. Start the dashboard**

```bash
docker compose up -d
```

**5. Access the dashboard**

Open `http://your-host:8080` in your browser.

---

## Mode 3: Bare-Metal Install

Use this when you want to run pihole-wtm directly on the Pi-hole host without Docker. This gives direct SQLite access without any container overhead.

### Prerequisites

- Python 3.12+
- Node.js 22+ and npm (for the initial frontend build)
- nginx (or another web server)
- `uv` (Python package manager): `pip install uv`

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/your-org/pihole-wtm.git
cd pihole-wtm
```

**2. Install backend dependencies**

```bash
cd backend
uv venv
uv pip install -e .
cd ..
```

**3. Build the frontend**

```bash
cd frontend
npm install
npm run build
cd ..
```

The built files are in `frontend/dist/`.

**4. Configure environment**

Create `/etc/pihole-wtm/pihole-wtm.env`:

```bash
PIHOLE_MODE=sqlite
PIHOLE_SQLITE_PATH=/etc/pihole/pihole-FTL.db
TRACKERDB_PATH=/var/lib/pihole-wtm/trackerdb.db
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=info
```

Create the data directory:

```bash
mkdir -p /var/lib/pihole-wtm
```

**5. Configure nginx**

Copy `nginx.conf` to `/etc/nginx/sites-available/pihole-wtm`:

```bash
cp nginx.conf /etc/nginx/sites-available/pihole-wtm
ln -s /etc/nginx/sites-available/pihole-wtm /etc/nginx/sites-enabled/
```

Edit the file to set the correct `root` path:

```nginx
location / {
    root /path/to/pihole-wtm/frontend/dist;
    # ... rest of config
}
```

Reload nginx:

```bash
nginx -t && systemctl reload nginx
```

**6. Run the backend with systemd**

Create `/etc/systemd/system/pihole-wtm.service`:

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

Enable and start:

```bash
systemctl daemon-reload
systemctl enable pihole-wtm
systemctl start pihole-wtm
```

**7. Access the dashboard**

Open `http://your-host` (default nginx port 80) in your browser.

---

## Permissions

In all deployment modes, pihole-wtm needs **read-only** access to `pihole-FTL.db` (SQLite mode only). The file is owned by `pihole:pihole` on a standard Pi-hole installation. The pihole-wtm process or container user must be in the `pihole` group, or the file permissions must allow world-readable access.

To add a user to the pihole group:

```bash
usermod -aG pihole www-data    # for bare-metal nginx/systemd setup
```

In Docker, the `ro` volume mount flag ensures read-only access is enforced at the container level regardless of file permissions.

---

## Upgrading

For Docker deployments, pull the latest image and recreate containers:

```bash
docker compose pull && docker compose up -d
```

For bare-metal deployments, `git pull` the repository, reinstall backend dependencies, rebuild the frontend, and restart the systemd service.
