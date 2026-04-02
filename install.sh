#!/bin/bash
# RaccoonClaw-OSS bootstrap installer
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
OPENCLAW_CONFIG="$OPENCLAW_HOME/openclaw.json"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CANONICAL_AGENTS=(
  chief_of_staff
  planning
  review_control
  delivery_ops
  brand_content
  business_analysis
  secops
  compliance_test
  engineering
  people_ops
)

banner() {
  echo ""
  echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║         RaccoonClaw-OSS Installer       ║${NC}"
  echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
  echo ""
}

log()   { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }
info()  { echo -e "${BLUE}ℹ️  $1${NC}"; }

check_deps() {
  info "检查 OpenClaw / Python 环境"

  if ! command -v openclaw >/dev/null 2>&1; then
    error "未找到 openclaw CLI。请先安装 OpenClaw。"
    exit 1
  fi
  log "OpenClaw CLI 可用"

  if ! command -v python3 >/dev/null 2>&1; then
    error "未找到 python3"
    exit 1
  fi
  log "Python3: $(python3 --version)"

  if [ ! -f "$OPENCLAW_CONFIG" ]; then
    error "未找到 ${OPENCLAW_CONFIG}。请先运行一次 openclaw 完成初始化。"
    exit 1
  fi
  log "OpenClaw 配置已找到"
}

backup_existing() {
  local backup_dir="$OPENCLAW_HOME/backups/raccoonclaw-oss-install-$(date +%Y%m%d-%H%M%S)"
  local has_existing=false

  for dir in "$OPENCLAW_HOME"/workspace-*/; do
    if [ -d "$dir" ]; then
      has_existing=true
      break
    fi
  done

  if [ "$has_existing" = false ] && [ ! -d "$OPENCLAW_HOME/agents" ]; then
    return
  fi

  info "备份当前 OpenClaw runtime"
  mkdir -p "$backup_dir"

  if [ -f "$OPENCLAW_CONFIG" ]; then
    cp "$OPENCLAW_CONFIG" "$backup_dir/openclaw.json"
  fi

  if [ -d "$OPENCLAW_HOME/agents" ]; then
    cp -R "$OPENCLAW_HOME/agents" "$backup_dir/agents"
  fi

  for dir in "$OPENCLAW_HOME"/workspace-*/; do
    if [ -d "$dir" ]; then
      cp -R "$dir" "$backup_dir/$(basename "$dir")"
    fi
  done

  log "备份已写入 $backup_dir"
}

create_workspaces() {
  info "创建 canonical workspaces"

  for agent in "${CANONICAL_AGENTS[@]}"; do
    local workspace="$OPENCLAW_HOME/workspace-$agent"
    mkdir -p "$workspace/skills"

    if [ -f "$REPO_DIR/agents/$agent/SOUL.md" ]; then
      sed "s|__REPO_DIR__|$REPO_DIR|g" "$REPO_DIR/agents/$agent/SOUL.md" > "$workspace/SOUL.md"
    fi

    cat > "$workspace/AGENTS.md" << 'AGENTS_EOF'
# AGENTS.md

1. 接到任务先确认需求。
2. 输出必须包含：任务ID、结果摘要、证据或文件路径、阻塞项。
3. 需要协作时，经由交付运营部或总裁办调度，不跨部门直接改派。
4. 涉及删除、外发、登录、付费等动作必须显式说明。
AGENTS_EOF

    log "workspace-$agent 已准备"
  done
}

register_agents() {
  info "写入 canonical agent 配置"

  cp "$OPENCLAW_CONFIG" "$OPENCLAW_CONFIG.bak.$(date +%Y%m%d-%H%M%S)"

  REPO_DIR="$REPO_DIR" OPENCLAW_HOME="$OPENCLAW_HOME" python3 << 'PYEOF'
import json
import os
from pathlib import Path

home = Path(os.environ["OPENCLAW_HOME"]).expanduser()
cfg_path = home / "openclaw.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

tools = cfg.setdefault("tools", {})
tools["profile"] = "coding"

commands = cfg.setdefault("commands", {})
commands["ownerDisplay"] = "hash"

agents = [
    {"id": "chief_of_staff", "allowAgents": ["planning"]},
    {"id": "planning", "allowAgents": ["review_control", "delivery_ops"]},
    {"id": "review_control", "allowAgents": ["delivery_ops", "planning"]},
    {"id": "delivery_ops", "allowAgents": ["brand_content", "business_analysis", "secops", "compliance_test", "engineering", "people_ops"]},
    {"id": "brand_content", "allowAgents": ["delivery_ops"]},
    {"id": "business_analysis", "allowAgents": ["delivery_ops"]},
    {"id": "secops", "allowAgents": ["delivery_ops"]},
    {"id": "compliance_test", "allowAgents": ["delivery_ops"]},
    {"id": "engineering", "allowAgents": ["delivery_ops"]},
    {"id": "people_ops", "allowAgents": ["delivery_ops"]},
]

agent_block = cfg.setdefault("agents", {})
current = [item for item in (agent_block.get("list") or []) if isinstance(item, dict)]
current_by_id = {str(item.get("id") or ""): item for item in current}
new_list = []

for agent in agents:
    workspace = str(home / f"workspace-{agent['id']}")
    entry = {
        "id": agent["id"],
        "workspace": workspace,
        "subagents": {"allowAgents": agent["allowAgents"]},
    }
    existing = current_by_id.get(agent["id"], {})
    if isinstance(existing, dict):
      merged = dict(existing)
      merged.update(entry)
      subagents = dict(existing.get("subagents") or {})
      subagents.update(entry["subagents"])
      merged["subagents"] = subagents
      entry = merged
    new_list.append(entry)

cfg["agents"]["list"] = new_list
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"registered {len(new_list)} canonical agents")
PYEOF

  log "canonical agents 已写入 openclaw.json"
}

init_data() {
  info "初始化仓库数据目录"
  mkdir -p "$REPO_DIR/data"

  for file in live_status.json agent_config.json model_change_log.json; do
    if [ ! -f "$REPO_DIR/data/$file" ]; then
      echo '{}' > "$REPO_DIR/data/$file"
    fi
  done
  if [ ! -f "$REPO_DIR/data/pending_model_changes.json" ]; then
    echo '[]' > "$REPO_DIR/data/pending_model_changes.json"
  fi
  if [ ! -f "$REPO_DIR/data/tasks_source.json" ]; then
    echo '[]' > "$REPO_DIR/data/tasks_source.json"
  fi

  log "data/ 已准备"
}

setup_python_env() {
  info "创建 Python 虚拟环境"
  python3 -m venv "$REPO_DIR/.venv-backend"
  "$REPO_DIR/.venv-backend/bin/pip" install --upgrade pip
  "$REPO_DIR/.venv-backend/bin/pip" install -r "$REPO_DIR/Raccoon/backend/requirements.txt"
  log "Python 环境已准备"
}

build_frontend() {
  info "构建前端"

  if ! command -v node >/dev/null 2>&1; then
    warn "未找到 node，跳过前端构建。"
    return
  fi

  if [ ! -f "$REPO_DIR/Raccoon/frontend/package.json" ]; then
    warn "未找到 Raccoon/frontend/package.json，跳过前端构建。"
    return
  fi

  cd "$REPO_DIR/Raccoon/frontend"
  npm install --silent 2>/dev/null || npm install
  npm run build
  cd "$REPO_DIR"

  log "前端构建完成"
}

first_sync() {
  info "执行首次同步"
  cd "$REPO_DIR"
  REPO_DIR="$REPO_DIR" python3 scripts/sync_agent_config.py || warn "sync_agent_config 返回警告"
  python3 scripts/refresh_live_data.py || warn "refresh_live_data 返回警告"
  log "首次同步完成"
}

restart_gateway() {
  info "重启 Gateway"
  if openclaw gateway restart >/dev/null 2>&1; then
    log "Gateway 已重启"
  else
    warn "Gateway 重启失败，请手动执行 openclaw gateway restart"
  fi
}

banner
check_deps
backup_existing
create_workspaces
register_agents
init_data
setup_python_env
build_frontend
first_sync
restart_gateway

echo ""
echo -e "${GREEN}RaccoonClaw-OSS 初始化完成。${NC}"
echo "下一步："
echo "  1. bash scripts/run_single_backend.sh"
echo "  2. 打开 http://127.0.0.1:7891"
echo "  3. 若需持续刷新，另开终端运行 bash scripts/run_loop.sh"
