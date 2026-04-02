#!/usr/bin/env bash
# send_email.sh — 发送邮件到指定邮箱
#
# 用法:
#   bash send_email.sh --email EMAIL --subject SUBJECT --body BODY [--content_type text]
#
# 参数:
#   --email         必填，目标邮箱地址（必须已绑定）
#   --subject       必填，邮件主题
#   --body          必填，邮件正文（仅支持纯文本）
#   --content_type  可选，内容类型，默认 "text"（当前公邮仅支持纯文本）
#
# 输出（stdout JSON）:
#   成功: {"success": true, "data": {}, "message": "邮件发送成功"}
#   失败: {"success": false, "error_code": 3, "message": "邮箱未绑定，请先绑定"}
#
# Exit Code:
#   0 = 发送成功
#   1 = 发送失败（未绑定、SMTP失败、额度限制等）
#
# 注意: Token 由本地代理服务自动注入，无需手动传入

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

# 解析参数
EMAIL=""
SUBJECT=""
BODY=""
CONTENT_TYPE="text"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email)         EMAIL="$2";        shift 2 ;;
    --subject)       SUBJECT="$2";      shift 2 ;;
    --body)          BODY="$2";         shift 2 ;;
    --content_type)  CONTENT_TYPE="$2"; shift 2 ;;
    *)               shift ;;
  esac
done

require_param "email"   "$EMAIL"
require_param "subject" "$SUBJECT"
require_param "body"    "$BODY"

# 构造请求体（使用 node 确保 JSON 转义正确，避免 body 中的特殊字符问题）
REQUEST_BODY=$(node -e "
console.log(JSON.stringify({
    email: process.argv[1],
    subject: process.argv[2],
    body: process.argv[3],
    content_type: process.argv[4]
}));
" "$EMAIL" "$SUBJECT" "$BODY" "$CONTENT_TYPE")

# 发送请求（避免命令替换导致 HTTP_STATUS 丢失）
RAW_RESPONSE_FILE=$(mktemp)
trap 'rm -f "$RAW_RESPONSE_FILE"' EXIT

do_post "/data/4123/forward" "$REQUEST_BODY" > "$RAW_RESPONSE_FILE"
RAW_RESPONSE=$(cat "$RAW_RESPONSE_FILE")

# 检查HTTP状态
if [[ "$HTTP_STATUS" != "200" ]]; then
  output_error 999 "HTTP请求失败，状态码: ${HTTP_STATUS}"
  exit 1
fi

# 解析并输出结果
parse_gateway_response "$RAW_RESPONSE"
