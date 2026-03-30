#!/usr/bin/env bash
# email_gateway.sh — email-skill 统一入口

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EMAIL_SKILL_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAP_SMTP_DIR="$(cd "${EMAIL_SKILL_DIR}/../imap-smtp-email" && pwd 2>/dev/null || true)"

CHECK_BIND_SH="${SCRIPT_DIR}/check_bind.sh"
SEND_CODE_SH="${SCRIPT_DIR}/send_code.sh"
VERIFY_BIND_SH="${SCRIPT_DIR}/verify_bind.sh"
SEND_EMAIL_SH="${SCRIPT_DIR}/send_email.sh"

IMAP_JS="${IMAP_SMTP_DIR}/scripts/imap.js"
SMTP_JS="${IMAP_SMTP_DIR}/scripts/smtp.js"
SETUP_SH="${IMAP_SMTP_DIR}/setup.sh"

PROVIDER=""
REST_ARGS=()

json_error() {
  local message="$1"
  local code="${2:-1}"
  if command -v jq >/dev/null 2>&1; then
    jq -n --arg msg "$message" --argjson code "$code" '{success:false,error_code:$code,message:$msg}'
  else
    node -e "
console.log(JSON.stringify({success: false, error_code: parseInt(process.argv[2]), message: process.argv[1]}));
" "$message" "$code"
  fi
}

print_help() {
  cat <<'EOF'
email_gateway.sh — 统一邮件入口

命令：
  capabilities
      展示所有可用能力、适用场景与配置方式

  send --provider <platform|personal> [参数]
      发送邮件统一命令
      - provider=platform: 走平台公邮服务（调用 send_email.sh）
          必填参数：--email --subject --body
          可选参数：--content_type text（当前仅支持纯文本）
          ⚠️ 收件人必须是用户有登录权限的邮箱（绑定需要验证码校验）
      - provider=personal: 走个人邮箱SMTP（调用 imap-smtp-email/scripts/smtp.js）
          必填参数：--to --subject
          可选参数：--body --cc --bcc --attach --from --html --body-file --html-file --subject-file

  bind-check --email <email>
  bind-send-code --email <email>
  bind-verify --email <email> --code <code>

  setup-personal
      启动个人邮箱 IMAP/SMTP 初始化向导（调用 ../imap-smtp-email/setup.sh）

  inbox-check --provider personal [--limit N] [--mailbox INBOX] [--recent 2h] [--unseen true]
  inbox-search --provider personal [search options]
  inbox-fetch --provider personal <uid> [--mailbox INBOX]
  inbox-download --provider personal <uid> [--mailbox INBOX] [--dir PATH] [--file NAME]
  inbox-mark-read --provider personal <uid...>
  inbox-mark-unread --provider personal <uid...>
  inbox-list-mailboxes --provider personal

说明：
  - 用户可按任务自由选择 provider，不再互斥。
  - platform 适合"免配置、给自己发通知"；personal 适合"给任意人发邮件/收件/检索/附件"。
EOF
}

print_capabilities() {
  cat <<'EOF'
{
  "success": true,
  "entry": "email-skill/scripts/unix/email_gateway.sh",
  "providers": [
    {
      "id": "platform",
      "name": "平台公邮服务",
      "config": "无需SMTP/IMAP配置；首次发送需完成邮箱绑定",
      "abilities": [
        "检查绑定状态",
        "发送验证码并绑定邮箱",
        "发送纯文本邮件"
      ],
      "limitations": [
        "收件人必须是用户有登录权限的邮箱（绑定需要验证码校验）",
        "不支持发送给任意第三方",
        "不支持收件/检索/附件下载",
        "不支持抄送(CC)、密送(BCC)",
        "不支持附件发送"
      ],
      "best_for": [
        "给自己发送通知/报告",
        "自动化提醒推送",
        "不想管理邮箱密码/授权码"
      ]
    },
    {
      "id": "personal",
      "name": "个人邮箱(IMAP/SMTP)",
      "config": "在 imap-smtp-email/.env 配置 IMAP/SMTP 凭据；可通过 setup.sh 向导生成",
      "abilities": [
        "SMTP发送（支持任意收件人、抄送/密送/附件）",
        "IMAP收件、检索、读取详情",
        "下载附件、标记已读/未读、列出文件夹"
      ],
      "limitations": [],
      "best_for": [
        "需要给他人发送邮件",
        "需要读取邮箱内容",
        "需要使用个人发件身份",
        "需要完整IMAP/SMTP能力"
      ]
    }
  ]
}
EOF
}

ensure_personal_ready() {
  if [[ -z "${IMAP_SMTP_DIR}" || ! -d "${IMAP_SMTP_DIR}" ]]; then
    json_error "未找到 imap-smtp-email 目录，无法使用 personal provider" 2
    exit 1
  fi
  if ! command -v node >/dev/null 2>&1; then
    json_error "未检测到 node，无法使用 personal provider" 2
    exit 1
  fi
  if [[ ! -f "${SMTP_JS}" || ! -f "${IMAP_JS}" ]]; then
    json_error "imap-smtp-email 脚本缺失，请检查 scripts/smtp.js 与 scripts/imap.js" 2
    exit 1
  fi
}

parse_provider_and_rest() {
  PROVIDER=""
  REST_ARGS=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --provider)
        PROVIDER="${2:-}"
        shift 2
        ;;
      *)
        REST_ARGS+=("$1")
        shift
        ;;
    esac
  done
}

forward_personal_smtp_send() {
  ensure_personal_ready
  (
    cd "${IMAP_SMTP_DIR}"
    node "${SMTP_JS}" send "$@"
  )
}

forward_personal_imap() {
  local subcommand="$1"
  shift
  ensure_personal_ready
  (
    cd "${IMAP_SMTP_DIR}"
    node "${IMAP_JS}" "${subcommand}" "$@"
  )
}

main() {
  local cmd="${1:-}"
  if [[ -z "$cmd" ]]; then
    print_help
    exit 0
  fi
  shift || true

  case "$cmd" in
    help|-h|--help)
      print_help
      ;;

    capabilities)
      print_capabilities
      ;;

    bind-check)
      bash "${CHECK_BIND_SH}" "$@"
      ;;

    bind-send-code)
      bash "${SEND_CODE_SH}" "$@"
      ;;

    bind-verify)
      bash "${VERIFY_BIND_SH}" "$@"
      ;;

    setup-personal)
      if [[ ! -f "${SETUP_SH}" ]]; then
        json_error "未找到 setup.sh，无法初始化 personal provider" 2
        exit 1
      fi
      (
        cd "${IMAP_SMTP_DIR}"
        bash "${SETUP_SH}"
      )
      ;;

    send)
      parse_provider_and_rest "$@"
      case "$PROVIDER" in
        platform)
          bash "${SEND_EMAIL_SH}" "${REST_ARGS[@]}"
          ;;
        personal)
          forward_personal_smtp_send "${REST_ARGS[@]}"
          ;;
        *)
          json_error "send 命令必须指定 --provider platform|personal" 1
          exit 1
          ;;
      esac
      ;;

    inbox-check)
      parse_provider_and_rest "$@"
      [[ "$PROVIDER" == "personal" ]] || { json_error "inbox-check 仅支持 --provider personal" 1; exit 1; }
      forward_personal_imap check "${REST_ARGS[@]}"
      ;;

    inbox-search)
      parse_provider_and_rest "$@"
      [[ "$PROVIDER" == "personal" ]] || { json_error "inbox-search 仅支持 --provider personal" 1; exit 1; }
      forward_personal_imap search "${REST_ARGS[@]}"
      ;;

    inbox-fetch)
      parse_provider_and_rest "$@"
      [[ "$PROVIDER" == "personal" ]] || { json_error "inbox-fetch 仅支持 --provider personal" 1; exit 1; }
      forward_personal_imap fetch "${REST_ARGS[@]}"
      ;;

    inbox-download)
      parse_provider_and_rest "$@"
      [[ "$PROVIDER" == "personal" ]] || { json_error "inbox-download 仅支持 --provider personal" 1; exit 1; }
      forward_personal_imap download "${REST_ARGS[@]}"
      ;;

    inbox-mark-read)
      parse_provider_and_rest "$@"
      [[ "$PROVIDER" == "personal" ]] || { json_error "inbox-mark-read 仅支持 --provider personal" 1; exit 1; }
      forward_personal_imap mark-read "${REST_ARGS[@]}"
      ;;

    inbox-mark-unread)
      parse_provider_and_rest "$@"
      [[ "$PROVIDER" == "personal" ]] || { json_error "inbox-mark-unread 仅支持 --provider personal" 1; exit 1; }
      forward_personal_imap mark-unread "${REST_ARGS[@]}"
      ;;

    inbox-list-mailboxes)
      parse_provider_and_rest "$@"
      [[ "$PROVIDER" == "personal" ]] || { json_error "inbox-list-mailboxes 仅支持 --provider personal" 1; exit 1; }
      forward_personal_imap list-mailboxes "${REST_ARGS[@]}"
      ;;

    *)
      json_error "未知命令: ${cmd}，可用命令见 --help" 1
      exit 1
      ;;
  esac
}

main "$@"
