#!/bin/bash
# RaccoonClaw-OSS Docker Entrypoint
# 确保容器内 OpenClaw CLI 已安装，并初始化 workspaces 和 agents
set -e

DATA_DIR="/app/data"
WORKSPACES_DIR="/home/appuser/.openclaw/workspaces"
SHARED_DIR="/app/shared"
INIT_MARKER="/app/.initialized"

echo "[entrypoint] RaccoonClaw-OSS 启动中..."

# ── 1. 安装/更新 OpenClaw CLI（容器内独立安装，不依赖宿主机）──────────────
if ! command -v openclaw &>/dev/null; then
    echo "[entrypoint] 安装 OpenClaw CLI..."
    pip install --no-cache-dir openclaw
else
    echo "[entrypoint] OpenClaw CLI 已安装: $(openclaw --version 2>/dev/null || echo 'version unknown')"
fi

# ── 2. 如尚未初始化，执行 workspace bootstrap ─────────────────────────────
if [ ! -f "$INIT_MARKER" ]; then
    echo "[entrypoint] 首次启动，执行 workspace 初始化..."

    # 初始化主配置（CLI 配置和 Gateway 配置）
    openclaw init --non-interactive 2>/dev/null || true

    # 初始化 workspace（使用 edict 的 workspace 配置）
    if [ -d "$SHARED_DIR" ]; then
        echo "[entrypoint] 注册 workspaces..."
        python3 -c "
import sys, json, pathlib, shutil, subprocess
ROOT = pathlib.Path('$SHARED_DIR').parent
shared = pathlib.Path('$SHARED_DIR')

# 注册每个 workspace
import os
workspace_ids = [
    'chief_of_staff', 'planning', 'review_control', 'delivery_ops',
    'brand_content', 'business_analysis', 'secops', 'compliance_test',
    'engineering', 'people_ops',
]
for ws_id in workspace_ids:
    ws_dir = pathlib.Path('/home/appuser/.openclaw') / 'workspace' / f'workspace-{ws_id}'
    ws_dir.mkdir(parents=True, exist_ok=True)

    # 复制 shared 文件到 workspace
    for fname in ['incident-playbook.json', 'review-rubric.json',
                  'workbench-modes.json', 'agent-registry.json', 'workflow-config.json']:
        src = shared / fname
        if src.exists():
            dst = ws_dir / fname
            if not dst.exists():
                shutil.copy2(src, dst)
    print(f'  workspace-{ws_id} ready')
"
    fi

    # 加载演示数据（如存在）
    if [ -d "$DATA_DIR" ]; then
        echo "[entrypoint] 加载演示数据..."
        python3 -c "
import pathlib, json, shutil

demo_src = pathlib.Path('$DATA_DIR')
tasks_src = demo_src / 'tasks_source.json'
tasks_dst = pathlib.Path('/home/appuser/.openclaw/workspace/workspace-delivery_ops/data/tasks_source.json')

if tasks_src.exists() and not tasks_dst.exists():
    tasks_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tasks_src, tasks_dst)
    print('  演示任务数据已加载')
"
    fi

    # 写入初始化标记
    echo "initialized at $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$INIT_MARKER"
    echo "[entrypoint] 初始化完成"
else
    echo "[entrypoint] 已初始化，跳过 bootstrap（删除 $INIT_MARKER 可重新初始化）"
fi

# ── 3. 启动后端 ────────────────────────────────────────────────────────────
echo "[entrypoint] 启动后端服务..."
exec python3 Raccoon/backend/run_desktop_backend.py
