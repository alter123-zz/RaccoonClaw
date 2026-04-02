#!/usr/bin/env python3
"""Shared blocker parsing utilities for task feedback and runtime guards."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re


_STRUCTURED_TRIGGER_RE = re.compile(
    r"(阻塞|遇阻|无法执行|无法继续|需登录|需要token|未配置|未找到|缺少|Service Unavailable|406 Not Acceptable|API Key|API_KEY|Cookie|凭证|授权|auth_error|rate limit|bot-detection)",
    re.IGNORECASE,
)
_FLOW_BLOCK_RE = re.compile(r"(执行回传（阻塞）|阻塞：|回传总裁办)", re.IGNORECASE)

_MISSING_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("联网搜索技能/额度", re.compile(r"Brave(?: Web)? Search|Brave API|web search.*API Key|设置 Brave Search|((缺少|未配置|未找到|需配置).{0,8}(智谱|zhipu))|(ZHIPUAI_API_KEY|zhipuai\.json).{0,12}(缺少|未配置|未找到|为空|需配置)|rate limit|额度耗尽|配额耗尽|bot-detection|DuckDuckGo returned a bot-detection challenge|auth_error", re.IGNORECASE)),
    ("浏览器 CLI 运行环境", re.compile(r"playwright|chromium|browser cli|浏览器 CLI|Executable doesn't exist|Failed to launch browser", re.IGNORECASE)),
    ("小红书登录 Cookie / Token", re.compile(r"小红书.*(Cookie|cookie|token|Token|需登录|登录token|406)", re.IGNORECASE)),
    ("第三方数据平台 API Key", re.compile(r"(新榜|蝉妈妈).*(API|Key|授权)|第三方数据平台", re.IGNORECASE)),
    ("浏览器代理技能", re.compile(r"浏览器代理|autoglm-browser-agent|签名验证失败|browser agent", re.IGNORECASE)),
    ("本地 token 服务", re.compile(r"127\.0\.0\.1:53699|get_token|Service Unavailable|503", re.IGNORECASE)),
]

_ACTION_MAP = {
    "联网搜索技能/额度": "立即改用浏览器 CLI：`python3 scripts/browser_cli.py search \"关键词\" --json`，命中结果后再用 `python3 scripts/browser_cli.py open \"URL\" --json`",
    "浏览器 CLI 运行环境": "修复 Playwright/Chromium 运行环境，确保 `python3 scripts/browser_cli.py search \"test\"` 可执行",
    "小红书登录 Cookie / Token": "提供小红书登录 Cookie / Token，或改为公开信息版替代方案",
    "第三方数据平台 API Key": "配置新榜/蝉妈妈等第三方数据平台 API Key",
    "浏览器代理技能": "修复浏览器代理技能运行环境，或改用其他数据获取方式",
    "本地 token 服务": "恢复本地 token 服务 `http://127.0.0.1:53699/get_token`",
}

_OCLAW_HOME = Path.home() / ".openclaw"


def _iter_text_fragments(raw: object) -> Iterable[str]:
    if raw is None:
        return
    if isinstance(raw, str):
        text = raw.strip()
        if text:
            yield text
        return
    if isinstance(raw, dict):
        for value in raw.values():
            yield from _iter_text_fragments(value)
        return
    if isinstance(raw, (list, tuple, set)):
        for value in raw:
            yield from _iter_text_fragments(value)
        return
    text = str(raw).strip()
    if text:
        yield text


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" -*\t")


def _collect_evidence(texts: list[str], limit: int = 4) -> list[str]:
    evidence: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for raw_line in text.splitlines():
            line = _normalize_line(raw_line)
            if not line:
                continue
            if not (_STRUCTURED_TRIGGER_RE.search(line) or _FLOW_BLOCK_RE.search(line)):
                continue
            if line in seen:
                continue
            seen.add(line)
            evidence.append(line)
            if len(evidence) >= limit:
                return evidence
    return evidence


def _detect_missing_items(texts: list[str]) -> list[str]:
    missing: list[str] = []
    combined = "\n".join(texts)
    for label, pattern in _MISSING_RULES:
        if pattern.search(combined):
            missing.append(label)
    return missing


def _has_browser_cli_available() -> bool:
    candidates = [
        _OCLAW_HOME / "workspace-chief_of_staff" / "scripts" / "browser_cli.py",
        _OCLAW_HOME / "workspace-business_analysis" / "scripts" / "browser_cli.py",
        _OCLAW_HOME / "workspace-planning" / "scripts" / "browser_cli.py",
    ]
    return any(path.exists() for path in candidates)


def _detect_kind(texts: list[str], missing_items: list[str]) -> str:
    combined = "\n".join(texts)
    if "联网搜索技能/额度" in missing_items:
        return "search"
    if any(item in {"小红书登录 Cookie / Token", "第三方数据平台 API Key"} for item in missing_items):
        return "credential"
    if re.search(r"Service Unavailable|503|get_token|超时|timeout", combined, re.IGNORECASE):
        return "service"
    if re.search(r"签名验证失败|技能不可用|runtime", combined, re.IGNORECASE):
        return "runtime"
    return "blocked"


def _build_summary(kind: str, missing_items: list[str], fallback_reason: str) -> str:
    if kind == "search":
        if _has_browser_cli_available():
            return "联网搜索技能不可用或额度耗尽，应立即切换到浏览器 CLI"
        return "联网搜索技能不可用，且浏览器 CLI 当前不可用"
    if kind == "credential" and missing_items:
        head = "执行遇阻：缺少 API / 凭证"
        if len(missing_items) == 1:
            return f"{head}（{missing_items[0]}）"
        return head
    if kind == "service":
        return "执行遇阻：依赖服务当前不可用"
    if kind == "runtime":
        return "执行遇阻：运行环境或技能不可用"
    return fallback_reason or "执行遇阻，等待补充条件后继续"


def detect_blocker_report(payload: object) -> dict | None:
    texts = [text for text in _iter_text_fragments(payload)]
    if not texts:
        return None

    combined = "\n".join(texts)
    if not (_STRUCTURED_TRIGGER_RE.search(combined) or _FLOW_BLOCK_RE.search(combined)):
        return None

    missing_items = _detect_missing_items(texts)
    evidence = _collect_evidence(texts)
    kind = _detect_kind(texts, missing_items)
    fallback_reason = evidence[0] if evidence else ""
    summary = _build_summary(kind, missing_items, fallback_reason)
    actions = [_ACTION_MAP[item] for item in missing_items if item in _ACTION_MAP]
    if not actions and kind != "blocked":
        actions.append("确认依赖恢复后再继续执行，或调整为不依赖该能力的替代方案")

    return {
        "kind": kind,
        "summary": summary,
        "missingItems": missing_items,
        "actions": actions,
        "evidence": evidence,
        "awaitingUserAction": any(item in {"小红书登录 Cookie / Token", "第三方数据平台 API Key"} for item in missing_items),
    }


def summarize_task_blocker(task: dict) -> dict | None:
    texts: list[str] = []
    task_id = str(task.get("id") or "").strip()

    for key in ("block", "now", "output"):
        value = str(task.get(key) or "").strip()
        if not value or value in {"无", "-"}:
            continue
        texts.append(value)

    for entry in task.get("flow_log") or []:
        if not isinstance(entry, dict):
            continue
        remark = str(entry.get("remark") or "").strip()
        if remark:
            texts.append(remark)

    report = detect_blocker_report(texts)
    if report is None:
        return None

    report["taskId"] = task_id
    report["state"] = str(task.get("state") or "")
    report["org"] = str(task.get("org") or "")
    return report


def render_blocker_feedback(task: dict) -> str:
    report = summarize_task_blocker(task)
    task_id = str(task.get("id") or "").strip()
    if report is None:
        return f"{task_id or '当前任务'} 暂无结构化阻塞反馈。"

    lines = [f"📋 {task_id or '当前任务'} 当前遇阻", "", report["summary"]]

    missing_items = report.get("missingItems") or []
    if missing_items:
        lines.append("")
        lines.append("需要补充：")
        for idx, item in enumerate(missing_items, 1):
            lines.append(f"{idx}. {item}")

    actions = report.get("actions") or []
    if actions:
        lines.append("")
        lines.append("建议下一步：")
        for idx, item in enumerate(actions, 1):
            lines.append(f"{idx}. {item}")

    evidence = report.get("evidence") or []
    if evidence:
        lines.append("")
        lines.append("已识别到的阻塞线索：")
        for item in evidence[:3]:
            lines.append(f"- {item}")

    return "\n".join(lines)
