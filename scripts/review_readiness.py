#!/usr/bin/env python3
"""Shared heuristics for deciding whether a task is ready for review_control review."""

from __future__ import annotations

import re
from typing import Any

try:
    from plan_guard import build_feedback as build_plan_feedback
except Exception:  # pragma: no cover - optional import safety
    build_plan_feedback = None

try:
    from review_rubric import evaluate_plan as evaluate_plan_with_rubric
    from workbench_modes import infer_mode_id_for_task
except Exception:  # pragma: no cover - optional import safety
    evaluate_plan_with_rubric = None
    infer_mode_id_for_task = None


READY_MARKERS = (
    "方案已起草",
    "方案起草完成",
    "提交评审",
    "提交审议",
    "准备提交评审",
    "送审",
)

SUBSTANCE_MARKERS = (
    "子任务",
    "分工",
    "执行方案",
    "实施方案",
    "派发",
    "部门",
    "验收",
    "风险",
    "资源",
    "排期",
    "流程",
    "评审",
    "交付",
    "拆解",
    "阶段",
)

GENERIC_PROGRESS_MARKERS = (
    "分析需求",
    "整理需求",
    "制定方案",
    "起草方案",
    "规划方案",
)

PATH_LIKE_RE = re.compile(r"^(?:\.{0,2}/|/|[A-Za-z]:\\).+\.(?:md|txt|json|csv|py|ts|js|html|css)$")
STRUCTURED_PLAN_RE = re.compile(r"(^|\n)\s*(?:\d+[.)、]|\|\s*\d+\s*\|)")


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _progress_entries(task: dict[str, Any], agent_id: str) -> list[dict[str, Any]]:
    progress_log = task.get("progress_log") or []
    if not isinstance(progress_log, list):
        return []
    return [
        row for row in progress_log
        if isinstance(row, dict) and (row.get("agent") or "").strip() == agent_id
    ]


def _meaningful_output(output_text: str) -> bool:
    text = _normalize_text(output_text)
    if len(text) < 40:
        return False
    if PATH_LIKE_RE.match(text) and "\n" not in text:
        return False
    return True


def build_plan_excerpt(task: dict[str, Any]) -> str:
    parts: list[str] = []

    output_text = _normalize_text(task.get("output"))
    if _meaningful_output(output_text):
        parts.append(output_text)

    for row in _progress_entries(task, "planning"):
        text = _normalize_text(row.get("text"))
        if text:
            parts.append(text)
        todos = row.get("todos") or []
        if isinstance(todos, list):
            completed_titles = [
                _normalize_text(item.get("title"))
                for item in todos
                if isinstance(item, dict)
                and item.get("status") in ("completed", "in-progress")
                and _normalize_text(item.get("title"))
            ]
            if completed_titles:
                parts.append(" / ".join(completed_titles))

    flow_log = task.get("flow_log") or []
    if isinstance(flow_log, list):
        for row in flow_log:
            if not isinstance(row, dict):
                continue
            if (row.get("from") or "").strip() != "产品规划部":
                continue
            remark = _normalize_text(row.get("remark"))
            if remark:
                parts.append(remark)

    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part or part in seen:
            continue
        seen.add(part)
        deduped.append(part)
    return "\n".join(deduped)


def evaluate_review_readiness(task: dict[str, Any]) -> dict[str, Any]:
    planning_entries = _progress_entries(task, "planning")
    planning_texts = [_normalize_text(row.get("text")) for row in planning_entries if _normalize_text(row.get("text"))]
    plan_excerpt = build_plan_excerpt(task)
    feedback: list[str] = []

    has_ready_signal = any(any(marker in text for marker in READY_MARKERS) for text in planning_texts)
    has_substantive_signal = any(any(marker in text for marker in SUBSTANCE_MARKERS) for text in planning_texts)

    if not planning_entries:
        feedback.append("产品规划部尚未留下任何方案进展，禁止直接送审。")
    elif not has_ready_signal:
        feedback.append("产品规划部尚未明确提交“方案已起草/提交评审”，禁止推进到评审质控部。")
    elif not has_substantive_signal:
        generic_only = all(any(marker in text for marker in GENERIC_PROGRESS_MARKERS) for text in planning_texts)
        has_structured_plan = bool(STRUCTURED_PLAN_RE.search(plan_excerpt))
        if generic_only and not has_structured_plan and not _meaningful_output(_normalize_text(task.get("output"))):
            feedback.append("当前只有泛化进展描述，缺少可审议的方案内容或结构化拆解。")

    if build_plan_feedback and plan_excerpt:
        has_structured_research_plan = (
            bool(STRUCTURED_PLAN_RE.search(plan_excerpt))
            or any(dept in plan_excerpt for dept in ("工程研发部", "经营分析部", "品牌内容部", "安全运维部"))
        )
        requirement = _normalize_text(task.get("title"))
        if requirement and has_structured_research_plan:
            payload = build_plan_feedback(requirement, plan_excerpt)
            if payload.get("isResearchTask") and not payload.get("ok"):
                for item in payload.get("feedback", []):
                    if item not in feedback:
                        feedback.append(item)

    if evaluate_plan_with_rubric and infer_mode_id_for_task and plan_excerpt:
        mode_id = infer_mode_id_for_task(task)
        rubric_result = evaluate_plan_with_rubric(plan_excerpt, mode_id=mode_id, requirement=_normalize_text(task.get("title")))
        if not rubric_result.get("ok"):
            for item in rubric_result.get("missingFindings", []):
                message = _normalize_text(item.get("message"))
                if message and message not in feedback:
                    feedback.append(message)

    return {
        "ok": not feedback,
        "feedback": feedback,
        "planningProgressCount": len(planning_entries),
        "hasReadySignal": has_ready_signal,
        "hasSubstantiveSignal": has_substantive_signal,
        "planExcerpt": plan_excerpt,
    }
