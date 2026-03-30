# Community edition container image

FROM --platform=${BUILDPLATFORM:-linux/amd64} node:20-bookworm-slim AS frontend-build
WORKDIR /app/edict/frontend
COPY edict/frontend/package.json edict/frontend/package-lock.json ./
RUN npm ci
COPY edict/frontend/ ./
RUN npm run build

FROM --platform=${TARGETPLATFORM:-linux/amd64} python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_DIR=/app \
    OPENCLAW_HOME=/app/.openclaw \
    OPENCLAW_PROJECT_ROOT=/app \
    OPENCLAW_CONFIG_PATH=/app/.openclaw/openclaw.json \
    RACCOONCLAW_DATA_PROFILE=clean \
    RACCOONCLAW_ENABLE_IM_CHANNELS=false \
    RACCOONCLAW_ENABLE_TOOLBOX=false \
    RACCOONCLAW_ENABLE_SCHEDULED_TASKS=true \
    RACCOONCLAW_ENABLE_AUTOMATION_MIRRORS=false \
    HOST=0.0.0.0 \
    PORT=7891

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY edict/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app
COPY --from=frontend-build /app/dashboard/dist /app/dashboard/dist

RUN chmod +x /app/scripts/docker_entrypoint.sh

EXPOSE 7891

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:7891/healthz > /dev/null || exit 1

ENTRYPOINT ["/app/scripts/docker_entrypoint.sh"]
