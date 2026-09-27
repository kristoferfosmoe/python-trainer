# syntax=docker/dockerfile:1
# Two images from one file (build context: the repository root):
#   --target web    Django + gunicorn (the API and the admin)
#   --target caddy  Caddy with the built web app, serving HTTPS

# --- Build the web app -------------------------------------------------------------
# The web app is the same on every CPU, so build it natively even when making
# images for another architecture (e.g. ARM servers).
FROM --platform=$BUILDPLATFORM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The simulator's Python files are bundled into the web app.
COPY sim/src /app/sim/src
RUN npm run build

# --- Caddy: HTTPS, the web app, and a reverse proxy to Django ------------------------
FROM caddy:2-alpine AS caddy
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=frontend-build /app/frontend/dist /srv

# --- Django ------------------------------------------------------------------------
FROM python:3.13-slim AS web
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    TRAINER_SIM_SRC=/app/sim/src \
    TRAINER_CONTENT_DIR=/app/content \
    DJANGO_STATIC_ROOT=/app/staticfiles
RUN pip install --no-cache-dir "uv>=0.9"
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY sim/src /app/sim/src
COPY content /app/content
COPY deploy/start-web.sh /app/start-web.sh
# /run/checker holds the socket Django uses to reach the lesson checker
# container (docker-compose.yml).
RUN DJANGO_ENV=production DJANGO_SECRET_KEY=only-for-collectstatic python manage.py collectstatic --noinput -v0 \
    && useradd --create-home --uid 1000 trainer \
    && mkdir -p /run/checker && chown trainer:trainer /run/checker
# The git commit, shown by /api/health (CI passes --build-arg APP_VERSION=<sha>).
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION
USER trainer
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"
CMD ["/app/start-web.sh"]
