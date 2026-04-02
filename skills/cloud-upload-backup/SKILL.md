---
name: cloud-upload-backup
description: |
  Cloud file upload and backup tool. Upload local files to Tencent SMH cloud storage, viewable in QClaw Mini Program.
  Use cases:
  - User says "上传文件", "上传某个文件", "确定上传" (upload file, upload a specific file, confirm upload)
  - User says "备份到云", "备份文件", "保存到云", "保存某文件到云" (back up to cloud, backup file, save to cloud)
  - User says "传到云空间", "上传到云空间" (transfer to cloud space, upload to cloud space)
  - User says "把文件发给我", "整理好发我", "发到手机", "传到手机" (send the file to me, send to my phone)
  - User says "打包并上传到cos", "上传到cos", "传到cos" (package and upload to COS, upload to COS)
  - User says "做完了发我一份", "弄好了发给我", "完成后把文件给我" (send me when done, give me the file after completion)
  - User says "导出之后发我", "生成完发给我看看", "跑完了把结果给我" (send after export, give me the result when finished)
  - User says "这个云文件还在吗", "之前上传的文件还能下吗" (is this cloud file still there, can I still download)
  - When QClaw needs to upload files and send them to the user's phone
  - When a task output (report, export, generated file) needs to be delivered to the user's mobile device
  - When the user's intent implies needing a file on another device but doesn't explicitly say "upload"
metadata:
  openclaw:
    emoji: "☁️"
    requires:
      bins:
        - curl
---

# 云文件上传备份工具 (Tencent SMH)

将本地文件上传至腾讯 SMH 云存储，上传后可在 QClaw 小程序中查看。使用 `@tencent/smh-js-sdk` 官方 SDK。

## Setup

无需额外安装依赖。文件上传通过本地 HTTP 接口 `/proxy/qclaw-cos` 完成，SMH 凭证由主进程自动管理，无需手动配置。

---

## Workflow

QClaw uses this skill in any scenario that requires uploading files to the cloud. **文件上传流程已简化为直接传输。**

### Complete flow

```
User triggers file upload
  → Step 1: Identify the local file path(s)
  → Step 2: Upload via `upload` command (loop for batch)
  → Step 3: Output the `message` field from JSON response VERBATIM — do NOT construct your own text
```

> **CRITICAL — Anti-hallucination design**: The upload API returns a pre-rendered `message` field containing the complete user-facing text (file name, size, file link, notice). **QClaw MUST output `message` verbatim.** QClaw does NOT need to extract `downloadUrl` or any other field to compose its own reply — the server has already done that. This eliminates the possibility of LLM hallucinating or incorrectly assembling URL fragments.

### Step 2: Upload

See **Commands** section below for detailed usage.

> **IMPORTANT**: 默认必须使用 `conflictStrategy: "ask"` 上传。这样当云端已存在同名文件时，接口会返回错误，QClaw 可以询问用户如何处理。**只有用户明确说了 "覆盖"/"替换" 或 "重命名" 时，才使用对应的 `conflictStrategy: "overwrite"` 或 `conflictStrategy: "rename"`。**

**Single file (默认):**

```bash
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/upload \
  -H 'Content-Type: application/json' \
  -d '{"localPath":"/path/to/file.pdf","conflictStrategy":"ask"}'
```

**Upload to specific directory:**

```bash
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/upload \
  -H 'Content-Type: application/json' \
  -d '{"localPath":"/path/to/photo.jpg","remotePath":"photos/photo.jpg","conflictStrategy":"ask"}'
```

**User explicitly requested overwrite:**

```bash
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/upload \
  -H 'Content-Type: application/json' \
  -d '{"localPath":"/path/to/report.pdf","conflictStrategy":"overwrite"}'
```

**User explicitly requested rename:**

```bash
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/upload \
  -H 'Content-Type: application/json' \
  -d '{"localPath":"/path/to/report.pdf","conflictStrategy":"rename"}'
```

**Batch upload (multiple files — use `batch-upload` endpoint):**

When the user wants to upload multiple files (e.g., "把这三个文件都发给我"), use the `batch-upload` endpoint. This returns a **single `message` field** containing the complete summary of all uploads — QClaw outputs it verbatim, no assembly needed.

```bash
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/batch-upload \
  -H 'Content-Type: application/json' \
  -d '{"files":[{"localPath":"/path/to/file1.pdf","conflictStrategy":"ask"},{"localPath":"/path/to/file2.docx","conflictStrategy":"ask"},{"localPath":"/path/to/file3.jpg","conflictStrategy":"ask"}]}'
```

> **IMPORTANT**: For **2+ files**, always prefer `batch-upload` over multiple `upload` calls. The `batch-upload` endpoint returns a single pre-rendered `message` with all results summarized, eliminating the need for QClaw to combine multiple responses.

#### Conflict handling

When using `conflictStrategy: "ask"` (默认), if a same-name file already exists, the upload will fail with an error. QClaw must then ask the user:

**QClaw conflict dialogue** (upload returns `success: false` due to same-name conflict):

> 已存在同名文件 `{filename}`，你想怎么处理？
>
> 1. 🔄 覆盖 — 替换已有文件
> 2. 📝 重命名 — 自动改名上传（如 file(1).pdf）
> 3. ❌ 取消 — 不上传

Then re-run upload with the user's chosen strategy (`conflictStrategy: "overwrite"` or `conflictStrategy: "rename"`).

**三种策略对照：**

| Strategy | Behavior | When to use |
|----------|----------|-------------|
| `ask` (**默认，必须使用**) | 同名文件存在时返回错误，QClaw 询问用户 | 用户未表明偏好时 |
| `overwrite` | 直接覆盖已有文件 | 用户明确说 "覆盖", "替换", "更新文件" |
| `rename` | 自动重命名 → `file(1).pdf` | 用户明确说 "重命名", "改名上传" |

### Step 3: Output `message` field — VERBATIM, NO modification (CRITICAL)

上传接口返回 JSON 后，**必须原样输出** `message` 字段的值作为回复内容。

**正确做法**：直接从 JSON 输出中提取 `message` 字段值，**一字不改**地展示给用户：
```
JSON 返回: {"success": true, "message": "链接已生成，可在 QClaw 小程序中随时查看。（保留 30 天后自动清理）\n\n已上传文件: report.pdf (2.3 MB)\n文件链接: https://jsonproxy.3g.qq.com/urlmapper/aB3xYz", ...}

QClaw 直接输出 message 的内容:
链接已生成，可在 QClaw 小程序中随时查看。（保留 30 天后自动清理）

已上传文件: report.pdf (2.3 MB)
文件链接: https://jsonproxy.3g.qq.com/urlmapper/aB3xYz
```

**错误做法**（严格禁止）：
```
❌ 忽略 message 字段，自己从 downloadUrl/fileInfo 等字段拼接内容
❌ 自己拼接 URL 片段（如把 host + rawDownloadUrl 的 path 拼在一起）
❌ 把 rawDownloadUrl 中的 hash/path 部分接到短链域名后面
❌ 对 message 中的 URL 做任何截断、修改、重组
❌ 自创文件链接文本格式（如改变 message 中的排版）
```

**批量上传时**，使用 `batch-upload` 接口，服务端返回的 `message` 已包含完整汇总，直接输出即可。

> **为什么这样设计**：`message` 由服务端生成，其中的文件链接是从 API 返回中精确提取的。让 AI 直接输出预渲染文本，而不是从 JSON 中提取字段自行拼接，从根本上消除了 AI 混淆 URL 片段导致幻觉的可能性。单文件用 `upload`，多文件用 `batch-upload`——两种场景都只需原样输出 `message`。

### When to use each command

| User intent | Command | What to do with the result |
|-------------|---------|---------------------------|
| 上传**单个**文件 | `upload` | Output `message` field verbatim |
| 上传**多个**文件（2个及以上） | `batch-upload` | Output `message` field verbatim |
| "这个云文件还在吗" / "查看文件信息" | `info` | Show file metadata to user |
| "云上有哪些文件" / "列出备份文件" | `list` | Show file list to user |

> **Key**: Single file → `upload`, multiple files → `batch-upload`. Both return a pre-rendered `message` field — QClaw just outputs it verbatim. QClaw never constructs its own response text from individual JSON fields.

---

## File Size Support

**There is NO file size limit.** The upload script supports files of any size, including multi-GB videos.

- **Small files (≤ 50 MB)**: Read into memory for fast upload.
- **Large files (> 50 MB)**: Use disk-backed lazy reading — the file is **never loaded entirely into memory**. The SDK reads it in 5 MB chunks (multipart upload), so even 10 GB+ files work smoothly.

> **IMPORTANT for QClaw**: Do NOT tell the user there is a file size limit (e.g. "2GB limit"). There is none. If the user wants to upload a large file, just proceed with the upload command normally. The script handles large files automatically via chunked/multipart upload.

---

## PORT 获取方式

所有 HTTP 请求中的 `PORT` 从环境变量 `AUTH_GATEWAY_PORT` 获取，该变量由 Electron 主进程在启动 Auth Gateway 时自动设置，子进程会自动继承。

**macOS / Linux (bash):**

```bash
PORT=${AUTH_GATEWAY_PORT:-19000}
echo "[QClaw] AUTH_GATEWAY_PORT: $PORT"
```

**Windows (PowerShell):**

```powershell
$PORT = if ($env:AUTH_GATEWAY_PORT) { $env:AUTH_GATEWAY_PORT } else { "19000" }
Write-Host "[QClaw] AUTH_GATEWAY_PORT: $PORT"
```

**Windows (CMD):**

```cmd
if not defined AUTH_GATEWAY_PORT set AUTH_GATEWAY_PORT=19000
set PORT=%AUTH_GATEWAY_PORT%
echo [QClaw] AUTH_GATEWAY_PORT: %PORT%
```

> **说明**：`AUTH_GATEWAY_PORT` 环境变量由 Electron 主进程自动注入，子进程（包括 OpenClaw）启动时自动继承。若环境变量未设置，则回退到默认端口 `19000`。此方式无需依赖 `python`，跨平台兼容且更轻量。

## 父进程 ID 获取方式

在执行 curl 命令前，获取当前进程的父进程 ID 并打印到控制台。

**macOS / Linux (bash):**

```bash
PPID_VAL=$(python3 -c "import os; print(os.getppid())")
echo "[QClaw] Parent PID: $PPID_VAL"
```

**Windows (PowerShell):**

```powershell
$PPID_VAL = python -c "import os; print(os.getppid())"
Write-Host "[QClaw] Parent PID: $PPID_VAL"
```

> **说明**：使用 `python/python3` 的 `os.getppid()` 获取父进程 ID，跨平台兼容（macOS/Linux/Windows 均支持）。打印格式为 `[QClaw] Parent PID: <ppid>`，便于日志追踪。

---

## Commands

### upload

Upload a local file directly by specifying its path.

```
POST /proxy/qclaw-cos/upload
Content-Type: application/json

{
  "localPath": "<local-file-path>",       // 必填：本地文件绝对路径
  "remotePath": "<cloud-path>",           // 可选：云端目标路径，省略则上传到根目录并保留原文件名
  "conflictStrategy": "ask|rename|overwrite"  // 可选：同名冲突策略，默认 ask
}
```

**Body 参数：**
- `localPath`（必填）：本地文件的绝对路径，支持 `~` 展开
- `remotePath`（可选）：云端目标路径。省略则上传到**根目录**并保留原文件名
- `conflictStrategy`（可选）：同名冲突处理策略：
  - `ask` (**QClaw 必须默认使用**) — 同名文件存在时返回错误，QClaw 询问用户处理方式
  - `rename` — 自动重命名新文件（如 `file(1).pdf`）
  - `overwrite` — 静默覆盖已有文件

**Examples:**

```bash
# macOS / Linux: 获取 PORT 和父进程 ID
PORT=${AUTH_GATEWAY_PORT:-19000}
echo "[QClaw] AUTH_GATEWAY_PORT: $PORT"
PPID_VAL=$(python3 -c "import os; print(os.getppid())")
echo "[QClaw] Parent PID: $PPID_VAL"

# Upload a file (QClaw 默认应使用 conflictStrategy: ask)
curl -s -X POST http://localhost:$PORT/proxy/qclaw-cos/upload \
  -H 'Content-Type: application/json' \
  -d '{"localPath":"/path/to/report.pdf","conflictStrategy":"ask"}'

# Upload to a specific path
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/upload \
  -H 'Content-Type: application/json' \
  -d '{"localPath":"/path/to/photo.jpg","remotePath":"photos/vacation.jpg","conflictStrategy":"ask"}'

# Upload a video
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/upload \
  -H 'Content-Type: application/json' \
  -d '{"localPath":"/path/to/clip.mp4","conflictStrategy":"ask"}'

# Upload and overwrite if same name exists (user explicitly requested)
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/upload \
  -H 'Content-Type: application/json' \
  -d '{"localPath":"/path/to/report.pdf","conflictStrategy":"overwrite"}'

# Upload with rename (user explicitly requested)
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/upload \
  -H 'Content-Type: application/json' \
  -d '{"localPath":"/path/to/report.pdf","conflictStrategy":"rename"}'
```

**Output (JSON):**

When upload **succeeds**:

```json
{
  "success": true,
  "message": "链接已生成，可在 QClaw 小程序中随时查看。（保留 30 天后自动清理）\n\n已上传文件: photo.jpg (2.0 MB)\n文件链接: https://jsonproxy.3g.qq.com/urlmapper/aB3xYz",
  "upload": {
    "localFile": "/path/to/photo.jpg",
    "remotePath": "photo.jpg",
    "fileSize": 2048576,
    "fileSizeHuman": "2.0 MB",
    "uploadTime": "3.2s",
    "rapidUpload": false
  },
  "downloadUrl": "https://jsonproxy.3g.qq.com/urlmapper/aB3xYz",
  "fileInfo": {
    "name": "photo.jpg",
    "size": 2048576,
    "sizeHuman": "2.0 MB",
    "type": "image/jpeg",
    "creationTime": "2026-03-13T10:00:00Z",
    "modificationTime": "2026-03-13T10:00:00Z",
    "previewUrl": "https://..."
  }
}
```

> **CRITICAL — `message` field (Anti-hallucination)**: The `message` field contains the **complete, pre-rendered text** that QClaw should output to the user. It already includes the file name, size, file link, and the standard notice. **QClaw MUST output `message` verbatim** — do NOT ignore it and try to compose your own reply from `downloadUrl`, `fileInfo`, or other fields.
>
> This design eliminates the need for the AI to extract and assemble information from multiple JSON fields, preventing URL hallucination (confusing short URL prefixes with long COS URL hash fragments).

When upload **fails**:

```json
{
  "success": false,
  "message": "❌ 文件上传失败：上传失败: 文件不存在: /path/to/missing.pdf\n\n你可以：\n1. 🔄 重试 — 重新上传这个文件\n2. ❌ 取消 — 暂时不上传",
  "error": "上传失败: 文件不存在: /path/to/missing.pdf"
}
```

> **Note**: Even for error cases, the `message` field contains the pre-rendered error text with user-facing options. QClaw should output it verbatim.

> **Note**: After upload, the script automatically converts the COS file URL to a short URL via the JPRX short link service (`data/4096/forward`). The short URL format is `https://jsonproxy.3g.qq.com/urlmapper/xxx`。手机端点击短链拉起 QClaw 小程序（文件保留 30 天），PC 端点击短链打开 H5 扫码页，用户微信扫码后跳转小程序查看文件。
>
> **Anti-hallucination design**: The `message` field is the **single source of truth** for QClaw's reply. The server pre-renders the complete response text with the correct file URL already embedded. This means there is **zero chance** of the AI constructing an incorrect URL, because the AI never needs to touch any URL — it just outputs the pre-rendered `message`. The `rawDownloadUrl` field only appears when short URL generation fails (as a fallback). Full URLs are logged server-side for debugging.

### batch-upload

Upload multiple local files in one request. Returns a **single pre-rendered `message`** with the complete summary of all uploads.

> **When to use**: Whenever the user wants to upload **2 or more** files. Prefer `batch-upload` over multiple `upload` calls — it produces a single `message` that QClaw outputs verbatim, eliminating the need to assemble multiple responses.

```
POST /proxy/qclaw-cos/batch-upload
Content-Type: application/json

{
  "files": [
    { "localPath": "<path1>", "remotePath": "<optional>", "conflictStrategy": "ask" },
    { "localPath": "<path2>", "conflictStrategy": "ask" }
  ]
}
```

**Body 参数：**
- `files`（必填）：文件数组（最多 20 个），每项包含：
  - `localPath`（必填）：本地文件绝对路径，支持 `~` 展开
  - `remotePath`（可选）：云端目标路径。省略则上传到根目录并保留原文件名
  - `conflictStrategy`（可选）：同名冲突策略，默认 `ask`

**Example:**

```bash
# macOS / Linux
curl -s -X POST http://localhost:$PORT/proxy/qclaw-cos/batch-upload \
  -H 'Content-Type: application/json' \
  -d '{"files":[{"localPath":"/path/to/report.pdf","conflictStrategy":"ask"},{"localPath":"/path/to/photo.jpg","conflictStrategy":"ask"},{"localPath":"/path/to/data.csv","conflictStrategy":"ask"}]}'
```

**Output (JSON):**

When all uploads **succeed**:

```json
{
  "success": true,
  "message": "3 个文件全部上传成功！链接可在 QClaw 小程序中随时查看。（保留 30 天后自动清理）\n\n📎 report.pdf (2.3 MB) — https://jsonproxy.3g.qq.com/urlmapper/aB3xYz\n📎 photo.jpg (1.1 MB) — https://jsonproxy.3g.qq.com/urlmapper/xK9mWq\n📎 data.csv (156 KB) — https://jsonproxy.3g.qq.com/urlmapper/pL2nRt",
  "total": 3,
  "successCount": 3,
  "failedCount": 0,
  "items": [ ... ]
}
```

When some uploads **fail** (partial success):

```json
{
  "success": false,
  "message": "3 个文件中 2 个上传成功（1 个失败）。成功文件的链接可在 QClaw 小程序中随时查看。（保留 30 天后自动清理）\n\n📎 report.pdf (2.3 MB) — https://jsonproxy.3g.qq.com/urlmapper/aB3xYz\n📎 photo.jpg (1.1 MB) — https://jsonproxy.3g.qq.com/urlmapper/xK9mWq\n\n❌ missing.log — 文件不存在: /path/to/missing.log",
  "total": 3,
  "successCount": 2,
  "failedCount": 1,
  "items": [ ... ]
}
```

> **CRITICAL**: The `message` field contains the **complete, pre-rendered summary** — file names, sizes, file links, success/failure counts, and the standard notice. **QClaw MUST output `message` verbatim.** Do NOT attempt to summarize or reformat the batch results yourself.

### info

Get file info for an existing cloud file (file link, preview, metadata).

```
POST /proxy/qclaw-cos/info
Content-Type: application/json

{ "remotePath": "<cloud-path>" }  // 必填：云端文件路径
```

**Example:**

```bash
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/info \
  -H 'Content-Type: application/json' \
  -d '{"remotePath":"report.pdf"}'
```

### list

List files in a cloud directory.

```
POST /proxy/qclaw-cos/list
Content-Type: application/json

{
  "dirPath": "<dir>",   // 可选：目录路径，默认 backup
  "limit": <n>          // 可选：最大返回数量，默认 50
}
```

**Examples:**

```bash
# List root directory
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/list \
  -H 'Content-Type: application/json' \
  -d '{"dirPath":"/"}'

# List with limit
curl -s -X POST http://localhost:PORT/proxy/qclaw-cos/list \
  -H 'Content-Type: application/json' \
  -d '{"dirPath":"/","limit":20}'
```

---

## Error Handling

所有命令输出 JSON 到 stdout。错误也以 JSON 返回：`{"success": false, "message": "...", "error": "..."}`

> **IMPORTANT**: 上传失败时，`message` 字段已包含完整的用户友好错误提示和操作选项。**直接输出 `message` 即可**，无需自行组织错误文案。

| 错误 | 处理方式 |
|------|---------|
| 上传失败（`success: false`） | 直接输出 `message` 字段内容（已包含错误原因和操作选项） |
| `401` / token 过期 | 告诉用户："云存储 token 已过期，请联系管理员刷新。" |
| 文件不存在 | `message` 已包含具体路径信息，直接输出即可 |
| 网络错误 | 重试 2 次，间隔 3s；仍失败则输出 `message` 字段内容 |
| 配额满 | 提示清理过期文件 |
| 上传取消 | `message` 已包含取消提示，直接输出即可 |

**IMPORTANT**: 上传失败时 **必须明确告知用户文件上传失败**，并给出具体错误原因。不要静默吞掉错误或仅显示技术日志。

---

## 禁止行为

- **NEVER** 忽略 `message` 字段自行从 `downloadUrl`、`fileInfo` 等字段拼接回复内容。`message` 是服务端预渲染的完整展示文本，**必须原样输出**
- **NEVER** 自己拼接、重组、修改任何 URL。如果需要展示链接，`message` 字段中已经包含了正确的链接
- **NEVER** 把 `rawDownloadUrl` 或 COS 长链中的任何片段与 `https://jsonproxy.3g.qq.com/` 拼接。短链由服务端生成，AI 不参与 URL 构造
- **NEVER** 对 `message` 中的内容做任何截断、修改、重组或格式变换
- **NEVER** 在批量上传时自行汇总/改写多个文件的结果。使用 `batch-upload` 接口，它的 `message` 已包含完整汇总
- **NEVER** 在 `success: false` 时展示文件链接
- **NEVER** 硬编码或暴露 SMH 凭证给用户
- **NEVER** 未经用户主动要求就上传其本地个人文件
- **NEVER** 在用户未明确表态时使用 `conflictStrategy: "rename"` 或 `conflictStrategy: "overwrite"`，必须用 `conflictStrategy: "ask"` 让用户选择

---

## 重要注意

- 用户说"上传文件"但没指定路径 → 追问："你要上传哪个文件？告诉我文件路径或文件名就行。"
- 用户说"确定上传 xxx"或"把 xxx 发给我" → 直接执行上传接口（`conflictStrategy: "ask"`）
- **单文件用 `upload`，多文件用 `batch-upload`**：2 个及以上文件时必须使用 `batch-upload` 接口，获取服务端预渲染的汇总 `message`
- **同名文件冲突**：上传时必须使用 `conflictStrategy: "ask"`。如果返回同名冲突错误，必须询问用户选择覆盖、重命名或取消，不要自行决定
- 文件默认上传到云空间根目录，用户可通过 `remotePath` 参数指定目标路径
- 文件链接会输出为短链格式（`https://jsonproxy.3g.qq.com/urlmapper/xxx`）。手机端点击短链拉起 QClaw 小程序查看（文件保留 30 天内可查），PC 端点击短链打开 H5 扫码页（微信扫码跳转小程序查看）；用户反馈链接过期时，用 `info` 获取新链接并重新生成短链
- 批量上传由服务端按顺序处理（不并行），避免 API 过载
- **`message` 原样输出 [CRITICAL]**：`upload` 和 `batch-upload` 接口返回的 `message` 字段包含完整的展示文本。QClaw **必须原样输出 `message`**，不得自行拼接或汇总回复。这是防止 AI 幻觉的核心机制
