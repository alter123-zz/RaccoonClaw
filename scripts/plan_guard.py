#!/usr/bin/env python3
"""Deterministic checks for planning quality on research/comparison tasks."""

from __future__ import annotations

import argparse
import json
import re
import sys


RESEARCH_KEYWORDS = ("调研", "案例", "对比", "竞品", "趋势", "框架", "报告", "分析")

DIMENSION_KEYWORDS = {
    "架构设计": ("架构", "architecture"),
    "Agent通信方式": ("通信", "消息", "message", "group chat", "state"),
    "任务编排能力": ("编排", "workflow", "state machine", "流程", "graph"),
    "可观测性": ("可观测", "trace", "监控", "观测", "observability", "日志"),
    "学习曲线": ("学习曲线", "上手", "hello world", "入门", "learning curve"),
    "推荐场景": ("推荐", "场景", "适用", "适合", "结论"),
}

DEPARTMENT_ALIASES = {
    "工程研发部": ("工程研发部", "engineering"),
    "安全运维部": ("安全运维部", "secops"),
    "经营分析部": ("经营分析部", "business_analysis"),
    "品牌内容部": ("品牌内容部", "brand_content"),
}


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def requested_dimensions(requirement: str) -> list[str]:
    dims = [name for name, aliases in DIMENSION_KEYWORDS.items() if contains_any(requirement, aliases)]
    return dims


def mentioned_departments(plan: str) -> set[str]:
    hits: set[str] = set()
    for dept, aliases in DEPARTMENT_ALIASES.items():
        if contains_any(plan, aliases):
            hits.add(dept)
    return hits


def numbered_items_count(plan: str) -> int:
    line_hits = sum(
        1
        for line in plan.splitlines()
        if re.match(r"^\s*(?:\d+[.)、]|\|\s*\d+\s*\|)", line.strip())
    )
    inline_hits = len(re.findall(r"(?:^|\s)(\d+[.)、])\s*", plan))
    return max(line_hits, inline_hits)


def build_feedback(requirement: str, plan: str) -> dict:
    is_research = contains_any(requirement, RESEARCH_KEYWORDS)
    dims = requested_dimensions(requirement)
    missing_dims = [name for name in dims if not contains_any(plan, DIMENSION_KEYWORDS[name])]
    departments = mentioned_departments(plan)
    missing_departments: list[str] = []
    feedback: list[str] = []

    if is_research:
        tech_present = any(name in departments for name in ("工程研发部", "安全运维部"))
        if not tech_present:
            missing_departments.append("工程研发部/安全运维部")
            feedback.append("缺少技术专项子任务，无法覆盖架构/通信/编排/可观测性等技术维度。")
        if "经营分析部" not in departments:
            missing_departments.append("经营分析部")
            feedback.append("缺少经营分析部子任务，量化数据、版本节奏、社区活跃度没有明确负责人。")
        if "品牌内容部" not in departments:
            missing_departments.append("品牌内容部")
            feedback.append("缺少品牌内容部子任务，最终结构化报告和推荐场景没有明确交付人。")
        if numbered_items_count(plan) < 3:
            feedback.append("方案拆解粒度过粗，研究型任务至少应拆成 3 个可派发子任务。")
        if len(departments) < 2:
            feedback.append("方案没有把子任务和部门绑定，仍然像泛化的“三步流程”。")

    for name in missing_dims:
        feedback.append(f"缺少“{name}”维度覆盖。")

    if contains_any(requirement, DIMENSION_KEYWORDS["推荐场景"]) and "推荐场景" in missing_dims:
        feedback.append("用户明确要结论或推荐场景，不能只有分析没有结论。")

    ok = not feedback
    return {
        "ok": ok,
        "isResearchTask": is_research,
        "requestedDimensions": dims,
        "missingDimensions": missing_dims,
        "departments": sorted(departments),
        "missingDepartments": missing_departments,
        "feedback": feedback,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate research/comparison task plans")
    parser.add_argument("--requirement", required=True, help="Original requirement text")
    parser.add_argument("--plan", required=True, help="Proposed execution plan text")
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    args = parser.parse_args(argv[1:])

    payload = build_feedback(args.requirement, args.plan)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print("通过" if payload["ok"] else "打回")
        for item in payload["feedback"]:
            print(f"- {item}")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
