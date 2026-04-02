#!/usr/bin/env bash
# check_bind.sh — 检查用户是否已绑定指定邮箱
#
# 用法:
#   bash check_bind.sh --email EMAIL
#
# 输出（stdout JSON）:
#   成功: {"success": true, "data": {"bound": true}, "message": "Success"}
#   失败: {"success": false, "error_code": 3, "message": "具体错误信息"}
#
# Exit Code:
#   0 = 请求成功（不论绑定与否）
#   1 = 请求失败
#
# 注意: Token 由本地代理服务自动注入，无需手动传入

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

do_post "/data/4118/forward" "$BODY" > "$RAW_RESPONSE_FILE"
RAW_RESPONSE=$(cat "$RAW_RESPONSE_FILE")

# 检查HTTP状态
if [[ "$HTTP_STATUS" != "200" ]]; then
  output_error 999 "HTTP请求失败，状态码: ${HTTP_STATUS}"
  exit 1
fi

# 解析并输出结果
parse_gateway_response "$RAW_RESPONSE"
