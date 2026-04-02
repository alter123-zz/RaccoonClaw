---
name: email-skill
description: "统一邮件入口：支持平台公邮服务与个人邮箱(IMAP/SMTP)双通道，用户可按需求自主选择。所有与发信相关的需求，都先经由该SKILL处理路由"
---

# 📧 Email Skill（统一入口）

> 本 Skill 是**统一邮件入口**：
> - 支持 **平台公邮服务（platform）**
> - 支持 **个人邮箱 IMAP/SMTP（personal）**
> - 两种方式**可并存**，由用户根据场景自主选择

---

## 1. 设计目标

`email-skill` 作为统一编排层：

- **统一入口**：通过一个脚本暴露全部邮件能力
- **自由选择**：用户可按任务选择 `platform` 或 `personal`
- **能力透明**：明确展示每种方式的能力边界与配置成本
- **并存兼容**：保留原有公邮流程，同时无缝接入 `imap-smtp-email`
- **跨平台**：同时支持 macOS/Linux（bash）和 Windows（CMD）

---

## 2. 能力总览

### provider = `platform`（平台公邮服务）

**定位**：平台公邮是一个**消息推送通道**，专门用于将内容推送到用户自己的邮箱。它不是一个通用的邮件发送工具。

**特点**：
- 无需配置 SMTP/IMAP 主机与密码，开箱即用
- 通过平台 API 完成绑定与发信
- ⚠️ **核心限制：仅支持给用户自己的邮箱发信**。绑定流程需要用户登录目标邮箱接收验证码，因此收件人只能是用户本人有登录权限的邮箱，无法发送给他人
- 适合场景：**消息推送类需求**，例如：
  - "帮我把今天的天气预报发到我邮箱"
  - "把这份分析报告推送给我"
  - "每日汇总发送到我的邮箱"
  - "把这段内容发给我自己留存"

**能力**：
- 检查邮箱是否已绑定
- 发送验证码到目标邮箱（用户需登录该邮箱查看验证码）
- 验证码校验并绑定邮箱
- 发送纯文本邮件到已绑定的用户自有邮箱

**不支持**：
- ❌ **不能发送邮件给他人**（不能发给同事、客户或任何第三方）
- ❌ **不支持 HTML 邮件**（当前公邮能力仅开放纯文本邮件，`content_type` 必须为 `text`）
- ❌ 不支持收件/检索/附件下载
- ❌ 不支持抄送（CC）、密送（BCC）
- ❌ 不支持附件发送

> 💡 **简单判断**：如果用户的需求是"把某些内容发到我自己的邮箱"，公邮适合；如果需求涉及"发给别人"，则不适合，应使用 `personal`。

### provider = `personal`（个人邮箱 IMAP/SMTP）

**特点**：
- 使用个人邮箱凭据（`.env` 配置 IMAP/SMTP 授权码）
- 可以发送邮件给**任意收件人**，不受绑定限制
- 支持完整的邮箱管理能力：收件、检索、下载附件、标记已读/未读
- 适合场景：需要给他人发邮件、需要收件管理、需要完整邮箱操作能力

**能力**：
- SMTP 发信（支持任意收件人、抄送、密送、附件）
- IMAP 收信/检索/读取详情
- 附件下载、邮件状态管理、邮箱文件夹枚举

---

## 3. 如何选择 provider（Agent 决策指引）

> ⚠️ 本节内容供 Agent 理解和引导用户，不是一个可执行的命令。

Agent 应根据用户的实际需求，通过对话理解意图后，引导用户选择合适的 provider。**在用户选择使用公邮之前，Agent 必须向用户清晰说明公邮的能力边界，由用户自行判断是否适合，再决定是否使用。**

### 公邮能力边界说明（Agent 应主动告知用户）

使用公邮前，Agent 应向用户传达以下关键信息：

1. **公邮仅支持给自己发信**：收件人只能是用户本人有登录权限的邮箱，无法发送给任何他人
2. **公邮本质是消息推送**：适合将内容（天气、报告、汇总等）推送到用户自己的邮箱，不是通用邮件工具
3. **由用户决定是否使用**：Agent 应说明上述限制后，让用户自行判断公邮是否满足需求

**能力对比**：

| 维度 | platform（公邮） | personal（个人邮箱） |
|------|-----------------|-------------------|
| 配置成本 | 零配置，开箱即用 | 需配置 IMAP/SMTP 凭据 |
| 收件人范围 | **仅限用户自己的邮箱** | 任意收件人 |
| 典型用途 | 消息推送（天气/报告/提醒→自己） | 邮件沟通（发给同事/客户/任何人） |
| 发件身份 | 平台统一发件人 | 用户个人邮箱地址 |
| 收件能力 | ❌ 不支持 | ✅ 支持 |
| 附件发送 | ❌ 不支持 | ✅ 支持 |
| 抄送/密送 | ❌ 不支持 | ✅ 支持 |
| 附件下载 | ❌ 不支持 | ✅ 支持 |

**用户意图信号 → 推荐 provider**：

- 用户说"把天气/新闻/报告推送到我邮箱" → `platform`（典型消息推送场景）
- 用户说"把这段内容发给我自己" → `platform`
- 用户说"发邮件给某个同事/客户" → `personal`（公邮无法发给他人）
- 用户说"查看/检索/读取邮件" → `personal`
- 用户说"下载邮件附件" → `personal`
- 用户说"不想配置任何东西" → 可推荐 `platform`，但**必须先告知仅能发给自己**，由用户确认
- 用户说"需要抄送/密送" → `personal`
- 用户说"需要带附件发送" → `personal`
- 用户说"发送 HTML 格式邮件" → `personal`（公邮仅支持纯文本）

> 📌 **Agent 行为准则**：当用户的发信需求可能适合公邮时，Agent 不应直接替用户做决定，而应先说明"公邮仅支持给您自己的邮箱发信，主要用于消息推送"，让用户确认后再执行。

---

## 4. 统一入口脚本

**macOS / Linux**：`scripts/unix/email_gateway.sh`
**Windows**：`scripts\windows\email_gateway.cmd`

### 4.1 查看能力

**macOS / Linux：**
```bash
bash scripts/unix/email_gateway.sh capabilities
```

**Windows CMD：**
```cmd
scripts\windows\email_gateway.cmd capabilities
```

### 4.2 发送邮件（统一 send 命令）

#### 使用平台公邮

**macOS / Linux：**
```bash
bash scripts/unix/email_gateway.sh send \
  --provider platform \
  --email "user@example.com" \
  --subject "日报" \
  --body "今日汇总：项目A完成80%，项目B已提测。" \
  --content_type "text"
```

**Windows CMD：**
```cmd
scripts\windows\email_gateway.cmd send --provider platform --email "user@example.com" --subject "日报" --body "今日汇总：项目A完成80%，项目B已提测。" --content_type "text"
```

#### 使用个人邮箱 SMTP

**macOS / Linux：**
```bash
bash scripts/unix/email_gateway.sh send \
  --provider personal \
  --to "user@example.com" \
  --subject "日报" \
  --body "今日汇总"
```

**Windows CMD：**
```cmd
scripts\windows\email_gateway.cmd send --provider personal --to "user@example.com" --subject "日报" --body "今日汇总"
```

### 4.3 平台公邮绑定流程

> ⚠️ **流程约束**：Agent 使用公邮发信前，**必须先执行 `bind-check` 检查绑定状态**。若返回结果表明邮箱已绑定，则**直接执行发信**，无需再走验证码流程。仅当邮箱**未绑定**时，才需要执行步骤 2（发送验证码）和步骤 3（验证绑定）。

**macOS / Linux：**
```bash
# 1) 检查绑定（必须先执行）
bash scripts/unix/email_gateway.sh bind-check --email "user@example.com"
# → 若已绑定：直接跳到 4.2 发送邮件，无需步骤 2、3
# → 若未绑定：继续执行步骤 2、3

# 2) 发送验证码（仅未绑定时执行，用户需登录该邮箱查看验证码）
bash scripts/unix/email_gateway.sh bind-send-code --email "user@example.com"

# 3) 验证绑定（仅未绑定时执行）
bash scripts/unix/email_gateway.sh bind-verify --email "user@example.com" --code "123456"
```

**Windows CMD：**
```cmd
REM 1) 检查绑定（必须先执行）
scripts\windows\email_gateway.cmd bind-check --email "user@example.com"
REM → 若已绑定：直接跳到 4.2 发送邮件，无需步骤 2、3
REM → 若未绑定：继续执行步骤 2、3

REM 2) 发送验证码（仅未绑定时执行，用户需登录该邮箱查看验证码）
scripts\windows\email_gateway.cmd bind-send-code --email "user@example.com"

REM 3) 验证绑定（仅未绑定时执行）
scripts\windows\email_gateway.cmd bind-verify --email "user@example.com" --code "123456"
```

### 4.4 个人邮箱能力（收件/检索/附件）

**macOS / Linux：**
```bash
# 检查邮件
bash scripts/unix/email_gateway.sh inbox-check --provider personal --limit 10 --recent 2h

# 搜索邮件
bash scripts/unix/email_gateway.sh inbox-search --provider personal --subject "发票" --unseen

# 拉取邮件详情
bash scripts/unix/email_gateway.sh inbox-fetch --provider personal 12345

# 下载附件
bash scripts/unix/email_gateway.sh inbox-download --provider personal 12345 --dir ~/Downloads
```

**Windows CMD：**
```cmd
REM 检查邮件
scripts\windows\email_gateway.cmd inbox-check --provider personal --limit 10 --recent 2h

REM 搜索邮件
scripts\windows\email_gateway.cmd inbox-search --provider personal --subject "发票" --unseen

REM 拉取邮件详情
scripts\windows\email_gateway.cmd inbox-fetch --provider personal 12345

REM 下载附件
scripts\windows\email_gateway.cmd inbox-download --provider personal 12345 --dir %USERPROFILE%\Downloads
```

---

## 5. 配置方式

### 5.1 平台公邮（platform）

- 无需 SMTP/IMAP 配置
- 需保证本地代理可用（脚本会通过代理转发平台 API）
- 首次发送前需执行 `bind-check` 检查绑定状态：已绑定可直接发信，未绑定时按绑定流程完成邮箱绑定（用户必须能登录目标邮箱以接收验证码）

### 5.2 个人邮箱（personal）

1) 进入 `imap-smtp-email` 目录
2) 安装依赖：`npm install`
3) 初始化配置：

**macOS / Linux：**
```bash
bash scripts/unix/email_gateway.sh setup-personal
```

**Windows CMD：**
```cmd
scripts\windows\email_gateway.cmd setup-personal
```

该向导会生成 `imap-smtp-email/.env`，包含 IMAP/SMTP 主机、账号、授权码等配置。

---

## 6. 目录结构

```text
email-skill/
├── SKILL.md
└── scripts/
    ├── unix/                         # macOS / Linux 脚本
    │   ├── email_gateway.sh          # 统一入口
    │   ├── common.sh                 # 公共函数库
    │   ├── check_bind.sh             # platform: 检查绑定
    │   ├── send_code.sh              # platform: 发送验证码
    │   ├── verify_bind.sh            # platform: 校验绑定
    │   └── send_email.sh             # platform: 发送邮件
    └── windows/                      # Windows CMD 脚本
        ├── email_gateway.cmd         # 统一入口
        ├── common.cmd                # 公共函数库
        ├── check_bind.cmd            # platform: 检查绑定
        ├── send_code.cmd             # platform: 发送验证码
        ├── verify_bind.cmd           # platform: 校验绑定
        └── send_email.cmd            # platform: 发送邮件

imap-smtp-email/
├── SKILL.md
├── setup.sh
└── scripts/
    ├── imap.js                       # personal: 收件/检索/附件
    └── smtp.js                       # personal: 发件
```

---

## 7. 兼容与约束

- 统一入口不修改 `imap-smtp-email` 的既有行为，只做路由与编排
- `provider=personal` 需要本机可用 `node`，并完成 `.env` 配置
- `provider=platform` 发送前必须先执行 `bind-check` 确认绑定状态：**已绑定则直接发信，未绑定才需要执行发送验证码（`bind-send-code`）并绑定（`bind-verify`）的流程**
- 所有脚本依赖 `node` 和 `curl`（Windows 10+ 自带 curl）
- macOS/Linux 脚本优先使用 `jq`，不可用时 fallback 到 `node`

### 定时发信任务前置要求

> ⚠️ **提前完成邮箱绑定**：若用户需要设置定时发信任务（如每日定时推送天气、周报汇总等）并使用 `platform` 公邮进行推送，Agent 必须在创建定时任务**之前**引导用户完成邮箱验证与绑定流程（bind-check → bind-send-code → bind-verify）。因为定时任务执行时用户不在场，无法实时完成验证码交互，若邮箱未提前绑定，定时任务将无法正常发信。

### 异常兜底策略

> ⚠️ **公邮发信余量不足自动切换**：使用 `platform` 公邮发信时（包括发送验证码和正式邮件），若接口返回 **"公共域名已达日发送上限"** 或其他表示发信余量不足的错误，说明当日平台公邮额度已耗尽。此时 Agent 应**自动切换至 `personal`（个人邮箱 SMTP）模式**帮助用户继续完成发信，无需用户手动干预。切换前应向用户简要说明原因（如"公邮今日额度已用完，已自动切换到个人邮箱为您发送"）。若 `personal` 模式尚未配置，Agent 应引导用户完成 `setup-personal` 配置后再发送。

### 邮件编码规范

> ⚠️ **优先使用 UTF-8 编码**：公邮发送邮件时（使用 `platform`），邮件主题和正文内容应优先使用 UTF-8 编码。

