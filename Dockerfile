# =============================================================
# pihole-wtm — multi-stage production image
# Stage 1: Build Vue frontend
# Stage 2: Final image with nginx + Python backend
# =============================================================

# --- Stage 1: Build frontend ---
FROM --platform=linux/amd64 node:22-alpine AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build


# --- Stage 2: Production image ---
FROM python:3.12-slim

# Install nginx and supervisor
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends nginx supervisor && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy backend source
COPY backend/ ./

# Copy built frontend
COPY --from=frontend-build /build/dist /usr/share/nginx/html

# Copy nginx config
COPY docker/nginx.conf /etc/nginx/sites-available/default

# Create data directory for SQLite databases
RUN mkdir -p /app/data

# Supervisor config — runs nginx + uvicorn together
RUN cat > /etc/supervisor/conf.d/pihole-wtm.conf <<'EOF'
[supervisord]
nodaemon=true
user=root

[program:nginx]
command=nginx -g "daemon off;"
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:uvicorn]
command=python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
directory=/app
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
EOF

EXPOSE 80

VOLUME /app/data

CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
