# RaccoonClaw-OSS
# 构建: docker build -t raccoonclaw .
# 运行: docker compose up
# 访问: http://localhost:7891
# 特点: 零依赖宿主机，容器内自带 OpenClaw CLI + 自动初始化

# Stage 1: 构建 React 前端
FROM --platform=${BUILDPLATFORM:-linux/amd64} node:20-alpine AS frontend-build
WORKDIR /build
COPY Raccoon/frontend/package.json Raccoon/frontend/package-lock.json ./
RUN npm ci --silent
COPY Raccoon/frontend/ ./
RUN npx vite build --outDir /build/dist

# Stage 2: Python 后端（零依赖宿主机）
FROM --platform=${TARGETPLATFORM:-linux/amd64} python:3.11-slim

WORKDIR /app

# 安装系统依赖 + playwright 浏览器（供测试/爬虫用）
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget curl git \
        libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
        libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
        libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && rm -rf /var/cache/apt/archives

# 安装 OpenClaw CLI（容器内独立，不依赖宿主机）
RUN pip install --no-cache-dir openclaw playwright \
    && playwright install chromium --with-deps

# 安装 Python 依赖
COPY Raccoon/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY agents/ ./agents/
COPY dashboard/ ./dashboard/
COPY scripts/ ./scripts/
COPY shared/ ./shared/
COPY skills/ ./skills/
COPY Raccoon/backend/ ./Raccoon/backend/
COPY install.sh ./

# 复制前端构建产物
COPY --from=frontend-build /build/dist ./dashboard/dist/

# 复制演示数据
COPY docker/demo_data/ ./data/

# 复制 entrypoint 脚本
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 初始化标记文件目录
RUN mkdir -p /app/.initialized

# 非 root 用户运行
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 7891

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7891/api/healthz')" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
