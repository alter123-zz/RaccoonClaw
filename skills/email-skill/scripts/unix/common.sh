#!/usr/bin/env bash
# common.sh — 邮件skill公共函数库
# 提供统一的HTTP请求发送、JSON解析、响应处理和标准化输出
# Token 由本地代理服务自动注入，无需手动传入

set -euo pipefail

# 远程 API 基础地址（通过 Remote-URL header 传递给本地代理）
REMOTE_BASE_URL="https://jprx.m.qq.com"

# --------------------------------------------------------
# 操作系统检测
# --------------------------------------------------------

# 检测当前操作系统类型，用于后续兼容性处理
detect_os() {
  local uname_out
  uname_out="$(uname -s 2>/dev/null || echo "Unknown")"
  case "$uname_out" in
    Linux*)   echo "linux" ;;
    Darwin*)  echo "macos" ;;
    CYGWIN*|MINGW*|MSYS*|MINGW32*|MINGW64*)  echo "windows" ;;
    *)        echo "unknown" ;;
  esac
}

CURRENT_OS=$(detect_os)
echo "[QClaw] Detected OS: $CURRENT_OS"

# --------------------------------------------------------
# 解析本地代理端口（跨平台兼容）
# --------------------------------------------------------

# 从环境变量 AUTH_GATEWAY_PORT 获取本地代理端口
# 该变量由 Electron 主进程在启动 Auth Gateway 时自动设置，子进程自动继承
# 若环境变量未设置，则回退到默认端口 19000
#
# 兼容性说明：
# - macOS / Linux: 直接使用 bash 的 ${VAR:-default} 语法
# - Windows (Git Bash / MSYS2 / Cygwin): 同上，bash 环境下语法一致
# - Windows (WSL): 需要通过 WSLENV 导出环境变量，或手动设置
#   如果 WSL 中获取不到，尝试从 Windows 侧读取
get_proxy_port() {
  local port="${AUTH_GATEWAY_PORT:-}"

  # 如果环境变量为空，且在 WSL 环境下，尝试从 Windows 注册表或 cmd 获取
  if [[ -z "$port" && "$CURRENT_OS" == "linux" && -f /proc/version ]]; then
    if grep -qi microsoft /proc/version 2>/dev/null; then
      echo "[QClaw] WSL detected, trying to read AUTH_GATEWAY_PORT from Windows environment" >&2
      port=$(cmd.exe /C "echo %AUTH_GATEWAY_PORT%" 2>/dev/null | tr -d '\r' || true)
      # cmd.exe 中未设置的变量会原样返回 %AUTH_GATEWAY_PORT%
      if [[ "$port" == "%AUTH_GATEWAY_PORT%" || -z "$port" ]]; then
        port=""
      fi
    fi
  fi

  # 最终回退到默认端口 19000
  if [[ -z "$port" ]]; then
    port="19000"
    echo "[QClaw] AUTH_GATEWAY_PORT not set, falling back to default port: $port" >&2
  fi

  echo "$port"
}

PROXY_PORT=$(get_proxy_port)
echo "[QClaw] AUTH_GATEWAY_PORT: $PROXY_PORT"
PROXY_BASE_URL="http://localhost:${PROXY_PORT}"

# --------------------------------------------------------
# JSON 解析工具选择：优先 jq，fallback 到 node
# --------------------------------------------------------

# json_extract 从JSON字符串中提取指定路径的值
# 用法: json_extract '{"a":{"b":1}}' '.a.b'
json_extract() {
  local json="$1"
  local path="$2"

  if command -v jq &>/dev/null; then
    echo "$json" | jq -r "$path"
  else
    # fallback: 用 node 解析
    # 将 jq 路径语法 .a.b 转换为 JS 属性访问 ["a"]["b"]
    local node_path
    node_path=$(echo "$path" | node -e "
const p = require('fs').readFileSync('/dev/stdin','utf8').trim();
if (p === '.') { process.stdout.write(''); process.exit(0); }
const parts = p.replace(/^\\./, '').split('.');
process.stdout.write(parts.map(k => '[\"' + k + '\"]').join(''));
")
    echo "$json" | node -e "
const data = JSON.parse(require('fs').readFileSync('/dev/stdin','utf8'));
const val = data${node_path};
if (typeof val === 'boolean') console.log(String(val));
else if (val !== null && val !== undefined && typeof val === 'object') console.log(JSON.stringify(val));
else console.log(val === null || val === undefined ? 'null' : val);
"
  fi
}

# --------------------------------------------------------
# HTTP 请求封装
# --------------------------------------------------------

# do_post 通过本地代理发送POST请求（Token由代理自动注入）
# 参数: $1=远程API路径 $2=请求体JSON
# 返回: 原始响应体（stdout），HTTP状态码（通过全局变量 HTTP_STATUS）
do_post() {
  local path="$1"
  local body="$2"
  local remote_url="${REMOTE_BASE_URL}${path}"

  local tmp_file
  tmp_file=$(mktemp)
  trap "rm -f '$tmp_file'" RETURN

  HTTP_STATUS=$(curl -s -o "$tmp_file" -w "%{http_code}" \
    -X POST "${PROXY_BASE_URL}/proxy/api" \
    -H "Remote-URL: ${remote_url}" \
    -H "Content-Type: application/json" \
    -d "$body")

  cat "$tmp_file"
}

# --------------------------------------------------------
# 响应解析
# --------------------------------------------------------

# parse_gateway_response 解析网关层响应，提取业务层结果
# 输入: 原始网关响应JSON
# 输出: 标准化JSON到stdout
# 返回: 0=业务成功 1=业务失败
parse_gateway_response() {
  local raw_response="$1"

  # 提取网关层 ret
  local ret
  ret=$(json_extract "$raw_response" '.ret')

  if [[ "$ret" != "0" ]]; then
    output_error 999 "网关层错误，ret=${ret}"
    return 1
  fi

  # 提取业务层 common.code 和 common.message
  local biz_code biz_message biz_data
  biz_code=$(json_extract "$raw_response" '.data.resp.common.code')
  biz_message=$(json_extract "$raw_response" '.data.resp.common.message')

  # 尝试提取业务数据（可能不存在）
  biz_data=$(json_extract "$raw_response" '.data.resp.data' 2>/dev/null || echo "null")
  if [[ "$biz_data" == "null" || -z "$biz_data" ]]; then
    biz_data="{}"
  fi

  if [[ "$biz_code" == "0" ]]; then
    output_success "$biz_data" "$biz_message"
    return 0
  else
    output_error "$biz_code" "$biz_message"
    return 1
  fi
}

# --------------------------------------------------------
# 标准化输出
# --------------------------------------------------------

# output_success 输出成功结果
# 参数: $1=data(JSON对象) $2=message
output_success() {
  local data="${1-}"
  local message="${2:-Success}"

  if [[ -z "$data" || "$data" == "null" ]]; then
    data="{}"
  fi

  if command -v jq &>/dev/null; then
    jq -n --argjson data "$data" --arg message "$message" \
      '{"success": true, "data": $data, "message": $message}'
  else
    node -e "
const data = JSON.parse(process.argv[1]);
const result = {success: true, data: data, message: process.argv[2]};
console.log(JSON.stringify(result));
" "$data" "$message"
  fi
}

# output_error 输出错误结果
# 参数: $1=error_code $2=message
output_error() {
  local error_code="${1:-999}"
  local message="${2:-未知错误}"

  if command -v jq &>/dev/null; then
    jq -n --argjson code "$error_code" --arg message "$message" \
      '{"success": false, "error_code": $code, "message": $message}'
  else
    node -e "
const result = {success: false, error_code: parseInt(process.argv[1]), message: process.argv[2]};
console.log(JSON.stringify(result));
" "$error_code" "$message"
  fi
}

# --------------------------------------------------------
# 参数解析辅助
# --------------------------------------------------------

# require_param 检查必填参数
# 参数: $1=参数名 $2=参数值
require_param() {
  local name="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    output_error 1 "缺少必填参数: ${name}"
    exit 1
  fi
}
