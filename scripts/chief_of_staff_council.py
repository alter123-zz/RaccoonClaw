#!/usr/bin/env python3
"""Mechanical helpers for the CEO Office agent.

This script used to contain a keyword-based 4-pass "council" classification
pipeline. Classification is now done by the agent's native semantic
understanding (see agents/chief_of_staff/SOUL.md).

This script provides mechanical operations:
  gen-id <direct|light|full>   — generate the next sequential task ID
  title-hint <message>         — generate a title suggestion from user text
  check-install <message>      — check for completed duplicate install tasks

Backward-compatible deprecated stubs are retained for callers that import
analyze_with_council() or analyze_message() programmatically.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Iterable

from runtime_paths import read_preferred_json
from task_ids import next_task_id
from utils import beijing_now


# ---------------------------------------------------------------------------
# Agent-to-org mapping (retained for check-install and deprecated stubs)
# ---------------------------------------------------------------------------

AGENT_TO_ORG = {
    "planning": "产品规划部",
    "engineering": "工程研发部",
    "brand_content": "品牌内容部",
    "business_analysis": "经营分析部",
    "compliance_test": "合规测试部",
    "secops": "安全运维部",
    "people_ops": "人力组织部",
    "chief_of_staff": "总裁办",
}


def _org_for_agent(agent: str) -> str:
    return AGENT_TO_ORG.get(str(agent or "").strip(), "")


# ---------------------------------------------------------------------------
# Text utilities (localized from intake_guard)
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    value = (text or "").strip()
    value = value.replace("\r", "\n")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _compact_text(text: str) -> str:
    value = _normalize_text(text)
    value = re.sub(r"^(请|麻烦|帮我|给我|请你|需要你|想让你)+\s*", "", value)
    value = re.sub(r"[。！？!?,，；;：:]+$", "", value)
    return value.strip()


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (text or "").lower())


def _extract_repo_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for owner, repo in re.findall(r"github\.com/([^/\s]+)/([^/\s?#]+)", text, flags=re.IGNORECASE):
        for token in (owner, repo):
            token = token.strip().lower()
            if token and token not in tokens:
                tokens.append(token)
    return tokens


def _pick_named_tokens(text: str) -> list[str]:
    candidates = re.findall(r"[A-Za-z][A-Za-z0-9.+-]{1,24}", text)
    keep: list[str] = []
    for token in candidates:
        if token.lower() in {"report", "analysis", "compare", "comparison", "multi", "agent"}:
            continue
        if token not in keep:
            keep.append(token)
    return keep


def _title_hint(text: str) -> str:
    compact = _compact_text(text)
    named = _pick_named_tokens(compact)
    lowered = compact.lower()

    if all(name.lower() in lowered for name in ("crewai", "autogen", "langgraph")):
        return "分析 CrewAI、AutoGen、LangGraph 多 Agent 框架"

    if ("对比" in compact or "compare" in lowered or "comparison" in lowered) and len(named) >= 2:
        return f"对比 {named[0]} 与 {named[1]} 方案差异"

    if ("分析" in compact or "analyze" in lowered or "analysis" in lowered) and named:
        head = "、".join(named[:3])
        suffix = "多 Agent 框架" if any(k in compact.lower() for k in ("agent", "框架")) else "方案"
        return f"分析 {head} {suffix}".strip()

    compact = re.sub(r"^(分析|调研|对比|整理|总结|写|输出|生成|处理)", "", compact).strip()
    compact = compact[:30]
    return compact or "整理需求并转交总裁办"


# ---------------------------------------------------------------------------
# Install duplicate detection (retained mechanical check)
# ---------------------------------------------------------------------------

def _find_completed_install_match(message: str, title_hint: str) -> dict | None:
    lowered = (message or "").lower()
    if not any(k in lowered for k in ("安装", "配置", "初始化", "依赖", "github.com")):
        return None

    repo_tokens = _extract_repo_tokens(lowered)
    title_key = _normalize_key(title_hint)

    try:
        from db_sync import list_tasks_sync
        tasks = list_tasks_sync()
    except Exception:
        tasks = read_preferred_json("tasks_source.json", [])

    for item in tasks:
        if str(item.get("state", "")).strip() != "Done":
            continue
        haystack = " ".join(
            str(item.get(field, ""))
            for field in ("title", "now", "output", "detail")
        ).lower()
        haystack_key = _normalize_key(haystack)
        title_match = bool(title_key and title_key in haystack_key)
        repo_match = bool(repo_tokens) and sum(token in haystack for token in repo_tokens) >= 1
        if not title_match and not repo_match:
            continue
        return {
            "taskId": str(item.get("id", "")).strip(),
            "title": str(item.get("title", "")).strip(),
            "output": str(item.get("output", "")).strip(),
            "now": str(item.get("now", "")).strip(),
        }
    return None


# ---------------------------------------------------------------------------
# Subcommand: gen-id
# ---------------------------------------------------------------------------

def _gen_task_id(flow_mode: str) -> dict:
    existing_ids = [
        str(item.get("id", "")).strip()
        for item in read_preferred_json("tasks_source.json", [])
    ]
    now = beijing_now()
    task_id = next_task_id(now, flow_mode, existing_ids)
    return {"ok": True, "taskId": task_id, "flowMode": flow_mode}


# ---------------------------------------------------------------------------
# Subcommand: title-hint
# ---------------------------------------------------------------------------

def _cmd_title_hint(message: str) -> dict:
    return {"ok": True, "titleHint": _title_hint(message)}


# ---------------------------------------------------------------------------
# Subcommand: check-install
# ---------------------------------------------------------------------------

def _cmd_check_install(message: str) -> dict:
    hint = _title_hint(message)
    result = _find_completed_install_match(message, hint)
    if result:
        return {"ok": True, "duplicate": True, "match": result}
    return {"ok": True, "duplicate": False}


# ---------------------------------------------------------------------------
# Subcommand: triage (lightweight forcing step for semantic classification)
# ---------------------------------------------------------------------------

def _cmd_triage(message: str) -> dict:
    """Return helper info to force the agent to stop and think before classifying.

    The agent does the actual semantic classification itself.
    This just provides mechanical assistance (title hint, install check).
    """
    hint = _title_hint(message)
    install_check = _find_completed_install_match(message, hint)
    compact = _normalize_text(message).lower()
    is_short_chat = len(_normalize_text(message)) <= 10 and not any(
        k in compact for k in ("写", "分析", "调研", "对比", "设计", "修复", "检查", "整理", "配置", "安装", "部署", "帮", "要", "需要", "请")
    )
    return {
        "ok": True,
        "titleHint": hint,
        "installDuplicate": bool(install_check),
        "installMatch": install_check,
        "looksLikeShortChat": is_short_chat,
        "note": (
            "⚠️ 你必须严格按以下规则行动，禁止跳过任何步骤：\n"
            "1. 如果消息是简短寒暄（你好/谢谢/收到等），直接回复一句话，禁止做其他任何事情。\n"
            "2. 如果消息要求产出内容（写文章/写文案/写报告/写代码/分析/调研/设计等），"
            "这是专业任务，你禁止自己执行。必须走轻流程建单，派给对应部门。\n"
            "3. 只有以下情况你可以自己处理：安装配置环境变量、改一句话措辞。\n"
            "4. 建单时必须调用 kanban_update.py create，不能只说'已安排'。\n"
            "5. 禁止自己撰写文章、报告、分析等长内容。"
        ),
    }


# ---------------------------------------------------------------------------
# DEPRECATED stubs for backward compatibility
# ---------------------------------------------------------------------------

def analyze_with_council(message: str) -> dict:
    """DEPRECATED: Classification is now done by the agent's semantic understanding.

    This function exists only for backward compatibility with callers that
    import it programmatically (legacy_server_bridge, dashboard).
    It returns a minimal valid payload indicating the message should be handled
    by the agent's own semantic classification.
    """
    # Return empty classification so the dashboard falls through to calling
    # the agent directly.  The agent will do semantic classification itself.
    return {
        "ok": True,
        "classification": "",
        "shouldCreateTask": False,
        "reason": "分类已由代理语义理解完成，此函数仅保留兼容性。",
        "flowMode": "",
        "requiredStages": [],
        "dispatchAgent": "",
        "dispatchOrg": "",
        "skipPlanning": True,
        "skipReview": True,
        "finalReviewRequired": False,
        "flowSummary": "语义分类已由代理完成。",
        "replyText": "",
        "taskId": "",
        "titleHint": _title_hint(message),
        "progressText": "",
        "progressPlan": "",
        "guardrail": "代理已自行完成语义分类。",
        "routeMode": "",
        "semanticIntent": "chat",
        "semanticProfile": {
            "shape": "chat",
            "taskShape": "chat",
            "semanticIntent": "chat",
            "coordinationNeed": "none",
            "canChiefHandle": True,
        },
        "directAgentHint": "",
        "council": {
            "router": {
                "classification": "",
                "reason": "废弃桩：分类由代理语义理解完成。",
                "routeMode": "",
                "semanticIntent": "chat",
                "semanticProfile": {
                    "shape": "chat",
                    "semanticIntent": "chat",
                    "coordinationNeed": "none",
                    "canChiefHandle": True,
                },
            },
            "planner": {
                "recommendedOrg": "",
                "recommendedAgent": "",
                "candidateOrgs": [],
                "complexity": "simple",
                "complexityPoints": 0,
                "complexityReasons": [],
                "deliverables": [],
                "titleHint": _title_hint(message),
            },
            "risk": {"risks": [], "missingInfo": [], "shouldEscalate": False, "needsClarification": False},
            "chief": {"decision": "", "summary": "废弃桩：分类由代理语义理解完成。"},
        },
    }


# Import intake_guard.analyze_message for any code that reaches council
# and then calls the guard.  The stub version is safe.
from intake_guard import analyze_message  # noqa: E402, F401


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Mechanical helpers for the CEO Office agent. "
        "Classification is done by the agent's semantic understanding.",
    )
    sub = parser.add_subparsers(dest="cmd")

    gen = sub.add_parser("gen-id", help="Generate next sequential task ID")
    gen.add_argument("flow_mode", choices=["direct", "light", "full"])

    triage = sub.add_parser("triage", help="Triage assist: title hint + install check")
    triage.add_argument("message", help="User message text")

    title = sub.add_parser("title-hint", help="Generate a title suggestion from message text")
    title.add_argument("message", help="User message text")

    check = sub.add_parser("check-install", help="Check for completed duplicate install tasks")
    check.add_argument("message", help="User message text")

    args = parser.parse_args(argv[1:])

    if args.cmd == "gen-id":
        result = _gen_task_id(args.flow_mode)
    elif args.cmd == "triage":
        result = _cmd_triage(args.message)
    elif args.cmd == "title-hint":
        result = _cmd_title_hint(args.message)
    elif args.cmd == "check-install":
        result = _cmd_check_install(args.message)
    else:
        parser.print_help()
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
