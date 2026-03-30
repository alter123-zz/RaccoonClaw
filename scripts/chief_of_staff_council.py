#!/usr/bin/env python3
"""Structured pre-dispatch council for the entry agent."""

from __future__ import annotations

import json
import re
import sys
from typing import Iterable

from intake_guard import analyze_message, _next_task_id, _title_hint
from runtime_paths import read_preferred_json
from utils import beijing_now


DEPARTMENT_RULES = (
    {
        "org": "工程研发部",
        "agent": "engineering",
        "keywords": (
            "代码", "开发", "修复", "bug", "api", "接口", "部署", "脚本", "自动化",
            "cron", "服务", "数据库", "网页", "前端", "后端", "playwright", "openclaw",
        ),
    },
    {
        "org": "品牌内容部",
        "agent": "brand_content",
        "keywords": (
            "文案", "内容", "文章", "博客", "公众号", "推文", "海报", "发帖", "雪球",
            "评论", "标题", "品牌", "传播", "朋友圈",
        ),
    },
    {
        "org": "经营分析部",
        "agent": "business_analysis",
        "keywords": (
            "经营", "财务", "分析", "数据", "报表", "测算", "成本", "营收", "利润",
            "估值", "市场", "竞品", "研究", "复盘",
        ),
    },
    {
        "org": "合规测试部",
        "agent": "compliance_test",
        "keywords": (
            "测试", "验证", "审查", "评测", "合规", "review", "qa",
        ),
    },
    {
        "org": "安全运维部",
        "agent": "secops",
        "keywords": (
            "安全", "运维", "告警", "监控", "服务器", "权限", "风控", "审计",
        ),
    },
    {
        "org": "人力组织部",
        "agent": "people_ops",
        "keywords": (
            "招聘", "人力", "组织", "绩效", "岗位", "面试", "培训",
        ),
    },
)

COMPLEXITY_KEYWORDS = {
    "跨部门": ("同时", "并且", "还要", "一边", "多部门", "协同"),
    "调研分析": ("调研", "分析", "案例", "对比", "竞品", "报告", "方案", "框架", "最新"),
    "交付要求": ("输出", "交付", "汇总", "清单", "表格", "ppt", "markdown", "报告"),
    "时效约束": ("今天", "今晚", "立刻", "马上", "尽快", "截止", "几点前"),
}

MISSING_INFO_PATTERNS = (
    (r"看看这个项目", "缺少项目链接或路径"),
    (r"帮我改一下", "缺少要修改的具体对象"),
    (r"写一篇", "缺少主题、对象或发布场景"),
    (r"分析一下", "缺少分析对象或范围"),
)

LIGHT_SPECIALIST_AGENTS = {"engineering", "brand_content", "business_analysis", "secops", "compliance_test", "people_ops"}

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

PLANNING_REQUIRED_KEYWORDS = (
    "方案", "架构", "选型", "拆解", "规划", "prd", "路线图", "需求文档",
    "技术路线", "实现方案", "产品方案",
)

PUBLICATION_KEYWORDS = (
    "发布", "发帖", "雪球", "公众号", "朋友圈", "推文", "微博", "对外", "公开", "投放",
)

REVIEW_REQUIRED_KEYWORDS = (
    "生产环境", "正式环境", "线上", "权限", "安全", "数据库", "迁移", "支付",
    "审计", "合规", "法务", "财务", "投资",
)


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    lowered = (text or "").lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _count_hits(text: str, keywords: Iterable[str]) -> int:
    lowered = (text or "").lower()
    return sum(1 for keyword in keywords if keyword.lower() in lowered)


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


def _find_completed_install_match(message: str, title_hint: str) -> dict | None:
    lowered = (message or "").lower()
    if not _contains_any(lowered, ("安装", "配置", "初始化", "依赖", "github.com")):
        return None

    repo_tokens = _extract_repo_tokens(lowered)
    title_key = _normalize_key(title_hint)
    
    # 优先从数据库查询
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


def _effective_candidate_orgs(planner: dict) -> list[str]:
    candidate_orgs = list(planner.get("candidateOrgs", []) or [])
    recommended_agent = str(planner.get("recommendedAgent") or "")
    if recommended_agent == "engineering":
        candidate_orgs = [org for org in candidate_orgs if org != "合规测试部"]
    return candidate_orgs


def _org_for_agent(agent: str) -> str:
    return AGENT_TO_ORG.get(str(agent or "").strip(), "")


def planner_pass(message: str, router: dict) -> dict:
    text = message or ""
    semantic_intent = str(router.get("semanticIntent") or "")
    direct_agent_hint = str(router.get("directAgentHint") or "")
    domain_hits: list[dict] = []
    for rule in DEPARTMENT_RULES:
        hit_count = _count_hits(text, rule["keywords"])
        if hit_count:
            domain_hits.append(
                {
                    "org": rule["org"],
                    "agent": rule["agent"],
                    "hitCount": hit_count,
                }
            )

    domain_hits.sort(key=lambda item: item["hitCount"], reverse=True)
    recommended = domain_hits[0] if domain_hits else {"org": "产品规划部", "agent": "planning", "hitCount": 0}
    if semantic_intent == "org_memory_sync":
        recommended = {"org": "工程研发部", "agent": "engineering", "hitCount": 99}
    elif router.get("classification") == "direct_execute" and direct_agent_hint in AGENT_TO_ORG:
        recommended = {
            "org": _org_for_agent(direct_agent_hint) or recommended["org"],
            "agent": direct_agent_hint,
            "hitCount": max(recommended.get("hitCount", 0), 50),
        }

    complexity_points = 0
    complexity_reasons: list[str] = []
    if len(text) >= 80:
        complexity_points += 1
        complexity_reasons.append("描述较长")
    if len(domain_hits) >= 2:
        complexity_points += 1
        complexity_reasons.append("涉及多个专业领域")
    for label, keywords in COMPLEXITY_KEYWORDS.items():
        if _contains_any(text, keywords):
            complexity_points += 1
            complexity_reasons.append(label)

    if router.get("classification") == "create_task":
        complexity_points += 1
        complexity_reasons.append("入口判定为正式任务")

    if complexity_points >= 4:
        complexity = "complex"
    elif complexity_points >= 2:
        complexity = "medium"
    else:
        complexity = "simple"

    deliverables = []
    if _contains_any(text, ("报告", "分析", "调研", "复盘")):
        deliverables.append("结构化分析")
    if _contains_any(text, ("文案", "评论", "发帖", "文章", "内容")):
        deliverables.append("内容成稿")
    if _contains_any(text, ("修复", "脚本", "部署", "接口", "自动化")):
        deliverables.append("执行结果")
    if not deliverables:
        deliverables.append("任务结果")

    return {
        "recommendedOrg": recommended["org"],
        "recommendedAgent": recommended["agent"],
        "candidateOrgs": [item["org"] for item in domain_hits[:3]],
        "complexity": complexity,
        "complexityPoints": complexity_points,
        "complexityReasons": complexity_reasons,
        "deliverables": deliverables,
        "titleHint": router.get("titleHint") or _title_hint(text),
    }


def risk_pass(message: str, router: dict, planner: dict) -> dict:
    text = message or ""
    semantic_profile = router.get("semanticProfile") if isinstance(router.get("semanticProfile"), dict) else {}
    risks: list[str] = []
    missing_info: list[str] = []
    classification = str(router.get("classification") or "")

    for pattern, reason in MISSING_INFO_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            missing_info.append(reason)

    if semantic_profile.get("coordinationNeed") == "cross_department" and classification in {"direct_handle", "direct_execute"}:
        risks.append("语义画像显示需要跨部门协同，不能按直办处理")
    if (
        semantic_profile.get("coordinationNeed") != "cross_department"
        and classification == "create_task"
    ):
        risks.append("语义画像未要求跨部门协同，不应直接进入 full 流程")
    if _contains_any(text, ("不要建任务", "别建任务")) and semantic_profile.get("coordinationNeed") == "cross_department":
        risks.append("用户要求不建任务，但语义画像显示该任务确实需要跨部门协同")

    should_escalate = bool(risks) and classification in {"direct_handle", "direct_execute"}
    needs_clarification = bool(missing_info) and classification == "create_task"

    return {
        "risks": risks,
        "missingInfo": missing_info,
        "shouldEscalate": should_escalate,
        "needsClarification": needs_clarification,
    }


def flow_plan_pass(message: str, final_route: dict, planner: dict, risk: dict) -> dict:
    classification = str(final_route.get("classification") or "")
    semantic_profile = final_route.get("semanticProfile") if isinstance(final_route.get("semanticProfile"), dict) else {}
    final_review_required = bool(semantic_profile.get("finalReviewRequired"))
    if classification == "direct_reply":
        return {
            "flowMode": "direct",
            "requiredStages": [],
            "dispatchAgent": "",
            "dispatchOrg": "",
            "initialState": "",
            "skipPlanning": True,
            "skipReview": True,
            "finalReviewRequired": False,
            "flowSummary": "直接处理，不进入正式协同链。",
        }

    if classification == "direct_handle":
        dispatch_agent = "" if classification == "direct_reply" else str(
            final_route.get("directAgentHint") or final_route.get("recommendedAgent") or ""
        )
        dispatch_org = "" if classification == "direct_reply" else str(
            _org_for_agent(dispatch_agent) or final_route.get("recommendedOrg")
        )
        return {
            "flowMode": "direct",
            "requiredStages": [],
            "dispatchAgent": dispatch_agent,
            "dispatchOrg": dispatch_org,
            "initialState": "",
            "skipPlanning": True,
            "skipReview": True,
            "finalReviewRequired": final_review_required,
            "flowSummary": "直接处理，不进入正式协同链。",
        }

    if classification == "direct_execute":
        dispatch_agent = str(final_route.get("directAgentHint") or final_route.get("recommendedAgent") or "")
        dispatch_org = str(_org_for_agent(dispatch_agent) or final_route.get("recommendedOrg"))
        return {
            "flowMode": "light",
            "requiredStages": ["dispatch", "execution"],
            "dispatchAgent": dispatch_agent,
            "dispatchOrg": dispatch_org,
            "initialState": "ChiefOfStaff",
            "skipPlanning": True,
            "skipReview": True,
            "finalReviewRequired": final_review_required,
            "flowSummary": f"总裁办完成语义理解后，直接派发给{dispatch_org or '专项部门'}执行。",
        }

    return {
        "flowMode": "full",
        "requiredStages": ["planning", "review", "dispatch", "execution"],
        "dispatchAgent": "planning",
        "dispatchOrg": "产品规划部",
        "initialState": "Planning",
        "skipPlanning": False,
        "skipReview": False,
        "finalReviewRequired": final_review_required,
        "flowSummary": "走完整协同链：产品规划 → 评审质控 → 交付运营 → 专项执行。",
    }


def _build_create_task(message: str, planner: dict, risk: dict) -> dict:
    task_id = _next_task_id(beijing_now(), "full")
    title_hint = planner.get("titleHint") or _title_hint(message)
    reasons = planner.get("complexityReasons", []) + risk.get("risks", [])
    reason = "；".join(reasons[:4]) or "总裁办会审后判定为正式协同任务"
    return {
        "classification": "create_task",
        "shouldCreateTask": True,
        "reason": reason,
        "replyText": "已收到需求，总裁办正在整理需求，稍候转交产品规划部处理。",
        "taskId": task_id,
        "titleHint": title_hint,
        "progressText": "总裁办会审后判定为正式需求，正在整理并准备建单",
        "progressPlan": "总裁办会审✅|整理需求🔄|创建任务|转交产品规划部",
        "guardrail": "会审已判定为正式协同任务；禁止跳过建单直接搜索或直接产出最终内容。",
        "routeMode": "create_task",
    }


def chief_pass(message: str, router: dict, planner: dict, risk: dict) -> dict:
    final = dict(router)
    classification = router.get("classification")
    completed_install = _find_completed_install_match(message, planner.get("titleHint") or "")

    if classification == "direct_handle" and completed_install:
        output_path = completed_install.get("output") or completed_install.get("now") or "已有完成记录"
        final["reason"] = (
            f"检测到同类安装任务已完成（{completed_install.get('taskId') or '历史任务'}），"
            "应直接复用结果，不需要重新建单。"
        )
        final["replyText"] = (
            "已检查到同类安装任务已完成，总裁办直接复用历史结果，不再重复创建任务。"
        )
        final["progressText"] = "命中重复安装历史记录，总裁办直接返回已有结果"
        final["progressPlan"] = "消息分诊✅|检查历史结果✅|直接回传"
        final["guardrail"] = (
            "禁止创建 JJC；禁止 flow；禁止转产品规划部。若历史结果失效，再按直办重新安装。"
        )
        final["historicalMatch"] = completed_install
        final["chiefDecision"] = "direct_handle"
        final["chiefSummary"] = f"命中历史完成记录，直接复用：{output_path}"
        final["recommendedOrg"] = planner.get("recommendedOrg")
        final["recommendedAgent"] = planner.get("recommendedAgent")
        final["deliverables"] = planner.get("deliverables", [])
        final["missingInfo"] = risk.get("missingInfo", [])
        final.update(flow_plan_pass(message, final, planner, risk))
        return final

    if classification in {"direct_handle", "direct_execute"}:
        if risk.get("shouldEscalate"):
            final = _build_create_task(message, planner, risk)
            final["chiefDecision"] = "escalated_to_task"
            final["chiefSummary"] = "会审发现语义画像与当前分诊不一致，升级为正式任务。"
        else:
            final["chiefDecision"] = classification
            final["chiefSummary"] = (
                "会审确认该任务可由总裁办直接处理。"
                if classification == "direct_handle"
                else "会审确认该任务可由总裁办直接派给单一专项部门处理。"
            )
    elif classification == "create_task":
        final["chiefDecision"] = "create_task"
        final["chiefSummary"] = "会审确认该任务需要正式协同链。"
    else:
        final["chiefDecision"] = "direct_reply"
        final["chiefSummary"] = "会审确认该消息属于短确认，可直接回复。"

    final["recommendedOrg"] = planner.get("recommendedOrg")
    final["recommendedAgent"] = planner.get("recommendedAgent")
    final["deliverables"] = planner.get("deliverables", [])
    final["missingInfo"] = risk.get("missingInfo", [])
    final.update(flow_plan_pass(message, final, planner, risk))
    return final


def analyze_with_council(message: str) -> dict:
    router = analyze_message(message)
    planner = planner_pass(message, router)
    risk = risk_pass(message, router, planner)
    chief = chief_pass(message, router, planner, risk)
    return {
        **chief,
        "council": {
            "router": {
                "classification": router.get("classification"),
                "reason": router.get("reason"),
                "routeMode": router.get("routeMode"),
                "semanticIntent": router.get("semanticIntent"),
                "semanticProfile": router.get("semanticProfile"),
            },
            "planner": planner,
            "risk": risk,
            "chief": {
                "decision": chief.get("chiefDecision"),
                "summary": chief.get("chiefSummary"),
            },
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "message required",
                    "usage": 'python3 scripts/chief_of_staff_council.py "用户原话"',
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    payload = analyze_with_council(" ".join(argv[1:]))
    payload["ok"] = True
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
