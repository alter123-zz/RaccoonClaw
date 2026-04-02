#!/usr/bin/env bash
# send_code.sh — 发送验证码到指定邮箱
#
# 用法:
#   bash send_code.sh --email EMAIL
#
# 输出（stdout JSON）:
#   成功: {"success": true, "data": {}, "message": "验证码已发送"}
#   失败: {"success": false, "error_code": 2, "message": "验证码发送频率限制，请5分钟后重试"}
#
# 注意: 5分钟内只会发送一次验证码，有频率限制
# 注意: Token 由本地代理服务自动注入，无需手动传入
#
# Exit Code:
#   0 = 发送成功
#   1 = 发送失败（频率限制、参数错误等）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

# 解析参数
EMAIL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email)  EMAIL="$2";  shift 2 ;;
    *)        shift ;;
  esac
done

require_param "email" "$EMAIL"

# 构造请求体
BODY=$(printf '{"email": "%s"}' "$EMAIL")

# 发送请求（避免命令替换导致 HTTP_STATUS 丢失）
RAW_RESPONSE_FILE=$(mktemp)
trap 'rm -f "$RAW_RESPONSE_FILE"' EXIT

do_post "/data/4121/forward" "$BODY" > "$RAW_RESPONSE_FILE"
RAW_RESPONSE=$(cat "$RAW_RESPONSE_FILE")

# 检查HTTP状态
if [[ "$HTTP_STATUS" != "200" ]]; then
  output_error 999 "HTTP请求失败，状态码: ${HTTP_STATUS}"
  exit 1
fi

# 解析并输出结果
parse_gateway_response "$RAW_RESPONSE"
