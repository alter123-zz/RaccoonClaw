#!/usr/bin/env node

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import readline from "node:readline/promises";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = path.resolve(__dirname, "..");
const STATE_ROOT = path.join(os.homedir(), ".openclaw", "playwright-community-publisher");
const AUTH_ROOT = path.join(STATE_ROOT, "auth");
const ARTIFACT_ROOT = path.join(STATE_ROOT, "artifacts");
const TASKS_PATH = path.join(os.homedir(), ".openclaw", "workspace-chief_of_staff", "data", "tasks_source.json");
const TASK_ARTIFACT_DIRS = ["deliverables", "reports", "outputs", "artifacts"];
const TASK_ID_PATTERN = /(JJC-\d{8}-\d{3})/;
const COMPANY_STOCK_TAG_MAP = {
  腾讯: "$腾讯控股(00700)$",
  腾讯控股: "$腾讯控股(00700)$",
  阿里巴巴: "$阿里巴巴(09988)$",
  百度: "$百度集团(09888)$",
  小米: "$小米集团(01810)$",
  美团: "$美团(03690)$",
  京东: "$京东集团(09618)$",
  网易: "$网易(09999)$",
  哔哩哔哩: "$哔哩哔哩(09626)$",
  优必选: "$优必选(09880)$",
  中芯国际: "$中芯国际(688981)$",
  寒武纪: "$寒武纪(688256)$",
  海光信息: "$海光信息(688041)$",
  浪潮信息: "$浪潮信息(000977)$",
  科大讯飞: "$科大讯飞(002230)$",
  金山办公: "$金山办公(688111)$",
  三六零: "$三六零(601360)$",
  宁德时代: "$宁德时代(300750)$",
  比亚迪: "$比亚迪(002594)$",
  隆基绿能: "$隆基绿能(601012)$",
  英伟达: "$英伟达(NVDA)$",
  英特尔: "$英特尔(INTC)$",
  微软: "$微软(MSFT)$",
  苹果: "$苹果(AAPL)$",
  Meta: "$Meta(META)$",
};
const INDUSTRY_STOCK_TAG_FALLBACKS = [
  { keywords: ["DeepSeek", "OpenAI", "Claude", "Kimi", "豆包", "文心一言", "大模型", "AI", "人工智能"], tags: ["$科大讯飞(002230)$", "$金山办公(688111)$", "$三六零(601360)$"] },
  { keywords: ["GPU", "算力", "服务器", "云计算", "数据中心"], tags: ["$浪潮信息(000977)$", "$中科曙光(603019)$", "$工业富联(601138)$"] },
  { keywords: ["芯片", "半导体", "处理器", "英伟达", "NVIDIA", "AMD"], tags: ["$寒武纪(688256)$", "$海光信息(688041)$", "$中芯国际(688981)$"] },
  { keywords: ["机器人", "人形机器人", "优必选", "宇树科技"], tags: ["$优必选(09880)$", "$埃斯顿(002747)$", "$机器人(300024)$"] },
  { keywords: ["自动驾驶", "智能驾驶", "智驾"], tags: ["$中科创达(300496)$", "$德赛西威(002920)$", "$比亚迪(002594)$"] },
  { keywords: ["安全", "网络安全", "数据安全", "信息安全"], tags: ["$三六零(601360)$", "$深信服(300454)$", "$启明星辰(002439)$"] },
  { keywords: ["新能源", "锂电池", "固态电池", "储能"], tags: ["$宁德时代(300750)$", "$亿纬锂能(300014)$", "$阳光电源(300274)$"] },
  { keywords: ["光伏", "风电", "电网", "氢能", "核电"], tags: ["$隆基绿能(601012)$", "$阳光电源(300274)$", "$国电南瑞(600406)$"] },
  { keywords: ["低空经济", "eVTOL", "飞行汽车", "卫星"], tags: ["$万丰奥威(002085)$", "$中直股份(600038)$", "$中国卫星(600118)$"] },
];
const TOPIC_STOPWORDS = new Set([
  "我们", "你们", "他们", "进行", "这个", "那个", "以及", "为了", "目前", "已经", "还是", "一个", "一些",
  "内容", "方案", "报告", "建议", "分析", "任务", "执行", "完成", "结果", "发布", "讨论", "评论", "工作流",
  "模式", "系统", "项目", "能力", "问题", "需要", "可以", "如果", "因为", "所以", "通过", "相关", "当前",
  "今天", "近期", "阶段", "方向", "重点", "观察", "继续", "开始", "就是", "不是", "以及", "影响", "价值",
  "用户", "产品", "社区", "平台", "市场", "行业", "公司", "增长", "策略", "研究", "现状", "趋势", "选题",
]);

const SITE_PRESETS = {
  xueqiu: {
    homeUrl: "https://xueqiu.com/",
    loginUrl: "https://xueqiu.com/",
    signedOut: ["text=登录", "text=手机号登录"],
    actions: {
      comment: {
        requiresUrl: true,
        openComposer: [
          "button:has-text('评论')",
          "text=写评论",
          "[data-testid='comment-button']",
        ],
        composer: [
          "textarea",
          "[contenteditable='true']",
          "[placeholder*='写']",
          "[placeholder*='评论']",
        ],
        submit: [
          "a.lite-editor__submit:not(.disabled)",
          ".lite-editor__toolbar__post a.lite-editor__submit:not(.disabled)",
          "a:has-text('发布')",
          "button:has-text('发布')",
          "button:has-text('发送')",
          "button:has-text('评论')",
        ],
      },
      discussion: {
        requiresUrl: false,
        url: "https://xueqiu.com/",
        openComposer: [
          "button:has-text('发帖')",
          "a:has-text('发帖')",
          "text=发帖",
          "[data-testid='publish-entry']",
        ],
        chooseMode: [
          "text=发讨论",
          "button:has-text('发讨论')",
          "a:has-text('发讨论')",
          "[role='menuitem']:has-text('发讨论')",
        ],
        composer: [
          ".modals.dimmer.js-shown .modal__tiny__editor .medium-editor-element[role='textbox']",
          ".modals.dimmer.js-shown .modal__tiny__editor .lite-editor__textarea.post_status [contenteditable='true']",
          ".lite-editor__textarea.post_status",
          ".editor-container .lite-editor__textarea",
          ".lite-editor__bd .lite-editor__textarea",
          ".medium-editor-element[role='textbox']",
          "textarea",
          "[contenteditable='true']",
          "[placeholder*='讨论']",
          "[placeholder*='分享']",
          "text=发表你的观点",
          "[placeholder*='想法']",
        ],
        imageTrigger: [
          ".modals.dimmer.js-shown .modal__tiny__editor .lite-editor__toolbar__btn.lite-editor__upload--img",
          ".modal__tiny__editor .lite-editor__toolbar a.lite-editor__upload--img",
        ],
        imageInput: [
          ".modals.dimmer.js-shown .modal__tiny__editor form[action*='/photo/upload.json'] input[name='file'][type='file']",
        ],
        imagePreview: [
          ".modals.dimmer.js-shown .modal__tiny__editor .img-single-upload img.ke_img",
          ".modals.dimmer.js-shown .modal__tiny__editor .img-single-upload",
          ".modals.dimmer.js-shown .modal__tiny__editor img.ke_img",
        ],
        submit: [
          ".modals.dimmer.js-shown .modal__tiny__editor a.lite-editor__submit:not(.disabled)",
          "a.lite-editor__submit:not(.disabled)",
          ".lite-editor__toolbar__post a.lite-editor__submit:not(.disabled)",
          "a:has-text('发布')",
          "a:has-text('发表')",
          "button:has-text('发布')",
          "button:has-text('发表')",
          "button:has-text('发送')",
        ],
      },
    },
  },
  futu: {
    homeUrl: "https://www.futunn.com/",
    loginUrl: "https://www.futunn.com/",
    signedOut: ["text=登录", "text=立即登录", "text=注册/登录"],
    actions: {
      comment: {
        requiresUrl: true,
        openComposer: ["button:has-text('评论')", "text=写评论"],
        composer: ["textarea", "[contenteditable='true']", "[placeholder*='评论']"],
        submit: ["button:has-text('发布')", "button:has-text('发送')"],
      },
      discussion: {
        requiresUrl: false,
        url: "https://www.futunn.com/",
        openComposer: [
          "button:has-text('发帖')",
          "a:has-text('发帖')",
          "button:has-text('发布')",
          "a:has-text('发布')",
          "text=发帖",
          "[data-testid='publish-entry']",
        ],
        chooseMode: [
          "text=发讨论",
          "text=讨论",
          "button:has-text('发讨论')",
          "button:has-text('讨论')",
          "a:has-text('发讨论')",
          "a:has-text('讨论')",
          "[role='menuitem']:has-text('讨论')",
        ],
        composer: [
          ".modal textarea",
          ".modal [contenteditable='true']",
          ".dialog textarea",
          ".dialog [contenteditable='true']",
          "[placeholder*='说点什么']",
          "[placeholder*='分享']",
          "[placeholder*='讨论']",
          "[placeholder*='发表']",
          "textarea",
          "[contenteditable='true']",
        ],
        submit: [
          ".modal button:not([disabled]):has-text('发布')",
          ".dialog button:not([disabled]):has-text('发布')",
          ".modal a:not(.disabled):has-text('发布')",
          ".dialog a:not(.disabled):has-text('发布')",
          "button:not([disabled]):has-text('发布')",
          "button:not([disabled]):has-text('发表')",
          "button:not([disabled]):has-text('发送')",
          "a:not(.disabled):has-text('发布')",
          "a:not(.disabled):has-text('发表')",
        ],
      },
    },
  },
  tiger: {
    homeUrl: "https://www.itiger.com/",
    loginUrl: "https://www.itiger.com/",
    signedOut: ["text=登录", "text=Sign in", "text=立即登录"],
    actions: {
      comment: {
        requiresUrl: true,
        openComposer: ["button:has-text('评论')", "text=写评论"],
        composer: ["textarea", "[contenteditable='true']", "[placeholder*='评论']"],
        submit: ["button:has-text('发布')", "button:has-text('发送')", "button:has-text('Post')"],
      },
      discussion: {
        requiresUrl: false,
        url: "https://www.itiger.com/",
        openComposer: [
          "button:has-text('发帖')",
          "a:has-text('发帖')",
          "button:has-text('发布')",
          "a:has-text('发布')",
          "text=发帖",
          "text=Post",
          "[data-testid='publish-entry']",
        ],
        chooseMode: [
          "text=发讨论",
          "text=讨论",
          "button:has-text('发讨论')",
          "button:has-text('讨论')",
          "a:has-text('发讨论')",
          "a:has-text('讨论')",
          "button:has-text('Post')",
          "[role='menuitem']:has-text('讨论')",
        ],
        composer: [
          ".modal textarea",
          ".modal [contenteditable='true']",
          ".dialog textarea",
          ".dialog [contenteditable='true']",
          "[placeholder*='说点什么']",
          "[placeholder*='分享']",
          "[placeholder*='讨论']",
          "[placeholder*='发表']",
          "textarea",
          "[contenteditable='true']",
        ],
        submit: [
          ".modal button:not([disabled]):has-text('发布')",
          ".dialog button:not([disabled]):has-text('发布')",
          ".modal button:not([disabled]):has-text('Post')",
          ".dialog button:not([disabled]):has-text('Post')",
          ".modal a:not(.disabled):has-text('发布')",
          ".dialog a:not(.disabled):has-text('发布')",
          "button:not([disabled]):has-text('发布')",
          "button:not([disabled]):has-text('发表')",
          "button:not([disabled]):has-text('发送')",
          "button:not([disabled]):has-text('Post')",
          "a:not(.disabled):has-text('发布')",
          "a:not(.disabled):has-text('Post')",
        ],
      },
    },
  },
};

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) {
      continue;
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key] = true;
      continue;
    }
    args[key] = next;
    i += 1;
  }
  return args;
}

function usage(message = "") {
  if (message) {
    console.error(message);
    console.error("");
  }
  console.error(
    "Usage: node scripts/community_publisher.mjs --site <xueqiu|futu|tiger> [--action comment|discussion] [--url <post-url>] [--content <text> | --content-file <file> | --task-id <JJC-...>] [--image <path> | --image-file <path>] [--mode preview|confirm|publish] [--stocks 腾讯控股(00700),青云科技(688316)] [--topics AI,DeepSeek] [--config <json>] [--headless true|false]",
  );
  process.exit(1);
}

async function loadPlaywright() {
  try {
    return await import("playwright");
  } catch (error) {
    console.error(
      JSON.stringify(
        {
          status: "blocked",
          reason: "missing_dependency",
          message: "未安装 playwright，请先在可联网环境执行 npm install playwright",
          detail: String(error?.message || error),
        },
        null,
        2,
      ),
    );
    process.exit(2);
  }
}

function truthy(value, fallback = false) {
  if (value === undefined) {
    return fallback;
  }
  return ["1", "true", "yes", "y"].includes(String(value).toLowerCase());
}

function timestampId(date = new Date()) {
  return date.toISOString().replaceAll(":", "").replaceAll(".", "").replace("T", "-").replace("Z", "");
}

async function fileExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

async function ensureDir(targetPath) {
  await fs.mkdir(targetPath, { recursive: true });
}

async function readText(targetPath) {
  return fs.readFile(targetPath, "utf8");
}

async function readJsonIfExists(targetPath) {
  if (!(await fileExists(targetPath))) {
    return {};
  }
  return JSON.parse(await readText(targetPath));
}

async function walkFiles(rootPath, collector) {
  let entries = [];
  try {
    entries = await fs.readdir(rootPath, { withFileTypes: true });
  } catch {
    return;
  }

  for (const entry of entries) {
    const fullPath = path.join(rootPath, entry.name);
    if (entry.isDirectory()) {
      await walkFiles(fullPath, collector);
      continue;
    }
    if (entry.isFile()) {
      collector.push(fullPath);
    }
  }
}

function uniq(items) {
  return [...new Set(items.filter(Boolean))];
}

function normalizeWhitespace(text) {
  return String(text || "")
    .replace(/\r/g, "")
    .replace(/\t/g, " ")
    .replace(/[ \u00A0]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function stripMarkdown(text) {
  return normalizeWhitespace(
    String(text || "")
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/`([^`]+)`/g, "$1")
      .replace(/!\[[^\]]*]\([^)]*\)/g, " ")
      .replace(/\[([^\]]+)]\(([^)]+)\)/g, "$1")
      .replace(/^#{1,6}\s*/gm, "")
      .replace(/^\|.*\|$/gm, " ")
      .replace(/^\s*[-*+]\s+/gm, "")
      .replace(/^\s*\d+\.\s+/gm, "")
      .replace(/[*_>~]/g, " ")
  );
}

function compactSentence(text, maxChars = 140) {
  const normalized = normalizeWhitespace(text).replace(/\s+/g, " ");
  if (normalized.length <= maxChars) {
    return normalized;
  }
  return normalized.slice(0, maxChars).trim().replace(/[，、；：\s]+$/g, "") + "…";
}

function isLikelyPath(raw) {
  const value = String(raw || "").trim();
  if (!value) {
    return false;
  }
  return /[\\/]/.test(value) || /\.(md|txt|json|csv)$/i.test(value);
}

function parseListArg(raw) {
  return uniq(
    String(raw || "")
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean),
  );
}

async function loadTasks(taskFilePath = TASKS_PATH) {
  if (!(await fileExists(taskFilePath))) {
    return [];
  }
  const parsed = JSON.parse(await readText(taskFilePath));
  return Array.isArray(parsed) ? parsed : [];
}

async function findTaskRecord(taskId, taskFilePath = TASKS_PATH) {
  const tasks = await loadTasks(taskFilePath);
  return tasks.find((task) => String(task?.id || "").trim() === String(taskId || "").trim()) || null;
}

async function discoverTaskArtifacts(taskId) {
  const openclawRoot = path.join(os.homedir(), ".openclaw");
  let roots = [];
  try {
    roots = await fs.readdir(openclawRoot, { withFileTypes: true });
  } catch {
    return [];
  }

  const matched = [];
  for (const root of roots) {
    if (!root.isDirectory() || !root.name.startsWith("workspace-")) {
      continue;
    }
    const workspacePath = path.join(openclawRoot, root.name);
    for (const dirName of TASK_ARTIFACT_DIRS) {
      const folderPath = path.join(workspacePath, dirName);
      const files = [];
      await walkFiles(folderPath, files);
      for (const filePath of files) {
        if (!TASK_ID_PATTERN.test(path.basename(filePath))) {
          continue;
        }
        if (!path.basename(filePath).includes(taskId)) {
          continue;
        }
        matched.push(filePath);
      }
    }
  }

  return uniq(matched);
}

async function resolveTaskSourcePaths(task) {
  const candidates = [];
  for (const raw of [task?.resolvedOutput, task?.output]) {
    const value = String(raw || "").trim();
    if (!value || !isLikelyPath(value)) {
      continue;
    }
    if (path.isAbsolute(value) && (await fileExists(value))) {
      candidates.push(value);
      continue;
    }
    const taskWorkspaceGuess = path.join(os.homedir(), ".openclaw", "workspace-chief_of_staff", value);
    if (await fileExists(taskWorkspaceGuess)) {
      candidates.push(taskWorkspaceGuess);
    }
  }
  const discovered = await discoverTaskArtifacts(String(task?.id || ""));
  return uniq([...candidates, ...discovered]);
}

async function readTaskSourceBundle(task) {
  const sourcePaths = await resolveTaskSourcePaths(task);
  const snippets = [];

  for (const sourcePath of sourcePaths.slice(0, 4)) {
    try {
      const stats = await fs.stat(sourcePath);
      if (!stats.isFile()) {
        continue;
      }
      const ext = path.extname(sourcePath).toLowerCase();
      if (![".md", ".txt", ".json", ".csv"].includes(ext)) {
        continue;
      }
      snippets.push({
        path: sourcePath,
        text: await readText(sourcePath),
      });
    } catch {
      // ignore unreadable sources
    }
  }

  return snippets;
}

function extractHighlightCandidates(text) {
  const raw = String(text || "");
  const lines = raw.split("\n").map((line) => line.trim()).filter(Boolean);
  const highlights = [];

  for (const line of lines) {
    if (/^#{1,6}\s+/.test(line) || /^[-*+]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      highlights.push(stripMarkdown(line));
    }
  }

  if (highlights.length >= 3) {
    return uniq(highlights.map((item) => compactSentence(item, 90))).slice(0, 4);
  }

  const sentences = stripMarkdown(raw)
    .split(/[。！？!\n]/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 18);
  return uniq([...highlights, ...sentences].map((item) => compactSentence(item, 90))).slice(0, 4);
}

function extractLeadParagraph(text) {
  const paragraphs = stripMarkdown(text)
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 30);
  return paragraphs[0] || "";
}

function formatStockTag(name, code) {
  const cleanName = String(name || "").trim();
  const cleanCode = String(code || "").trim();
  if (!cleanCode) {
    return "";
  }
  return cleanName ? `$${cleanName}(${cleanCode})$` : `$${cleanCode}$`;
}

function extractStockTags(text, limit = 5) {
  const source = String(text || "");
  const tags = [];
  const seenCodes = new Set();
  const patterns = [
    /\$([^$()]{1,30})\((\d{4,6}|[A-Z]{1,6})\)\$/g,
    /([A-Za-z\u4e00-\u9fa5·]{2,30})\((\d{4,6}|[A-Z]{1,6})\)/g,
  ];

  for (const pattern of patterns) {
    let match;
    while ((match = pattern.exec(source)) !== null) {
      const code = String(match[2] || "").trim().toUpperCase();
      if (!code || seenCodes.has(code)) {
        continue;
      }
      seenCodes.add(code);
      tags.push(formatStockTag(match[1], code));
      if (tags.length >= limit) {
        return tags;
      }
    }
  }

  if (!tags.length) {
    for (const [name, tag] of Object.entries(COMPANY_STOCK_TAG_MAP)) {
      if (!source.includes(name)) {
        continue;
      }
      const codeMatch = tag.match(/\(([^()]+)\)/);
      const code = codeMatch?.[1] || tag;
      if (seenCodes.has(code)) {
        continue;
      }
      seenCodes.add(code);
      tags.push(tag);
      if (tags.length >= limit) {
        return tags;
      }
    }
  }

  if (!tags.length) {
    for (const { keywords, tags: fallbackTags } of INDUSTRY_STOCK_TAG_FALLBACKS) {
      if (!keywords.some((keyword) => source.includes(keyword))) {
        continue;
      }
      for (const tag of fallbackTags) {
        const codeMatch = tag.match(/\(([^()]+)\)/);
        const code = codeMatch?.[1] || tag;
        if (seenCodes.has(code)) {
          continue;
        }
        seenCodes.add(code);
        tags.push(tag);
        if (tags.length >= limit) {
          return tags;
        }
      }
    }
  }

  return tags;
}

function extractTopicTags(title, text, limit = 4) {
  const source = `${title || ""}\n${text || ""}`;
  const manualMentions = [];
  const knownPatterns = [
    /DeepSeek/gi,
    /OpenAI/gi,
    /Claude/gi,
    /ChatGPT/gi,
    /腾讯混元/g,
    /混元/g,
    /英伟达/g,
    /大模型/g,
    /AI/g,
    /智能体/g,
    /自动化/g,
    /知乎/g,
    /雪球/g,
    /量化/g,
    /云计算/g,
  ];

  for (const pattern of knownPatterns) {
    const match = source.match(pattern);
    if (match?.[0]) {
      manualMentions.push(match[0]);
    }
  }

  const tokenMatches = source.match(/[\u4e00-\u9fa5A-Za-z0-9]{2,12}/g) || [];
  const score = new Map();
  for (const token of [...manualMentions, ...tokenMatches]) {
    const normalized = String(token).trim();
    if (!normalized || TOPIC_STOPWORDS.has(normalized)) {
      continue;
    }
    if (/^\d+$/.test(normalized)) {
      continue;
    }
    score.set(normalized, (score.get(normalized) || 0) + 1);
  }

  return [...score.entries()]
    .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length)
    .map(([token]) => token)
    .filter((token) => token.length >= 2 && token.length <= 12)
    .slice(0, limit)
    .map((token) => `#${token}#`);
}

function decorateDiscussionContent(content, stockTags, topicTags) {
  const normalized = normalizeWhitespace(content);
  const hasAnyStock = stockTags.some((tag) => normalized.includes(tag));
  const pieces = [];

  pieces.push(normalized);
  if (stockTags.length && !hasAnyStock) {
    pieces.push(stockTags.join(" "));
  }

  return pieces.filter(Boolean).join("\n\n").trim();
}

function buildDiscussionDraft(task, bundle) {
  const mergedText = bundle.map((item) => item.text).join("\n\n");
  const lead = extractLeadParagraph(mergedText) || compactSentence(task?.title || "", 120);
  const highlights = extractHighlightCandidates(mergedText).slice(0, 3);
  const closingSource = stripMarkdown(mergedText)
    .split(/[。！？!\n]/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 20);
  const closing = compactSentence(closingSource.at(-1) || "后续还得继续看产品落地和真实反馈，这才是判断价值的关键。", 100);

  const lines = [];
  if (lead) {
    lines.push(compactSentence(lead, 180));
  }
  if (highlights.length) {
    lines.push("", "我更关注三点：");
    highlights.forEach((item, index) => {
      lines.push(`${index + 1}. ${compactSentence(item, 96)}`);
    });
  }
  if (closing) {
    lines.push("", closing);
  }
  return lines.join("\n").trim();
}

async function generateDiscussionFromTask(taskId, artifactDir, taskFilePath = TASKS_PATH) {
  const task = await findTaskRecord(taskId, taskFilePath);
  if (!task) {
    throw new Error(`任务不存在: ${taskId}`);
  }

  const bundle = await readTaskSourceBundle(task);
  const inlineFallback = String(task.output || "")
    .trim()
    .replace(/^\//, "");
  if (!bundle.length && inlineFallback && !isLikelyPath(inlineFallback)) {
    bundle.push({ path: "inline-output", text: inlineFallback });
  }

  if (!bundle.length) {
    throw new Error(`任务 ${taskId} 暂无可读取的交付内容，无法自动生成讨论正文`);
  }

  const mergedText = bundle.map((item) => item.text).join("\n\n");
  const stockTags = extractStockTags(mergedText);
  const topicTags = extractTopicTags(task.title, mergedText);
  const discussion = decorateDiscussionContent(buildDiscussionDraft(task, bundle), stockTags, []);
  const draftPath = path.join(artifactDir, `${taskId}-xueqiu-discussion.txt`);
  await fs.writeFile(draftPath, discussion, "utf8");

  return {
    task,
    draftPath,
    discussion,
    stockTags,
    topicTags,
    sourcePaths: bundle.map((item) => item.path),
  };
}

function mergePreset(basePreset, overridePreset) {
  const mergedActions = {};
  const baseActions = basePreset.actions || {};
  const overrideActions = overridePreset.actions || {};
  for (const action of new Set([...Object.keys(baseActions), ...Object.keys(overrideActions)])) {
    const baseAction = baseActions[action] || {};
    const overrideAction = overrideActions[action] || {};
    mergedActions[action] = {
      ...baseAction,
      ...overrideAction,
      openComposer: overrideAction.openComposer || baseAction.openComposer,
      chooseMode: overrideAction.chooseMode || baseAction.chooseMode,
      composer: overrideAction.composer || baseAction.composer,
      imageTrigger: overrideAction.imageTrigger || baseAction.imageTrigger,
      imageInput: overrideAction.imageInput || baseAction.imageInput,
      imagePreview: overrideAction.imagePreview || baseAction.imagePreview,
      submit: overrideAction.submit || baseAction.submit,
    };
  }
  return {
    ...basePreset,
    ...overridePreset,
    signedOut: overridePreset.signedOut || basePreset.signedOut,
    actions: mergedActions,
  };
}

async function firstVisible(page, selectors, timeoutMs = 1500) {
  for (const selector of selectors || []) {
    const locator = page.locator(selector);
    let count = 0;
    try {
      count = await locator.count();
    } catch {
      count = 0;
    }

    const limit = Math.min(count || 1, 8);
    for (let index = 0; index < limit; index += 1) {
      const candidate = locator.nth(index);
      try {
        await candidate.waitFor({ state: "visible", timeout: timeoutMs });
        return { locator: candidate, selector };
      } catch {
        // try next candidate
      }
    }
  }
  return null;
}

async function firstExisting(page, selectors) {
  for (const selector of selectors || []) {
    const locator = page.locator(selector);
    let count = 0;
    try {
      count = await locator.count();
    } catch {
      count = 0;
    }
    if (count > 0) {
      return { locator: locator.first(), selector };
    }
  }
  return null;
}

async function maybeClick(page, selectors) {
  const found = await firstVisible(page, selectors, 1200);
  if (!found) {
    return null;
  }
  await found.locator.click({ timeout: 2000 });
  return found.selector;
}

async function waitForActionable(page, selectors, timeoutMs = 5000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const found = await firstVisible(page, selectors, 400);
    if (found) {
      return found;
    }
    await page.waitForTimeout(250);
  }
  return null;
}

async function fillComposer(page, found, content) {
  const handle = await found.locator.elementHandle();
  const tagName = handle ? await handle.evaluate((el) => el.tagName.toLowerCase()) : "";
  const contentEditable = handle
    ? await handle.evaluate((el) => el.getAttribute("contenteditable"))
    : null;
  const className = handle ? await handle.evaluate((el) => el.className || "") : "";

  if (tagName === "textarea" || tagName === "input") {
    await found.locator.fill(content);
    return "fill";
  }

  if (contentEditable === "true") {
    await found.locator.evaluate((el) => {
      const editorRoot = el.closest(".lite-editor__textarea") || el.parentElement || el;
      const placeholder = editorRoot?.querySelector(".fake-placeholder");

      if (placeholder) {
        placeholder.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
        placeholder.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
        placeholder.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        placeholder.style.pointerEvents = "none";
      }

      if (typeof el.focus === "function") {
        el.focus();
      }

      const selection = window.getSelection?.();
      if (selection) {
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
      }
    });

    await page.waitForTimeout(120);
    await page.keyboard.insertText(content);

    await found.locator.evaluate((el, value) => {
      const normalizeParagraphs = (text) =>
        text
          .split(/\n{2,}/)
          .map((item) => item.trim())
          .filter(Boolean);

      const current = (el.textContent || "").trim();
      if (!current) {
        const paragraphs = normalizeParagraphs(value);
        el.replaceChildren();

        if (!paragraphs.length) {
          const br = document.createElement("br");
          el.append(br);
        } else {
          for (const paragraphText of paragraphs) {
            const p = document.createElement("p");
            p.textContent = paragraphText;
            el.appendChild(p);
          }
        }
      }

      const editorRoot = el.closest(".lite-editor__textarea") || el.parentElement || el;
      const placeholder = editorRoot?.querySelector(".fake-placeholder");
      if (placeholder) {
        placeholder.style.display = value.trim() ? "none" : "";
      }

      el.dispatchEvent(new FocusEvent("focus", { bubbles: true }));
      el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
      el.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "Enter" }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
      el.dispatchEvent(new FocusEvent("blur", { bubbles: true }));
    }, content);
    return "contenteditable";
  }

  if (String(className).includes("lite-editor__textarea")) {
    const placeholder = found.locator.locator(".fake-placeholder").first();
    try {
      if (await placeholder.isVisible({ timeout: 500 })) {
        await placeholder.click({ force: true, timeout: 2000 });
      } else {
        await found.locator.click({ force: true, timeout: 2000 });
      }
    } catch {
      await found.locator.evaluate((el) => {
        const placeholderEl = el.querySelector(".fake-placeholder");
        const target = placeholderEl || el;
        target.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
        target.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
        target.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        if (typeof el.focus === "function") {
          el.focus();
        }
      });
    }
    await page.waitForTimeout(150);
    await page.keyboard.insertText(content);
    return "lite-editor";
  }

  await found.locator.click({ force: true });
  await page.keyboard.insertText(content);
  return "keyboard";
}

async function anyVisible(page, selectors) {
  for (const selector of selectors || []) {
    const locator = page.locator(selector).first();
    try {
      await locator.waitFor({ state: "visible", timeout: 500 });
      if (await locator.isVisible()) {
        return selector;
      }
    } catch {
      // ignore
    }
  }
  return null;
}

async function resolveImage(args) {
  const imageArg = args.image || args["image-file"];
  if (!imageArg) {
    return null;
  }

  const resolvedPath = path.resolve(String(imageArg));
  if (!(await fileExists(resolvedPath))) {
    console.error(
      JSON.stringify(
        {
          status: "blocked",
          reason: "missing_image_file",
          message: `配图文件不存在: ${resolvedPath}`,
          action: "先提供有效图片路径，或不传 --image / --image-file",
        },
        null,
        2,
      ),
    );
    process.exit(7);
  }

  return resolvedPath;
}

async function uploadImage(page, actionConfig, imagePath) {
  if (!imagePath) {
    return null;
  }

  const waitForPreview = async (timeoutMs = 8000) =>
    waitForActionable(page, actionConfig.imagePreview || [], timeoutMs);

  const verifyUpload = async (mode, selector) => {
    const previewSelector = await waitForPreview(8000);
    if (!previewSelector) {
      throw new Error("图片未实际挂载到编辑器，请补充站点覆盖配置");
    }
    return { mode, selector, previewSelector: previewSelector.selector };
  };

  if (actionConfig.imageTrigger?.length) {
    const trigger = await firstVisible(page, actionConfig.imageTrigger, 1200);
    if (!trigger) {
      throw new Error("未找到配图上传入口，请补充站点覆盖配置");
    }

    const chooserPromise = page.waitForEvent("filechooser", { timeout: 2500 }).catch(() => null);
    await trigger.locator.click({ timeout: 2000, force: true });
    const chooser = await chooserPromise;
    if (chooser) {
      await chooser.setFiles(imagePath);
      const chooserPreview = await waitForPreview(1800);
      if (chooserPreview) {
        return { mode: "filechooser", selector: trigger.selector, previewSelector: chooserPreview.selector };
      }
    }

    await page.waitForTimeout(500);
    const fallbackInput = await firstExisting(page, actionConfig.imageInput || []);
    if (fallbackInput) {
      await fallbackInput.locator.setInputFiles(imagePath);
      return verifyUpload("trigger+input", fallbackInput.selector);
    }
  }

  const directInput = await firstExisting(page, actionConfig.imageInput || []);
  if (directInput) {
    await directInput.locator.setInputFiles(imagePath);
    return verifyUpload("input", directInput.selector);
  }

  throw new Error("未找到配图上传控件，请补充站点覆盖配置");
}

async function moveUploadedImageToFront(composer) {
  return composer.locator.evaluate((el) => {
    const imageBlock = el.querySelector(".img-single-upload");
    if (!imageBlock) {
      return false;
    }

    const nodes = [...el.childNodes].filter((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        return (node.textContent || "").trim().length > 0;
      }
      if (node.nodeType !== Node.ELEMENT_NODE) {
        return false;
      }
      const element = /** @type {HTMLElement} */ (node);
      if (element === imageBlock) {
        return true;
      }
      return element.textContent?.trim() || element.querySelector("img");
    });
    const firstNode = nodes[0] || el.firstChild;
    if (firstNode !== imageBlock) {
      el.insertBefore(imageBlock, firstNode || null);
    }

    el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertParagraph" }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  });
}

function actionLabel(action) {
  return action === "discussion" ? "讨论" : "评论";
}

async function resolveContent(args) {
  if (args.content && String(args.content).trim()) {
    return { content: String(args.content), source: "inline" };
  }

  const contentFile = args["content-file"];
  if (!contentFile) {
    return { content: "", source: "" };
  }

  const resolvedPath = path.resolve(contentFile);
  if (!(await fileExists(resolvedPath))) {
    console.error(
      JSON.stringify(
        {
          status: "blocked",
          reason: "missing_content_file",
          message: `内容文件不存在: ${resolvedPath}`,
          action: `先创建该文件，或改用 --content 直接传正文`,
        },
        null,
        2,
      ),
    );
    process.exit(6);
  }

  return { content: await readText(resolvedPath), source: resolvedPath };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const site = args.site;
  const url = args.url;
  const action = args.action || "comment";
  const mode = args.mode || "preview";
  const headless = truthy(args.headless, false);
  const taskId = String(args["task-id"] || "").trim();

  if (!site || !SITE_PRESETS[site]) {
    usage("缺少或不支持的 --site，支持 xueqiu / futu / tiger");
  }
  if (!["preview", "publish", "confirm"].includes(mode)) {
    usage("--mode 仅支持 preview、publish 或 confirm");
  }

  const configOverride = args.config ? await readJsonIfExists(path.resolve(args.config)) : {};
  const siteConfig = mergePreset(SITE_PRESETS[site], configOverride[site] || {});
  const actionConfig = siteConfig.actions?.[action];
  if (!actionConfig) {
    usage(`站点 ${site} 不支持 --action ${action}`);
  }
  if (actionConfig.requiresUrl && !url) {
    usage(`动作 ${action} 缺少 --url`);
  }

  await ensureDir(AUTH_ROOT);
  const storageStatePath = args["storage-state"] || path.join(AUTH_ROOT, `${site}.json`);
  if (!(await fileExists(storageStatePath))) {
    console.error(
      JSON.stringify(
        {
          status: "blocked",
          site,
          reason: "missing_auth_state",
          message: `未找到登录态文件: ${storageStatePath}`,
          action: `先运行 node ${path.join(SKILL_ROOT, "scripts", "save_auth_state.mjs")} --site ${site}`,
        },
        null,
        2,
      ),
    );
    process.exit(3);
  }

  const runId = timestampId();
  const artifactDir = path.join(ARTIFACT_ROOT, site, runId);
  await ensureDir(artifactDir);
  const imagePath = await resolveImage(args);

  let contentPayload = await resolveContent(args);
  let generated = null;
  if (!contentPayload.content.trim() && taskId) {
    generated = await generateDiscussionFromTask(taskId, artifactDir, args["task-file"] ? path.resolve(args["task-file"]) : TASKS_PATH);
    contentPayload = { content: generated.discussion, source: generated.draftPath };
  }

  if (!contentPayload.content.trim()) {
    usage("缺少评论内容，请传 --content、--content-file，或使用 --task-id 从任务结果自动生成");
  }

  let content = contentPayload.content.trim();
  const manualStocks = parseListArg(args.stocks).map((item) => {
    if (item.startsWith("$")) {
      return item;
    }
    const match = item.match(/^([^()]+)\(([^()]+)\)$/);
    if (match) {
      return formatStockTag(match[1], match[2]);
    }
    return `$${item}$`;
  });
  const manualTopics = parseListArg(args.topics).map((item) => {
    if (item.startsWith("#") && item.endsWith("#")) {
      return item;
    }
    return `#${item.replace(/^#+|#+$/g, "")}#`;
  });

  const autoStocksEnabled = truthy(args["auto-stocks"], site === "xueqiu" && action === "discussion");
  const autoTopicsEnabled = truthy(args["auto-topics"], false);
  const stockTags = uniq([
    ...(autoStocksEnabled ? extractStockTags(content) : []),
    ...(generated?.stockTags || []),
    ...manualStocks,
  ]).slice(0, 5);
  const topicTags = uniq([
    ...(autoTopicsEnabled ? extractTopicTags(generated?.task?.title || "", content) : []),
    ...(autoTopicsEnabled ? generated?.topicTags || [] : []),
    ...manualTopics,
  ]).slice(0, 5);

  if (site === "xueqiu" && action === "discussion") {
    content = decorateDiscussionContent(content, stockTags, topicTags);
    if (contentPayload.source && contentPayload.source !== "inline") {
      await fs.writeFile(contentPayload.source, content, "utf8");
    }
  }

  const { chromium } = await loadPlaywright();
  const browser = await chromium.launch({ headless });
  const context = await browser.newContext({ storageState: storageStatePath });
  await context.tracing.start({ screenshots: true, snapshots: true });
  const page = await context.newPage();

  const result = {
    status: "blocked",
    site,
    action,
    mode,
    url: url || actionConfig.url || siteConfig.homeUrl,
    artifactDir,
    steps: [],
  };
  if (taskId) {
    result.taskId = taskId;
  }
  if (contentPayload.source) {
    result.contentSource = contentPayload.source;
  }
  if (imagePath) {
    result.imageSource = imagePath;
  }
  if (topicTags.length) {
    result.topicTags = topicTags;
  }
  if (stockTags.length) {
    result.stockTags = stockTags;
  }
  if (generated?.sourcePaths?.length) {
    result.generatedFrom = generated.sourcePaths;
  }

  try {
    await page.goto(result.url, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2000);
    result.steps.push("goto");

    const signedOutSelector = await anyVisible(page, siteConfig.signedOut);
    if (signedOutSelector) {
      throw new Error(`登录态失效，检测到未登录提示: ${signedOutSelector}`);
    }

    const openSelector = await maybeClick(page, actionConfig.openComposer);
    if (openSelector) {
      result.steps.push(`openComposer:${openSelector}`);
      await page.waitForTimeout(1200);
    }

    if (actionConfig.chooseMode?.length) {
      const modeSelector = await maybeClick(page, actionConfig.chooseMode);
      if (modeSelector) {
        result.steps.push(`chooseMode:${modeSelector}`);
        await page.waitForTimeout(1500);
      }
    }

    const composer = await firstVisible(page, actionConfig.composer, 2500);
    if (!composer) {
      throw new Error(`未找到${action === "discussion" ? "发讨论" : "评论"}输入框，请补充站点覆盖配置`);
    }

    const fillMode = await fillComposer(page, composer, content.trim());
    result.steps.push(`composer:${composer.selector}`);
    result.steps.push(`fill:${fillMode}`);

    let imagePreviewSelector = "";
    if (imagePath) {
      const upload = await uploadImage(page, actionConfig, imagePath);
      result.steps.push(`image:${upload.mode}:${upload.selector}`);
      imagePreviewSelector = upload.previewSelector || "";
      result.imagePreviewSelector = imagePreviewSelector;
      const movedImage = await moveUploadedImageToFront(composer);
      if (movedImage) {
        result.steps.push("image:move-to-front");
      }
      await page.waitForTimeout(1800);
    }

    if (imagePreviewSelector) {
      const previewTarget = await firstVisible(page, [imagePreviewSelector], 1200);
      if (previewTarget) {
        await previewTarget.locator.scrollIntoViewIfNeeded();
        await page.waitForTimeout(500);
      }
    }

    const previewPath = path.join(artifactDir, "preview.png");
    await page.screenshot({ path: previewPath, fullPage: true });
    result.previewScreenshot = previewPath;

    if (mode === "preview") {
      result.status = "preview_ready";
      result.message = `${actionLabel(action)}已填充，当前停在发布前预览`;
    } else {
      if (mode === "confirm") {
        const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
        const answer = await rl.question(`预览已生成: ${previewPath}\n确认发布请输入 y，取消直接回车: `);
        await rl.close();
        if (!/^y(es)?$/i.test(String(answer || "").trim())) {
          result.status = "preview_ready";
          result.message = `${actionLabel(action)}已生成预览，未执行发布`;
          result.confirmed = false;
          console.log(JSON.stringify(result, null, 2));
          return;
        }
        result.confirmed = true;
      }
      const submit = await waitForActionable(page, actionConfig.submit, 6000);
      if (!submit) {
        throw new Error("未找到发布按钮，请补充站点覆盖配置");
      }
      await submit.locator.click({ timeout: 3000 });
      result.steps.push(`submit:${submit.selector}`);
      await page.waitForTimeout(2500);
      const publishedPath = path.join(artifactDir, "published.png");
      await page.screenshot({ path: publishedPath, fullPage: true });
      result.publishedScreenshot = publishedPath;
      result.status = "published";
      result.message = `${actionLabel(action)}已提交`;
    }
  } catch (error) {
    const errorPath = path.join(artifactDir, "error.png");
    try {
      await page.screenshot({ path: errorPath, fullPage: true });
      result.errorScreenshot = errorPath;
    } catch {
      // ignore screenshot failure
    }
    result.status = "blocked";
    result.reason = "automation_failed";
    result.message = String(error?.message || error);
  } finally {
    const tracePath = path.join(artifactDir, "trace.zip");
    try {
      await context.tracing.stop({ path: tracePath });
      result.trace = tracePath;
    } catch {
      // ignore trace stop failure
    }
    await fs.writeFile(path.join(artifactDir, "result.json"), JSON.stringify(result, null, 2), "utf8");
    await context.close();
    await browser.close();
  }

  console.log(JSON.stringify(result, null, 2));
  process.exit(result.status === "blocked" ? 4 : 0);
}

main().catch((error) => {
  console.error(
    JSON.stringify(
      {
        status: "blocked",
        reason: "unexpected_error",
        message: String(error?.message || error),
      },
      null,
      2,
    ),
  );
  process.exit(5);
});
