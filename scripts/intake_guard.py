#!/usr/bin/env python3
"""Deterministic intake guard for the chief-of-staff entrypoint."""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from typing import Iterable

from runtime_paths import read_preferred_json
from task_ids import next_task_id
from utils import beijing_now


DIRECT_REPLY_PATTERNS = (
    r"^(好|好的|好嘞|好呀|收到|收到啦|了解|明白|知道了|辛苦了|谢谢|谢了|谢啦|thanks|thank you|ok|okay|好的收到)$",
    r"^(继续|开始吧|往下做|继续做)$",
    r"^(不是这个|不是这个意思|不对|错了|改一下|重来)$",
    r"^(嗯|哦|哦哦|哈哈|哈哈哈|行|可以|没问题)$",
)

ACTION_KEYWORDS = (
    "做", "查", "看", "修", "修复", "处理", "安排", "接口", "调研", "分析", "写", "整理", "总结", "对比", "设计", "修改",
    "优化", "规划", "部署", "评估", "复盘", "列一下", "汇总", "梳理", "研究", "产出",
    "report", "analyze", "analysis", "compare", "comparison", "research", "review", "plan",
)

DELIVERABLE_KEYWORDS = (
    "报告", "方案", "清单", "建议", "步骤", "表格", "文案", "框架", "对比报告", "调研报告",
    "执行计划", "汇报", "总结", "ppt", "markdown", "表", "report", "plan", "table",
)

AUTOMATION_MARKERS = (
    "cron", "定时", "定时任务", "自动化", "整点", "schedule", "scheduled", "每小时", "每天", "每周", "run",
)

DIRECT_EXECUTE_MARKERS = (
    "直接输出最终内容",
    "只输出整理好的内容",
    "不要自行发送消息",
    "运行抓取脚本",
    "执行以下任务",
    "整理输出格式",
    "整理成以下格式",
    "最终内容供投递",
    "一步执行",
    "直接安排",
)

BASIC_DIRECT_MARKERS = (
    "翻译", "润色", "改标题", "改一下标题", "改措辞", "提炼一句",
    "一句话总结", "简短总结", "改成更口语", "改成更正式",
    "更口语", "更正式", "口语一点", "正式一点",
)

LOOKUP_DIRECT_TARGET_KEYWORDS = (
    "天气", "气温", "温度", "下雨", "降雨", "温差",
    "时间", "日期", "星期", "几号", "几号了",
)

CONTENT_OUTPUT_KEYWORDS = (
    "文案", "标题", "摘要", "周报", "周报摘要", "海报", "报名引导语", "话术", "说明", "提纲",
    "朋友圈", "公众号", "推文",
)

ARTIFACT_INPUT_MARKERS = (
    "基于这份", "根据这份", "按这份", "按照这份",
    "基于这个", "根据这个", "按这个", "按照这个",
    "这段采访", "这份采访", "这份活动方案", "这份合作方案", "这份方案", "这段内容",
)

REVIEW_TASK_KEYWORDS = (
    "风险", "明显风险", "风险点", "合规", "审查", "评审", "审核", "把关",
)

SIMPLE_TASK_HINT_KEYWORDS = (
    "改", "改成", "改得", "改一下", "改得更", "写", "整理", "生成", "输出",
    "给我", "来一版", "一版", "一段", "一句", "标题", "文案", "摘要", "说明",
    "修复", "修一下", "查询", "查", "看看", "给可发版本", "直接给可发版本",
)

SIMPLE_TASK_BLOCKERS = (
    "报告", "方案", "框架", "对比", "调研", "研究", "复盘", "路线图", "prd", "架构",
    "公开发布", "对外", "生产环境", "正式环境", "迁移", "权限", "合规", "法务", "财务",
    "支付", "新闻", "最佳实践", "竞品", "市场", "技术选型", "长期规划",
)

SETUP_DIRECT_KEYWORDS = (
    "安装", "配置", "配置下", "配置一下", "登录", "授权", "接入", "接好",
    "环境检查", "检查环境", "初始化", "启动", "跑起来", "本地运行", "依赖",
    "补依赖", "修依赖", "修复依赖", "sdk", "api key", "apikey", "token",
    "cookie", "账号登录",
)

SETUP_DIRECT_BLOCKERS = (
    "方案", "架构", "调研", "报告", "对比", "最佳实践", "迁移", "集群",
    "生产环境", "正式环境", "上线方案", "技术选型", "长期规划",
)

MEMORY_SYNC_SCOPE_KEYWORDS = (
    "所有agent", "每个agent", "全体agent", "全部agent", "所有智能体", "每个智能体",
    "全员", "所有部门", "每个部门", "统一写入", "统一同步", "批量同步", "批量更新",
    "统一补充", "统一追加", "全量同步", "写进记忆", "写入记忆", "更新记忆",
)

MEMORY_SYNC_TARGET_KEYWORDS = (
    "记忆", "memory", "soul", "提示词", "规则", "联网工具", "cli浏览器", "browser_cli",
    "soul.md", "能力说明", "统一配置", "agent配置", "工作记忆", "执行规范", "工作规范", "统一规范",
    "部门职责", "职责说明", "角色边界", "职责边界", "分工边界", "协作边界", "边界规则",
    "工具白名单", "工具黑名单", "禁用某类工具", "禁用工具", "停用工具", "工具治理", "工具策略",
    "浏览器cli", "浏览器回退", "回退链路", "联网回退", "搜索skill", "skill", "zhipu-web-search",
)

RESEARCH_KEYWORDS = (
    "案例", "盘点", "对比", "榜单", "趋势", "市场", "竞品", "最佳实践", "最新", "今年",
    "过去", "实时", "联网", "框架", "技术选型", "多 agent", "multi agent", "crewai",
    "autogen", "langgraph",
)

CHAT_PREFIXES = ("好", "收到", "继续", "谢谢", "辛苦", "可以", "行", "不是这个")
ACK_TOKENS = {
    "好", "好的", "收到", "继续", "谢谢", "辛苦了", "可以", "行",
    "不是这个", "不是这个意思", "不对", "错了", "改一下", "重来",
}


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


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.fullmatch(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _looks_like_direct_reply(text: str) -> bool:
    normalized = _normalize_text(text)
    compact = re.sub(r"[。！？!?,，；;：:\s]+", "", normalized)
    if not compact:
        return True
    if len(normalized) > 24:
        return False
    if _matches_any(normalized.lower(), DIRECT_REPLY_PATTERNS):
        return True
    parts = [part.strip() for part in re.split(r"[。！？!?,，；;：:\s]+", normalized) if part.strip()]
    if parts and len(parts) <= 3 and all(part in ACK_TOKENS for part in parts):
        return True
    return compact in CHAT_PREFIXES


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _direct_agent_hint(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("风险", "合规", "审查", "评审", "审核", "把关")):
        return "compliance_test"
    if any(token in lowered for token in (
        "agent", "智能体", "记忆", "memory", "soul", "提示词", "联网工具", "cli浏览器", "browser_cli",
        "部门职责", "职责说明", "角色边界", "职责边界", "分工边界", "协作边界", "边界规则",
        "禁用工具", "停用工具", "工具治理", "工具策略",
    )):
        return "engineering"
    if any(token in lowered for token in ("代码", "脚本", "部署", "自动化", "接口", "openclaw", "gateway", "服务")):
        return "engineering"
    if any(token in lowered for token in ("文案", "文章", "博客", "标题", "改写", "润色", "内容")):
        return "brand_content"
    if any(token in lowered for token in ("分析", "报表", "数据", "市场", "调研")):
        return "business_analysis"
    return "chief_of_staff"


def _is_direct_execute(text: str) -> bool:
    automation_hit = _contains_any(text, AUTOMATION_MARKERS)
    direct_hit = _contains_any(text, DIRECT_EXECUTE_MARKERS)
    if automation_hit and direct_hit:
        return True
    if "cron 投递" in text or ("cron" in text.lower() and "不要自行发送消息" in text):
        return True
    if "运行抓取脚本" in text and ("整理输出格式" in text or "快讯" in text):
        return True
    if "直接派给" in text or "直接安排到" in text or "直接安排" in text:
        return True
    return False


def _is_basic_direct_handle(text: str) -> bool:
    if len(text) > 60:
        return False
    if _contains_any(text, RESEARCH_KEYWORDS) or _contains_any(text, DELIVERABLE_KEYWORDS):
        return False
    return _contains_any(text, BASIC_DIRECT_MARKERS)


def _is_simple_lookup(text: str) -> bool:
    if len(text) > 60:
        return False
    if _contains_any(text, RESEARCH_KEYWORDS) or _contains_any(text, DELIVERABLE_KEYWORDS):
        return False
    if _contains_any(text, ("同时", "并且", "顺便", "另外", "再", "然后")):
        return False
    target_hit = _contains_any(text, LOOKUP_DIRECT_TARGET_KEYWORDS)
    query_hit = _contains_any(text, ("查", "查询", "看看", "看下", "告诉我", "问一下", "帮我查"))
    return target_hit and query_hit


def _is_simple_task(text: str) -> bool:
    if len(text) > 100:
        return False
    if _contains_any(text, SIMPLE_TASK_BLOCKERS):
        return False
    if _contains_any(text, ("同时", "并且", "另外", "顺便", "以及", "还要", "分别")):
        return False
    if _contains_any(text, ("这个", "那个", "这里", "那里")) and len(text) <= 30:
        return False
    return _contains_any(text, SIMPLE_TASK_HINT_KEYWORDS)


def _is_setup_direct_handle(text: str) -> bool:
    if len(text) > 120:
        return False
    if _contains_any(text, RESEARCH_KEYWORDS) or _contains_any(text, DELIVERABLE_KEYWORDS):
        return False
    if _contains_any(text, SETUP_DIRECT_BLOCKERS):
        return False
    if _contains_any(text, ("同时", "并且", "还要", "顺便", "另外")):
        return False
    return _contains_any(text, SETUP_DIRECT_KEYWORDS)


def _is_org_memory_sync(text: str) -> bool:
    lowered = text.lower()
    compact = _semantic_compact(text)
    scope_hit = _contains_any(lowered, MEMORY_SYNC_SCOPE_KEYWORDS) or _contains_any(compact, MEMORY_SYNC_SCOPE_KEYWORDS)
    target_hit = _contains_any(lowered, MEMORY_SYNC_TARGET_KEYWORDS) or _contains_any(compact, MEMORY_SYNC_TARGET_KEYWORDS)
    action_hit = (
        _contains_any(lowered, ("写", "写入", "更新", "同步", "补充", "记住", "加到", "写进", "补", "追加", "禁用", "停用", "替换", "切换", "改成"))
        or _contains_any(compact, ("写入", "更新", "同步", "补充", "记住", "加到", "写进", "追加", "禁用", "停用", "替换", "切换", "改成"))
    )
    if scope_hit and target_hit and action_hit:
        return True
    if ("所有agent都可以使用" in lowered or "所有agent都可以使用" in compact) and target_hit:
        return True
    if scope_hit and _contains_any(compact, ("soulmd", "提示词", "执行规范", "工作规范", "统一规范")):
        return True
    if scope_hit and _contains_any(compact, ("部门职责", "职责说明", "角色边界", "职责边界", "分工边界", "协作边界", "边界规则")):
        return True
    if scope_hit and _contains_any(compact, ("禁用工具", "停用工具", "工具治理", "工具策略", "工具白名单", "工具黑名单", "浏览器cli", "浏览器回退", "回退链路", "联网回退", "zhipuwebsearch")):
        return True
    return False


def _needs_planning_signal(text: str) -> bool:
    if _contains_any(text, ("架构", "路线图", "技术选型", "prd", "规划", "拆解", "实现方案", "产品方案")):
        return True
    if "方案" in text and not _contains_any(text, ("这份方案", "活动方案", "合作方案", "原方案", "现有方案")):
        return True
    return False


def _build_semantic_profile(text: str) -> dict:
    normalized = _normalize_text(text)
    direct_agent = _direct_agent_hint(normalized)
    artifact_based = _contains_any(normalized, ARTIFACT_INPUT_MARKERS)
    content_output = _contains_any(normalized, CONTENT_OUTPUT_KEYWORDS)
    review_task = _contains_any(normalized, REVIEW_TASK_KEYWORDS)
    simple_lookup = _is_simple_lookup(normalized)
    setup_direct = _is_setup_direct_handle(normalized)
    org_memory_sync = _is_org_memory_sync(normalized)
    basic_direct = _is_basic_direct_handle(normalized)
    deterministic_execute = _is_direct_execute(normalized)
    simple_task = _is_simple_task(normalized)
    formal_signal = (
        _contains_any(normalized, ACTION_KEYWORDS)
        or _contains_any(normalized, DELIVERABLE_KEYWORDS)
        or _contains_any(normalized, RESEARCH_KEYWORDS)
    )
    final_review_required = _contains_any(normalized, ("公开发布", "对外", "生产环境", "正式环境", "权限", "合规", "法务", "财务"))
    needs_planning = _needs_planning_signal(normalized)
    cross_department = _contains_any(normalized, ("同时", "并且", "另外", "顺便", "以及", "还要", "分别", "协同", "多部门"))

    shape = "chat"
    semantic_intent = "chat"
    coordination_need = "none"
    can_chief_handle = True

    if setup_direct:
        shape = "setup"
        semantic_intent = "setup_direct"
    elif simple_lookup:
        shape = "lookup"
        semantic_intent = "simple_lookup"
    elif basic_direct:
        shape = "rewrite"
        semantic_intent = "basic_direct"
    elif org_memory_sync:
        shape = "org_policy"
        semantic_intent = "org_memory_sync"
        coordination_need = "single_department"
        can_chief_handle = False
        direct_agent = "engineering"
    elif review_task and not needs_planning and not cross_department:
        shape = "review"
        semantic_intent = "simple_task"
        coordination_need = "single_department"
        can_chief_handle = False
        direct_agent = "compliance_test"
    elif artifact_based and content_output and not final_review_required and not needs_planning:
        shape = "artifact_to_content"
        semantic_intent = "simple_task"
        coordination_need = "single_department"
        can_chief_handle = False
        direct_agent = "brand_content"
    elif simple_task and direct_agent != "chief_of_staff":
        shape = "bounded_specialist"
        semantic_intent = "simple_task"
        coordination_need = "single_department"
        can_chief_handle = False
    elif simple_task:
        shape = "bounded_self"
        semantic_intent = "simple_task"
    elif deterministic_execute and direct_agent != "chief_of_staff":
        shape = "deterministic_specialist"
        semantic_intent = "deterministic_execute"
        coordination_need = "single_department"
        can_chief_handle = False
    elif deterministic_execute:
        shape = "deterministic_self"
        semantic_intent = "deterministic_execute"
    elif formal_signal:
        shape = "formal"
        semantic_intent = "formal_task"
        coordination_need = "cross_department" if (needs_planning or cross_department or _contains_any(normalized, RESEARCH_KEYWORDS)) else "single_department"
        can_chief_handle = direct_agent == "chief_of_staff" and coordination_need == "none"

    return {
        "shape": shape,
        "taskShape": shape,
        "semanticIntent": semantic_intent,
        "thingIs": semantic_intent,
        "needsSpecialist": not can_chief_handle,
        "specialistAgent": "" if can_chief_handle else direct_agent,
        "coordinationNeed": coordination_need,
        "canChiefHandle": can_chief_handle,
        "artifactBased": artifact_based,
        "contentOutput": content_output,
        "reviewTask": review_task,
        "needsReview": final_review_required,
        "finalReviewRequired": final_review_required,
        "needsPlanning": needs_planning,
    }


def _next_task_id(now: dt.datetime, flow_mode: str = "full") -> str:
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
        suffix = "多 Agent 框架" if _contains_any(compact, ("agent", "框架")) else "方案"
        return f"分析 {head} {suffix}".strip()

    compact = re.sub(r"^(分析|调研|对比|整理|总结|写|输出|生成|处理)", "", compact).strip()
    compact = compact[:30]
    return compact or "整理需求并转交总裁办"


def analyze_message(text: str) -> dict:
    normalized = _normalize_text(text)
    if _looks_like_direct_reply(normalized):
        profile = _build_semantic_profile(normalized)
        return {
            "classification": "direct_reply",
            "shouldCreateTask": False,
            "reason": "消息是短确认或闲聊，不触发正式任务。",
            "replyText": "",
            "taskId": "",
            "titleHint": "",
            "progressText": "",
            "progressPlan": "",
            "guardrail": "允许直接用一句话回复，不需要建单。",
            "routeMode": "direct_reply",
            "semanticIntent": "chat",
            "semanticProfile": profile,
        }

    profile = _build_semantic_profile(normalized)
    semantic_intent = str(profile.get("semanticIntent") or "chat")
    can_chief_handle = bool(profile.get("canChiefHandle"))
    coordination_need = str(profile.get("coordinationNeed") or "none")
    specialist_agent = str(profile.get("specialistAgent") or "")

    if semantic_intent == "basic_direct":
        return {
            "classification": "direct_handle",
            "shouldCreateTask": False,
            "reason": "消息属于低复杂度基础任务，可由总裁办直办。",
            "replyText": "已收到，这类基础任务由总裁办直接处理。",
            "taskId": "",
            "titleHint": _title_hint(normalized),
            "progressText": "判定为基础直办任务，准备由总裁办直接完成",
            "progressPlan": "消息分诊✅|总裁办直办🔄|结果回传",
            "guardrail": "禁止进入完整协同链，除非执行中发现范围扩大。",
            "directAgentHint": "chief_of_staff",
            "routeMode": "direct_handle",
            "semanticIntent": semantic_intent,
            "semanticProfile": profile,
        }

    if semantic_intent == "chat":
        return {
            "classification": "direct_reply",
            "shouldCreateTask": False,
            "reason": "未命中正式任务特征，按普通对话处理。",
            "replyText": "",
            "taskId": "",
            "titleHint": "",
            "progressText": "",
            "progressPlan": "",
            "guardrail": "按普通对话回复，不建单。",
            "routeMode": "direct_reply",
            "semanticIntent": semantic_intent,
            "semanticProfile": profile,
        }

    if coordination_need == "cross_department":
        task_id = _next_task_id(beijing_now(), "full")
        return {
            "classification": "create_task",
            "shouldCreateTask": True,
            "reason": "总裁办已完成语义画像，判断该需求需要跨部门协同，进入 full 流程。",
            "replyText": "已收到需求，总裁办正在整理需求并判断流程。",
            "taskId": task_id,
            "titleHint": _title_hint(normalized),
            "progressText": "已完成语义画像，判定需要跨部门协同，准备建单并分诊",
            "progressPlan": "消息分诊✅|语义消化✅|创建任务🔄|流转分派",
            "guardrail": "在分诊完成前，不要直接产出最终交付物。",
            "routeMode": "create_task",
            "semanticIntent": semantic_intent,
            "semanticProfile": profile,
        }

    if can_chief_handle:
        return {
            "classification": "direct_handle",
            "shouldCreateTask": False,
            "reason": "总裁办已完成语义画像，判断该需求不需要专项能力，也不需要协同，可直接处理。",
            "replyText": "已收到，这件事由总裁办直接处理。",
            "taskId": "",
            "titleHint": _title_hint(normalized),
            "progressText": "已完成语义画像，判定为总裁办直办任务",
            "progressPlan": "消息分诊✅|语义消化✅|直接处理🔄|结果回传",
            "guardrail": "禁止误升为正式协同链，除非执行中发现任务范围明显扩大。",
            "directAgentHint": "chief_of_staff",
            "routeMode": "direct_handle",
            "semanticIntent": semantic_intent,
            "semanticProfile": profile,
        }

    return {
        "classification": "direct_execute",
        "shouldCreateTask": False,
        "reason": "总裁办已完成语义画像，判断该需求需要专项能力但不需要跨部门协同，可直接派给对应部门处理。",
        "replyText": "已收到，这件事会直接安排给对应专项部门处理。",
        "taskId": "",
        "titleHint": _title_hint(normalized),
        "progressText": "已完成语义画像，判定为单部门专项任务，准备直派执行",
        "progressPlan": "消息分诊✅|语义消化✅|直派执行🔄|结果回传",
        "guardrail": "默认不进入完整协同链；只有在执行中发现真实跨部门依赖时再升级。",
        "directAgentHint": specialist_agent or _direct_agent_hint(normalized),
        "routeMode": "direct_execute",
        "semanticIntent": semantic_intent,
        "semanticProfile": profile,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "message required",
                    "usage": 'python3 scripts/intake_guard.py "用户原话"',
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    payload = analyze_message(" ".join(argv[1:]))
    payload["ok"] = True
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
