#!/usr/bin/env python3
"""DEPRECATED: Intake Guard — Keyword Classification Engine

This module's keyword-based classification logic has been replaced by the
CEO Office agent's native semantic understanding. The module is preserved
as a thin stub for backward compatibility with import chains.

Classification is now done by the agent (LLM) directly, guided by the
semantic descriptions in agents/chief_of_staff/SOUL.md.

The keyword tuples and classification functions below have been removed.
Only utility functions retained for use by other modules.
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
from typing import Iterable

from runtime_paths import read_preferred_json
from task_ids import next_task_id
from utils import beijing_now


# ---------------------------------------------------------------------------
# Utility functions (retained — used by chief_of_staff_council.py and others)
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


def _semantic_compact(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (text or "").lower())


def _next_task_id(now: _dt.datetime, flow_mode: str = "full") -> str:
    existing_ids = [str(item.get("id", "")).strip() for item in read_preferred_json("tasks_source.json", [])]
    return next_task_id(now, flow_mode, existing_ids)


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
# DEPRECATED: Classification stub
# ---------------------------------------------------------------------------

def analyze_message(text: str) -> dict:
    """DEPRECATED: Classification is now handled by the agent's semantic understanding.

    Returns a neutral default that signals "let the agent decide".
    """
    return {
        "classification": "",
        "shouldCreateTask": False,
        "reason": "分类已由代理语义理解完成。",
        "replyText": "",
        "taskId": "",
        "titleHint": _title_hint(text),
        "progressText": "",
        "progressPlan": "",
        "guardrail": "代理已自行完成语义分类。",
        "routeMode": "",
        "semanticIntent": "chat",
        "semanticProfile": {
            "shape": "chat",
            "taskShape": "chat",
            "semanticIntent": "chat",
            "thingIs": "chat",
            "needsSpecialist": False,
            "specialistAgent": "",
            "coordinationNeed": "none",
            "canChiefHandle": True,
            "artifactBased": False,
            "contentOutput": False,
            "reviewTask": False,
            "needsReview": False,
            "finalReviewRequired": False,
            "needsPlanning": False,
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point (kept for backward compat — always returns stub)
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            '{\n  "ok": false,\n  "error": "message required",\n'
            '  "note": "intake_guard classification is deprecated. '
            "Use agent's semantic understanding instead.\"\n}"
        )
        return 1

    payload = analyze_message(" ".join(argv[1:]))
    payload["ok"] = True
    import json
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
