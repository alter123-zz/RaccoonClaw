#!/usr/bin/env python3
"""Deterministic checks for final delivery quality on research/comparison tasks."""

from __future__ import annotations

import argparse
import json
import sys


RESEARCH_KEYWORDS = ("调研", "案例", "对比", "竞品", "趋势", "框架", "报告", "分析", "推荐场景")
FAILURE_KEYWORDS = (
    "无法联网",
    "网络访问受限",
    "网络搜索服务暂不可用",
    "搜索服务暂不可用",
    "未找到相关信息",
    "web search",
    "rate limit",
    "限流",
    "请求失败",
)
FINDING_KEYWORDS = (
    "关键发现",
    "对比",
    "结论",
    "推荐",
    "推荐场景",
    "适用场景",
    "架构",
    "通信",
    "编排",
    "可观测",
    "学习曲线",
    "量化",
    "已确认",
)
SOURCE_KEYWORDS = (
    "来源",
    "资料",
    "GitHub",
    "版本",
    "Issue",
    "Stars",
    "文档",
    "社区",
    "引用",
)
GAP_KEYWORDS = (
    "待验证",
    "缺失来源",
    "补充数据源",
    "限制说明",
    "待补充",
    "进一步核验",
    "下一步",
)


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def build_feedback(requirement: str, report: str) -> dict:
    requirement = requirement or ""
    report = report or ""

    is_research = contains_any(requirement, RESEARCH_KEYWORDS)
    if not is_research:
        return {
            "ok": True,
            "isResearchTask": False,
            "feedback": [],
        }

    feedback: list[str] = []
    stripped = report.strip()

    has_failure = contains_any(stripped, FAILURE_KEYWORDS)
    has_findings = contains_any(stripped, FINDING_KEYWORDS)
    has_sources = contains_any(stripped, SOURCE_KEYWORDS)
    has_gaps = contains_any(stripped, GAP_KEYWORDS)

    if len(stripped) < 120:
        feedback.append("最终交付过短，研究类任务至少应给出结构化结论和关键发现。")
    if not has_findings:
        feedback.append("缺少明确的对比结论/关键发现，不能只写过程或空泛说明。")
    if not has_sources:
        feedback.append("缺少来源或量化依据提示，无法说明结论基于哪些资料。")
    if has_failure and not has_gaps:
        feedback.append("出现联网/搜索失败时，必须先切到浏览器 CLI 或补充待验证项、缺失来源和下一步建议。")
    if has_failure and not has_findings:
        feedback.append("即使搜索失败，也必须先给出已确认信息和初步结论，不能只报错。")

    return {
        "ok": not feedback,
        "isResearchTask": True,
        "hasFailureSignals": has_failure,
        "hasFindings": has_findings,
        "hasSources": has_sources,
        "hasGapHandling": has_gaps,
        "feedback": feedback,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate final delivery quality")
    parser.add_argument("--requirement", required=True, help="Original requirement text")
    parser.add_argument("--report", required=True, help="Compiled final report text")
    parser.add_argument("--json", action="store_true", help="Print JSON payload")
    args = parser.parse_args(argv[1:])

    payload = build_feedback(args.requirement, args.report)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print("通过" if payload["ok"] else "打回")
        for item in payload["feedback"]:
            print(f"- {item}")
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
