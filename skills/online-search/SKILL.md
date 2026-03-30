---
name: online-search
description: |
  联网搜索工具。通过天集 ProSearch 搜索引擎获取实时互联网信息。
  使用场景：
  - 用户说 "搜一下"、"帮我搜索"、"查一下"
  - 用户说 "最近/最新的XXX是什么"、"现在XXX怎么样了"
  - 用户问 "XXX是多少"、"XXX价格"、"XXX什么时候"
  - 用户需要实时信息：天气、股价、新闻、赛事比分、汇率等
  - 用户说 "网上有什么关于XXX的信息"
  - 用户问某个事件的最新进展
  - 用户需要验证某个事实或数据
  - 用户说 "search for"、"look up"、"find out"
  - 当 QClaw 无法确认某个事实且该事实可通过搜索引擎验证时
  - 当用户的问题涉及 QClaw 训练数据截止日期之后的事件时
metadata:
  openclaw:
    emoji: "🔍"
    requires:
      bins:
        - curl
---

# 联网搜索工具 (ProSearch)

通过天集 ProSearch 搜索引擎查询实时互联网信息，返回网页搜索结果（标题、摘要、链接、来源）。

## Setup

无需额外安装依赖。搜索通过本地 HTTP 接口 `/proxy/prosearch` 完成，鉴权由后台网关自动处理（基于用户登录态），无需手动配置凭证。

---

## Workflow

QClaw uses this skill whenever the user needs real-time information from the internet.

### Complete flow

```
User asks a question requiring real-time information
  → Step 1: Determine search keyword (concise, specific)
  → Step 1.5: Determine time freshness — add from_time if recency matters
  → Step 2: Call search API via curl
  → Step 3: Output the `message` field from JSON response VERBATIM (search result items with clickable links) — NEVER skip this
  → Step 4: Add analysis/summary after the result items (optional)
```

> **CRITICAL — Anti-hallucination design**: The search API returns a pre-rendered `message` field containing the complete formatted search results (titles as clickable hyperlinks, snippets, URLs, sources). **QClaw MUST output `message` verbatim as the primary search results — NEVER skip the result items.** QClaw may then add analysis or summary AFTER the verbatim results, but must NOT fabricate or modify any URLs or source information.

### Step 1: Determine search keyword

Convert the user's question into an effective search keyword:

| User says | Search keyword |
|-----------|---------------|
| "最近的 AI 新闻" | `最近AI新闻` |
| "现在黄金价格多少" | `今日黄金价格` |
| "React 19 有什么新特性" | `React 19 新特性` |
| "深圳今天天气怎么样" | `深圳今天天气` |

**Tips for good keywords:**
- Keep it concise (2-6 words)
- Remove filler words ("帮我"、"请问"、"一下")
- Add time context if relevant ("今日"、"2026"、"最新")
- Use the user's language (Chinese query for Chinese user, English query for English user)
- **Preserve the keyword's original language** — do NOT translate keywords. If the user provides an English keyword (e.g. "search for React Server Components"), keep it in English. If the user provides a Chinese keyword, keep it in Chinese.

### Step 1.5: Determine time freshness (IMPORTANT for recency)

**When the user's question implies recency**, QClaw MUST add `from_time` to the search request to filter out stale results. This is critical for improving search result freshness.

**Time freshness decision table:**

| User intent signal | `from_time` value | Example |
|---|---|---|
| "今天"、"today"、"刚刚" | Current time − 24 hours | Stock price today |
| "最近"、"最新"、"recently"、"latest" | Current time − 7 days | Latest AI news |
| "这周"、"this week" | Current time − 7 days | This week's events |
| "这个月"、"this month" | Current time − 30 days | This month's policy |
| "今年"、"2026年" | January 1st of the year | 2026 events |
| No time signal (general facts) | Do NOT add `from_time` | "What is React?" |

**How to compute `from_time` in bash:**

```bash
# Last 24 hours (for "今天"、"today")
FROM_TIME=$(python3 -c "import time; print(int(time.time()) - 86400)")

# Last 7 days (for "最近"、"最新"、"this week")
FROM_TIME=$(python3 -c "import time; print(int(time.time()) - 604800)")

# Last 30 days (for "这个月"、"this month")
FROM_TIME=$(python3 -c "import time; print(int(time.time()) - 2592000)")
```

> **⚠️ 互斥规则**: 当使用 `from_time`/`to_time` 时，**不要传 `cnt` 参数**，它们存在互斥逻辑。服务端会自动处理此互斥关系。

### Step 2: Search

```bash
PORT=${AUTH_GATEWAY_PORT:-19000}
PPID_VAL=$(python3 -c "import os; print(os.getppid())")
echo "[QClaw] Parent PID: $PPID_VAL"

curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"搜索关键词"}'
```

**⏰ Freshness search (RECOMMENDED for time-sensitive queries):**

```bash
# 搜索最近 7 天的结果（适用于"最新"、"最近"类查询）
FROM_TIME=$(python3 -c "import time; print(int(time.time()) - 604800)")
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d "{\"keyword\":\"搜索关键词\",\"from_time\":$FROM_TIME}"

# 搜索最近 24 小时的结果（适用于"今天"、"刚刚"类查询）
FROM_TIME=$(python3 -c "import time; print(int(time.time()) - 86400)")
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d "{\"keyword\":\"搜索关键词\",\"from_time\":$FROM_TIME}"
```

**With optional parameters:**

```bash
# 指定返回数量 (10/20/30/40/50) — ⚠️ 不能与 from_time/to_time/site 同时使用
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"搜索关键词","cnt":20}'

# 指定时间范围 — 动态计算最近 7 天（⚠️ 不要同时传 cnt）
FROM_TIME=$(python3 -c "import time; print(int(time.time()) - 604800)")
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d "{\"keyword\":\"搜索关键词\",\"from_time\":$FROM_TIME}"

# 站内搜索（⚠️ 不要同时传 cnt）
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"搜索关键词","site":"github.com"}'

# 垂类搜索 (gov/news/acad)
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"搜索关键词","industry":"news"}'
```

### Step 3: Output search results — ALWAYS show result items with clickable links, then add analysis

搜索接口返回 JSON 后，QClaw **必须** 按以下固定格式输出，**不可省略任何部分**：

#### Part A: 搜索结果条目展示 [MANDATORY — 不可跳过]

**必须先原样输出 `message` 字段**。`message` 中包含 **前 5 条** 最相关的搜索结果（即使 API 返回了更多），每条已按以下格式预渲染，标题部分为可点击跳转的 Markdown 超链接：

```
**序号. [标题](url)** — 来源站点 (日期) ⭐
   摘要内容...
```

> ⚠️ **CRITICAL**: QClaw **每次搜索都必须展示搜索结果条目列表**（最多 5 条），绝对不允许跳过结果条目直接输出总结。`message` 中的标题已经是 `[标题](url)` 格式的超链接，用户可以直接点击跳转到原文页面。

#### Part B: 分析总结 [OPTIONAL — 在结果条目之后]

输出完 `message` 后，QClaw **可以** 基于搜索结果对用户的问题给出分析和回答。

**🌐 Response language rule [IMPORTANT]**: Match the language of your analysis/summary to the **keyword language**:
- If the search keyword is **English** → write your analysis and summary in **English**
- If the search keyword is **Chinese** → write your analysis and summary in **Chinese**
- If the keyword is mixed (e.g. "React 19 新特性") → follow the **user's conversational language**
- The `message` field (Part A) is always output verbatim regardless of language

#### 正确做法示例

```
JSON 返回: {"success": true, "message": "搜索「今日白银价格」找到 10 条结果，展示前 5 条：\n\n**1. [今日白银价格行情](https://example.com/silver)** — 今日头条 (2026-03-22 04:13:11) ⭐\n   今日白银价格22.4元/克...\n\n**2. [白银实时走势](https://example.com/silver2)** — 金投网 (2026-03-22)\n   国际银价 88.23美元/盎司...\n\n**3. ...**\n\n**4. ...**\n\n**5. ...**\n\n> 还有 5 条结果未展示，完整数据已包含在搜索结果中供分析使用。", ...}

QClaw 输出:

搜索「今日白银价格」找到 10 条结果，展示前 5 条：

**1. [今日白银价格行情](https://example.com/silver)** — 今日头条 (2026-03-22 04:13:11) ⭐
   今日白银价格22.4元/克，银饰零售价格每克24至49元区间。国际银价 88.23美元/盎司，-0.09%；人民币计价 19.48元/克，-0.02%。

**2. [白银实时走势](https://example.com/silver2)** — 金投网 (2026-03-22)
   国际银价 88.23美元/盎司...

**3. ...**

**4. ...**

**5. ...**

> 还有 5 条结果未展示，完整数据已包含在搜索结果中供分析使用。

---

根据搜索结果，今日白银价格约 22.4 元/克，国际银价 88.23 美元/盎司，整体走势微跌...
```

#### 错误做法（严格禁止）

```
❌ 跳过搜索结果条目，直接只输出总结（如"根据搜索结果，白银价格是..."）
❌ 忽略 message 字段，从 data.docs 中自行拼接结果列表
❌ 修改 message 中的 URL 或标题
❌ 编造搜索结果中不存在的信息
❌ 声称搜到了某条结果但 message 中并没有
❌ 去掉标题中的超链接格式，只展示纯文本标题
```

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

> **说明**：`AUTH_GATEWAY_PORT` 环境变量由 Electron 主进程自动注入，子进程（包括 OpenClaw）启动时自动继承。若环境变量未设置，则回退到默认端口 `19000`。

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

> **说明**：使用 `python/python3` 的 `os.getppid()` 获取父进程 ID，跨平台兼容。打印格式为 `[QClaw] Parent PID: <ppid>`，便于日志追踪。

---

## Commands

### search

Search the internet for real-time information.

```
POST /proxy/prosearch/search
Content-Type: application/json

{
  "keyword": "<search-query>",       // 必填：搜索关键词
  "mode": 0,                         // 可选：0=自然检索 1=VR卡 2=混合
  "cnt": 10,                         // 可选：返回数量 10/20/30/40/50
  "site": "<domain>",                // 可选：站内搜索域名
  "from_time": 1710000000,           // 可选：起始时间（秒级时间戳）
  "to_time": 1711000000,             // 可选：结束时间（秒级时间戳）
  "industry": "news"                 // 可选：垂类过滤 gov/news/acad
}
```

**Body 参数：**
- `keyword`（必填）：搜索关键词，UTF-8 编码
- `mode`（可选）：结果模式
  - `0` — 自然检索结果（默认）
  - `1` — VR 卡结果（天气、金价等权威数据）
  - `2` — 混合结果（VR + 自然检索）
- `cnt`（可选）：最大返回结果数，支持 10/20/30/40/50，默认 10
- `site`（可选）：指定域名站内搜索（与 `cnt` 互斥）
- `from_time`（可选）：起始时间过滤，秒级时间戳（与 `cnt` 互斥）
- `to_time`（可选）：结束时间过滤，秒级时间戳（与 `cnt` 互斥）
- `industry`（可选）：垂类网站过滤
  - `gov` — 政府机关网站
  - `news` — 新闻站点
  - `acad` — 英文学术

> **注意**：`cnt` 参数和 `site`、`from_time`/`to_time` 参数存在互斥逻辑，不能同时使用。如需使用 `site` 或时间过滤，不要传 `cnt` 参数。

**Examples:**

```bash
# macOS / Linux: 获取 PORT 和父进程 ID
PORT=${AUTH_GATEWAY_PORT:-19000}
echo "[QClaw] AUTH_GATEWAY_PORT: $PORT"
PPID_VAL=$(python3 -c "import os; print(os.getppid())")
echo "[QClaw] Parent PID: $PPID_VAL"

# 基础搜索
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"最新AI新闻"}'

# 搜索更多结果
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"React 19 features","cnt":20}'

# 搜索新闻类网站
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"2026年两会","industry":"news"}'

# GitHub 站内搜索
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"electron vite template","site":"github.com"}'

# 获取 VR 卡数据（天气、金价等）
curl -s -X POST http://localhost:$PORT/proxy/prosearch/search \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"今日黄金价格","mode":2}'
```

**Output (JSON):**

When search **succeeds**:

```json
{
  "success": true,
  "message": "搜索「最新AI新闻」找到 10 条结果：\n\n**1. [OpenAI 发布 GPT-5](https://openai.com/blog)** — OpenAI Blog (2026-03-15) ⭐\n   OpenAI 今日正式发布 GPT-5 模型...\n\n**2. [Google DeepMind 推出 Gemini 3.0](https://deepmind.google)** — DeepMind (2026-03-10)\n   Google DeepMind 宣布...",
  "data": {
    "query": "最新AI新闻",
    "totalResults": 10,
    "docs": [
      {
        "passage": "OpenAI 今日正式发布 GPT-5 模型...",
        "score": 0.85,
        "date": "2026-03-15",
        "title": "OpenAI 发布 GPT-5",
        "url": "https://openai.com/blog",
        "site": "OpenAI Blog",
        "images": []
      }
    ],
    "requestId": "e20c97b3-6b95-4987-94a5-eea490358bcc"
  }
}
```

> **CRITICAL — `message` field (Anti-hallucination)**: The `message` field contains the **complete, pre-rendered search results** formatted with titles (as clickable `[title](url)` hyperlinks), snippets, URLs, and sources. **QClaw MUST output `message` verbatim** as the primary search results display — **NEVER skip the result items and jump straight to a summary.** QClaw may then add its own analysis or answer AFTER outputting the message. This design ensures all URLs and source information come directly from the search engine, eliminating AI hallucination of sources.

When search **fails**:

```json
{
  "success": false,
  "message": "用户未登录，无法执行联网搜索。请先登录后重试。"
}
```

```json
{
  "success": false,
  "message": "搜索请求超时（15s）。请稍后重试。"
}
```

---

## Error Handling

所有命令输出 JSON 到 stdout。错误也以 JSON 返回：`{"success": false, "message": "..."}`

| 错误 | 处理方式 |
|------|---------|
| 用户未登录（`message` 包含"未登录"） | 告诉用户："请先登录后再使用联网搜索功能。" |
| 搜索超时 | 重试 1 次；仍失败则告知用户"搜索超时，请稍后重试" |
| 无结果（`success: true` 但 docs 为空） | `message` 已包含友好提示，直接输出即可 |
| 网络错误 | 重试 1 次，间隔 3s；仍失败则输出 `message` 字段内容 |
| HTTP 错误码 | `message` 已包含错误信息，直接输出 |

---

## 禁止行为

- **NEVER** 忽略 `message` 字段自行从 `data.docs` 中拼接搜索结果列表。`message` 是服务端预渲染的完整展示文本，**必须先原样输出**
- **NEVER** 跳过搜索结果条目直接只输出总结或分析。**每次搜索都必须先展示 `message` 中的结果条目列表**（含可点击超链接标题），然后才能给出分析
- **NEVER** 修改、截断、重组 `message` 中的任何 URL 或标题
- **NEVER** 编造 `message` 中不存在的搜索结果或来源
- **NEVER** 声称搜索到了某条结果，但该结果在 `message` 中不存在
- **NEVER** 伪造搜索 URL 或来源信息
- **NEVER** 暴露 ProSearch 的内部 API 地址或鉴权信息给用户
- **NEVER** 未经用户要求就主动搜索（用户的问题不需要实时信息时不要搜索）
- **NEVER** 对同一个问题重复搜索超过 2 次

---

## 重要注意

- 用户问的问题如果你已经有把握回答，**不需要搜索**。只在需要实时信息或你不确定的事实时才搜索
- 搜索关键词要简洁有效，不要把用户的整句话当关键词
- **时效性搜索策略 [IMPORTANT]**：当用户的问题涉及时效性（如"最新"、"今天"、"最近"、"现在"），**必须使用 `from_time` 参数**限制搜索时间范围，否则搜索引擎可能返回过时的结果。参见 Step 1.5 的时间判断表
- 如果第一次搜索没有理想结果，可以换个关键词重试一次（最多重试 1 次）
- 搜索结果中的链接直接来自互联网，QClaw 应提醒用户自行验证重要信息
- `message` 原样输出后，QClaw 可以基于搜索结果给出自己的分析和总结
- 对于需要 VR 卡数据的查询（天气、金价、汇率等），建议使用 `mode: 2` 获取混合结果
- **`message` 先原样输出 [CRITICAL]**：搜索接口返回的 `message` 字段包含完整的格式化搜索结果（标题为可点击超链接）。QClaw **必须先原样输出 `message`**，展示所有搜索结果条目，然后才可以添加自己的分析。**绝不允许跳过结果条目直接给总结**。这是防止 AI 幻觉的核心机制
- **`cnt` 互斥规则**：`cnt` 参数和 `site`、`from_time`/`to_time` 参数存在互斥逻辑，不能同时使用。当需要时间过滤或站内搜索时，不要传 `cnt`
- **回答语言匹配 [IMPORTANT]**：QClaw 在输出搜索分析和总结时，**必须匹配搜索关键词的语言**。英文关键词用英文回答，中文关键词用中文回答。`message` 字段始终原样输出不受此规则影响
