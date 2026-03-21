# Development Setup

pihole-wtm uses [ddev](https://ddev.com/) for local development. ddev provides a consistent, Docker-based environment that runs the FastAPI backend and Vite dev server side by side.

## Prerequisites

- [ddev](https://ddev.readthedocs.io/en/stable/users/install/ddev-installation/) (v1.23+)
- Docker (Docker Desktop or Docker Engine + Docker Compose plugin)
- Git

You do **not** need Python, Node.js, or any other runtimes installed locally — ddev provides them inside containers.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/theteknocat/pihole-wtm.git
cd pihole-wtm
```

### 2. Start the ddev environment

```bash
ddev start
```

This will:

- Pull and start the ddev web container
- Install Python dependencies via `uv` into the container
- Install Node.js dependencies via `npm install`
- Start the FastAPI backend with `uvicorn --reload` on port 8000
- Start the Vite dev server on port 5173

### 3. Configure the Pi-hole connection (optional)

For convenience during development, set the Pi-hole connection in `.ddev/config.local.yaml` (gitignored):

```yaml
web_environment:
  - PIHOLE_API_URL=http://192.168.1.1       # your Pi-hole's address
  - PIHOLE_API_PASSWORD=your_password        # enables always-on sync
```

Then restart ddev for the changes to take effect:

```bash
ddev restart
```

Both are optional — if not set, you'll enter the URL and password on the login page each session. For active development, setting both is convenient so sync runs immediately on `ddev start`.

### 4. Open the dashboard

The Vite dev server proxies `/api` requests to the FastAPI backend, so the dashboard is available at:

```text
https://pihole-wtm.ddev.site
```

The FastAPI backend is also accessible directly (useful for Swagger UI):

```text
https://pihole-wtm.ddev.site:8443
https://pihole-wtm.ddev.site:8443/docs
```

## Daily Development

### Running backend tests

```bash
ddev exec -d /var/www/html/backend pytest
```

With coverage:

```bash
ddev exec -d /var/www/html/backend pytest --cov=app --cov-report=term-missing
```

### Running frontend tests

```bash
ddev exec -d /var/www/html/frontend npm run test
```

### Linting

Backend (ruff):

```bash
ddev exec -d /var/www/html/backend ruff check app tests
```

Backend type checking (mypy):

```bash
ddev exec -d /var/www/html/backend mypy app
```

Frontend (ESLint + vue-tsc):

```bash
ddev exec -d /var/www/html/frontend npm run lint
ddev exec -d /var/www/html/frontend npm run type-check
```

### Restarting services

If you change backend dependencies (`pyproject.toml`) or need a clean restart:

```bash
ddev restart
```

To restart just the FastAPI process (it uses `--reload` so file saves trigger this automatically):

```bash
ddev exec supervisorctl restart fastapi
```

## Adding Backend Dependencies

Dependencies are managed with `uv`. To add a package:

```bash
ddev exec -d /var/www/html/backend uv add some-package
```

This updates `pyproject.toml` and `uv.lock`. Commit both files.

## Adding Frontend Dependencies

```bash
ddev exec -d /var/www/html/frontend npm install some-package
```

Commit the updated `package.json` and `package-lock.json`.

## Stopping the Environment

```bash
ddev stop
```

## Troubleshooting

**Backend not starting**: Check ddev logs with `ddev logs`. Look for Python import errors or missing configuration.

**Frontend not loading**: Check that the Vite dev server started with `ddev logs --follow`. Port conflicts can sometimes prevent it from binding.

**TrackerDB not downloading**: In restricted network environments, the container may not be able to reach GitHub. You can manually copy a `trackerdb.db` file into `backend/data/` and it will be used instead.

**Pi-hole connection failing**: Run `ddev exec curl http://your-pihole/api/auth` to verify network reachability from within the ddev container.
