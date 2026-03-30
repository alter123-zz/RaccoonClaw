#!/usr/bin/env bash
# verify_bind.sh — 校验验证码并绑定邮箱
#
# 用法:
#   bash verify_bind.sh --email EMAIL --code CODE
#
# 输出（stdout JSON）:
#   成功: {"success": true, "data": {}, "message": "邮箱绑定成功"}
#   失败: {"success": false, "error_code": 3, "message": "验证码错误"}
#
# Exit Code:
#   0 = 绑定成功
#   1 = 绑定失败（验证码错误、已绑定等）
#
# 注意: Token 由本地代理服务自动注入，无需手动传入

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

# 解析参数
EMAIL=""
CODE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email)  EMAIL="$2";  shift 2 ;;
    --code)   CODE="$2";   shift 2 ;;
    *)        shift ;;
  esac
done

require_param "email" "$EMAIL"
require_param "code"  "$CODE"

# 构造请求体
BODY=$(printf '{"email": "%s", "code": "%s"}' "$EMAIL" "$CODE")

# 发送请求（避免命令替换导致 HTTP_STATUS 丢失）
RAW_RESPONSE_FILE=$(mktemp)
trap 'rm -f "$RAW_RESPONSE_FILE"' EXIT

do_post "/data/4122/forward" "$BODY" > "$RAW_RESPONSE_FILE"
RAW_RESPONSE=$(cat "$RAW_RESPONSE_FILE")

# 检查HTTP状态
if [[ "$HTTP_STATUS" != "200" ]]; then
  output_error 999 "HTTP请求失败，状态码: ${HTTP_STATUS}"
  exit 1
fi

# 解析并输出结果
parse_gateway_response "$RAW_RESPONSE"
