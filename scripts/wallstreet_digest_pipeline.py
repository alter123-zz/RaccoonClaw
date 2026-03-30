#!/usr/bin/env python3
"""WallstreetCN + CLS tech digest pipeline for cron delivery.

Flow:
1. Fetch WallstreetCN / CLS live items
2. Filter tech/AI keywords and exclude politics/current affairs
3. Generate Snowball/Futu-style comments with stock codes
4. Moderate generated comments
5. Print the final digest for cron delivery
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import random
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from xueqiu_pending_publish import create_pending_draft

OCLAW_HOME = Path.home() / ".openclaw"
WALLSTREET_CRAWLER = OCLAW_HOME / "workspace-engineering" / "skills" / "wallstreet-crawler" / "wallstreet-crawler.py"
MODERATION_SCRIPT = OCLAW_HOME / "workspace-secops" / "skills" / "news-aggregator-skill" / "scripts" / "content_moderation.py"
XUEQIU_PUBLISHER = OCLAW_HOME / "workspace-chief_of_staff" / "skills" / "playwright-community-publisher" / "scripts" / "community_publisher.mjs"
XUEQIU_DRAFT_DIR = OCLAW_HOME / "playwright-community-publisher" / "wallstreet-drafts"
LIVE_URL = "https://wallstreetcn.com/live/global"
CLS_TELEGRAPH_URL = "https://www.cls.cn/telegraph"
CLS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": CLS_TELEGRAPH_URL,
}

# 去重数据文件
SENT_NEWS_CACHE = OCLAW_HOME / "workspace-chief_of_staff" / "data" / "wallstreet_sent_cache.json"


def load_sent_news() -> set[str]:
    """加载已发送新闻ID集合"""
    if SENT_NEWS_CACHE.exists():
        try:
            data = json.loads(SENT_NEWS_CACHE.read_text(encoding="utf-8"))
            return set(data.get("sent_ids", []))
        except Exception:
            pass
    return set()


def save_sent_news(sent_ids: set[str]):
    """保存已发送新闻ID集合"""
    cache_dir = SENT_NEWS_CACHE.parent
    cache_dir.mkdir(parents=True, exist_ok=True)
    # 只保留最近100条
    data = {"sent_ids": list(sent_ids)[-100:]}
    SENT_NEWS_CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

AI_KEYWORDS = [
    "AI", "人工智能", "大模型", "LLM", "ChatGPT", "GPT", "OpenAI",
    "Anthropic", "Claude", "Gemini", "DeepSeek", "豆包", "文心一言",
    "算力", "GPU", "英伟达", "NVIDIA", "AMD", "芯片", "处理器",
]
TECH_KEYWORDS = [
    "科技", "技术", "互联网", "云计算", "自动驾驶", "智能驾驶",
    "量子计算", "量子通信", "5G", "6G", "卫星", "机器人", "人形机器人",
    "eVTOL", "低空经济", "操作系统", "浏览器", "开源", "安全", "软件",
]
ENERGY_KEYWORDS = [
    "新能源", "锂电池", "固态电池", "光伏", "风电", "核电", "电力",
    "电网", "氢能", "储能", "聚变能源", "长时储能",
]
ALL_KEYWORDS = AI_KEYWORDS + TECH_KEYWORDS + ENERGY_KEYWORDS
COMMENTARY_KEYWORDS = AI_KEYWORDS + TECH_KEYWORDS
POLITICAL_EXCLUSION_KEYWORDS = [
    "特朗普", "伊朗", "以色列", "乌克兰", "俄罗斯", "巴基斯坦", "阿富汗", "黎巴嫩",
    "停火", "袭击", "空袭", "导弹", "军方", "军队", "军舰", "防空", "无人机袭击",
    "大使馆", "外交", "总统", "总理", "海峡", "国务院", "白宫", "新华社", "央视",
    "军事行动", "交火", "核武器", "领袖", "使馆",
]
LEGAL_SCANDAL_EXCLUSION_KEYWORDS = [
    "诉讼", "起诉", "审理", "庭审", "判决", "法官", "法院", "原告", "被告", "律师",
    "欺诈", "欺诈案", "丑闻", "争议", "纷争", "互撕", "举报", "调查", "指控",
    "药物", "毒品", "氯胺酮", "药检", "婚姻", "出轨", "桃色", "绯闻", "八卦",
    "爆料", "爆雷", "传闻", "私生活", "人身攻击", "口水战",
]
MARKET_STRATEGY_EXCLUSION_KEYWORDS = [
    "券商", "研报", "策略", "仓位", "个股挖掘", "指数", "震荡", "情绪", "情绪面", "风偏",
    "风险偏好", "成交", "成交额", "放量", "缩量", "资金面", "资金行为", "资金流",
    "A股", "沪指", "深成指", "创业板", "北向资金", "市场定价", "行情", "走势",
]
BUSINESS_PROGRESS_KEYWORDS = [
    "发布", "上线", "开源", "升级", "更新", "推出", "发布会", "内测", "公测", "版本",
    "模型", "新品", "新款", "量产", "交付", "落地", "部署", "商用", "商业化", "应用",
    "接入", "适配", "合作", "签署", "订单", "客户", "中标", "项目", "基地", "工厂",
    "投产", "扩产", "产能", "出货", "装机", "融资", "募资", "估值", "并购", "收购",
    "入股", "战略投资", "IPO", "财报", "营收", "利润", "亏损", "预增", "预亏",
    "指引", "经营", "业绩", "增长", "技术突破", "突破", "研发", "流片", "试产",
]

COMPANY_CODE_MAP = {
    # 港股科技
    "百度": "9888.HK",
    "阿里巴巴": "9988.HK",
    "腾讯": "0700.HK",
    "美团": "3690.HK",
    "网易": "9999.HK",
    "京东": "9618.HK",
    "小米": "1810.HK",
    "快手": "1024.HK",
    "哔哩哔哩": "9626.HK",
    "联想": "0992.HK",
    # A股科技/AI
    "中芯国际": "688981.SH",
    "寒武纪": "688256.SH",
    "海光信息": "688041.SH",
    "浪潮信息": "000977.SZ",
    "科大讯飞": "002230.SZ",
    "金山办公": "688111.SH",
    "三六零": "601360.SH",
    "拓尔思": "300229.SZ",
    "同花顺": "300033.SZ",
    "东方财富": "300059.SZ",
    "万得": "Wind",
    "恒生电子": "600570.SH",
    # 新能源
    "宁德时代": "300750.SZ",
    "比亚迪": "002594.SZ",
    "隆基绿能": "601012.SH",
    "通威股份": "600438.SH",
    "三峡能源": "600905.SH",
    "亿纬锂能": "300014.SZ",
    "赣锋锂业": "002460.SZ",
    # 半导体
    "沪电股份": "002463.SZ",
    "金安国纪": "002636.SZ",
    "长电科技": "600584.SH",
    "通富微电": "002156.SZ",
    "北方华创": "002371.SZ",
    "中微公司": "688012.SH",
    # 机器人/宇树
    "优必选": "9880.HK",
    "优必选科技": "9880.HK",
    "宇树科技": "未上市",
    "追觅": "未上市",
    "华为": "未上市",
    "DeepSeek": "未上市",
    "Kimi": "未上市",
    "月之暗面": "未上市",
    # 美股
    "英伟达": "NVDA.US",
    "AMD": "AMD.US",
    "英特尔": "INTC.US",
    "高通": "QCOM.US",
    "微软": "MSFT.US",
    "谷歌": "GOOGL.US",
    "苹果": "AAPL.US",
    "Meta": "META.US",
    "OpenAI": "未上市",
    "Anthropic": "未上市",
}

# 禁用行业联想股票 - 只保留新闻中直接提到的股票
INDUSTRY_STOCK_FALLBACKS: list[tuple[tuple[str, ...], list[str]]] = []

POSITIVE_TOKENS = ("签署", "订单", "增长", "突破", "发布", "合作", "利好", "加快", "推进")
NEGATIVE_TOKENS = ("下跌", "承压", "回落", "警惕", "风险", "飘绿", "跌幅")


@dataclass
class DigestItem:
    time: str
    title: str
    content: str
    item_id: str
    source: str
    category: str
    stock_codes: list[str]
    comment: str
    moderation_result: str
    moderation_score: int
    url: str


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"无法加载模块: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_news(channel: str, limit: int) -> list[dict[str, Any]]:
    if not WALLSTREET_CRAWLER.exists():
        raise FileNotFoundError(f"wallstreet-crawler 不存在: {WALLSTREET_CRAWLER}")
    crawler = _load_module(WALLSTREET_CRAWLER, "wallstreet_crawler_runtime")
    raw = crawler.fetch_livenews(channel=channel, limit=limit)
    parsed = crawler.parse_livenews(raw, fields="time,content_text,title,id")
    for item in parsed:
        item["source"] = "wallstreet"
    return parsed


def fetch_cls_news(limit: int) -> list[dict[str, Any]]:
    request = urllib.request.Request(CLS_TELEGRAPH_URL, headers=CLS_HEADERS)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw_html = response.read().decode("utf-8", errors="ignore")

    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", raw_html, flags=re.S | re.I)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.S | re.I)
    cleaned = re.sub(r"<[^>]+>", "\n", cleaned)
    cleaned = html.unescape(cleaned).replace("\xa0", " ")
    cleaned = re.sub(r"\r", "", cleaned)
    cleaned = re.sub(r"\n{2,}", "\n", cleaned)

    results: list[dict[str, Any]] = []
    pattern = re.compile(
        r"(?P<time>\d{2}:\d{2}:\d{2})\s+〖(?P<title>[^〗]+)〗(?P<content>.*?)(?=\n\d{2}:\d{2}:\d{2}\n+〖|\Z)",
        re.S,
    )
    for match in pattern.finditer(cleaned):
        title = normalize_text(match.group("title"))
        content = normalize_text(match.group("content"))
        content = re.split(r"\s+(?:阅\s+\d|评论\s*\(|分享\(|环球市场情报|电报持续更新中)", content)[0].strip()
        if not title and not content:
            continue
        stable_id = hashlib.sha1(f"{match.group('time')}|{title}|{content[:80]}".encode("utf-8")).hexdigest()[:12]
        results.append(
            {
                "time": match.group("time"),
                "content_text": content,
                "title": title,
                "id": f"cls:{stable_id}",
                "source": "cls",
                "source_url": CLS_TELEGRAPH_URL,
            }
        )
        if len(results) >= limit:
            break
    return results


def load_mock_news(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        if isinstance(payload.get("news"), list):
            return payload["news"]
        if isinstance(payload.get("items"), list):
            return payload["items"]
    if isinstance(payload, list):
        return payload
    return []


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def fallback_title(content: str, limit: int = 42) -> str:
    normalized = normalize_text(content)
    if not normalized:
        return "未命名快讯"
    sentence = re.split(r"[。！？!?；;]", normalized)[0].strip()
    head = sentence or normalized
    return head[:limit] + ("..." if len(head) > limit else "")


def classify_item(text: str) -> str:
    lowered = text.lower()
    if any(keyword.lower() in lowered for keyword in AI_KEYWORDS):
        return "AI"
    if any(keyword.lower() in lowered for keyword in ENERGY_KEYWORDS):
        return "ENERGY"
    if any(keyword.lower() in lowered for keyword in TECH_KEYWORDS):
        return "TECH"
    return "DEFAULT"


def is_political_item(title: str, content: str) -> bool:
    text = f"{title} {content}"
    return any(token in text for token in POLITICAL_EXCLUSION_KEYWORDS)


def is_excluded_topic(title: str, content: str) -> bool:
    text = f"{title} {content}"
    return any(token in text for token in LEGAL_SCANDAL_EXCLUSION_KEYWORDS)


def is_market_strategy_item(title: str, content: str) -> bool:
    text = f"{title} {content}"
    return any(token in text for token in MARKET_STRATEGY_EXCLUSION_KEYWORDS)


def is_commentary_target(title: str, content: str) -> bool:
    haystack = f"{title} {content}".lower()
    return any(keyword.lower() in haystack for keyword in COMMENTARY_KEYWORDS)


def is_business_progress_item(title: str, content: str) -> bool:
    text = f"{title} {content}"
    return any(token in text for token in BUSINESS_PROGRESS_KEYWORDS)


def filter_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items:
        content = normalize_text(item.get("content_text", ""))
        title = normalize_text(item.get("title", "")) or fallback_title(content)
        haystack = f"{title} {content}".lower()
        if not is_commentary_target(title, content):
            continue
        if is_political_item(title, content):
            continue
        if is_excluded_topic(title, content):
            continue
        if is_market_strategy_item(title, content):
            continue
        if not is_business_progress_item(title, content):
            continue
        filtered.append(
            {
                "time": normalize_text(item.get("time", "")),
                "title": title,
                "content": content,
                "id": str(item.get("id", "")),
                "source": str(item.get("source", "wallstreet")),
                "source_url": str(item.get("source_url", "")),
                "category": classify_item(haystack),
            }
        )
    return filtered


def format_stock_display(name: str, code: str) -> str | None:
    clean_name = normalize_text(name)
    clean_code = normalize_text(code)
    if not clean_code or clean_code in {"未上市", "Wind"}:
        return None

    symbol = clean_code
    if clean_code.endswith(".HK"):
        symbol = clean_code[:-3]
        if symbol.isdigit():
            symbol = symbol.zfill(5)
    elif clean_code.endswith(".US"):
        symbol = clean_code[:-3]
    elif clean_code.endswith(".SH") or clean_code.endswith(".SZ"):
        symbol = clean_code[:-3]

    return f"{clean_name}({symbol})" if clean_name else symbol


def infer_industry_stock_codes(text: str, limit: int = 3) -> list[str]:
    matches: list[str] = []
    for keywords, stocks in INDUSTRY_STOCK_FALLBACKS:
        if any(keyword in text for keyword in keywords):
            for stock in stocks:
                if stock not in matches:
                    matches.append(stock)
                    if len(matches) >= limit:
                        return matches
    return matches[:limit]


def should_use_industry_fallback(title: str, content: str) -> bool:
    if is_political_item(title, content):
        return False
    if is_excluded_topic(title, content):
        return False
    if is_market_strategy_item(title, content):
        return False
    if not is_business_progress_item(title, content):
        return False
    return True


def extract_stock_codes(title: str, content: str) -> list[str]:
    text = f"{title} {content}"
    codes: list[str] = []

    for name, code in COMPANY_CODE_MAP.items():
        if name not in text:
            continue
        display = format_stock_display(name, code)
        if display and display not in codes:
            codes.append(display)

    for match in re.finditer(r"\b([036]\d{5})\b", text):
        raw = match.group(1)
        if raw not in codes:
            codes.append(raw)

    for match in re.finditer(r"\b([A-Z]{2,5})\b", text):
        raw = match.group(1)
        if raw in {"AI", "LLM", "GPU", "GPT", "AIGC", "AGI", "AMD"}:
            if raw == "AMD" and "AMD(AMD)" not in codes:
                codes.append("AMD(AMD)")
            continue
        us_code = format_stock_display("", raw)
        if any(company in text for company, mapped_code in COMPANY_CODE_MAP.items() if mapped_code == f"{raw}.US") and us_code and us_code not in codes:
            codes.append(us_code)

    if codes:
        return codes[:3]

    if not should_use_industry_fallback(title, content):
        return []

    return infer_industry_stock_codes(text, limit=3)


def detect_sentiment(title: str, content: str) -> str:
    text = f"{title} {content}"
    pos = sum(token in text for token in POSITIVE_TOKENS)
    neg = sum(token in text for token in NEGATIVE_TOKENS)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


def generate_comment(title: str, content: str, category: str, stock_codes: list[str]) -> str:
    """调用大模型生成深度评论"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key="dummy", base_url="http://127.0.0.1:8080/v1")
        
        codes_text = "、".join(stock_codes) if stock_codes else "无明确相关上市公司"
        stock_rule = (
            "2. 必须包含股票代码格式如：$腾讯控股(00700)$ 或 $阿里巴巴-SW(09988)$"
            if stock_codes
            else "2. 如果新闻没有明确对应上市公司，就不要硬写股票代码，也不要出现“相关标的”这种占位词"
        )
        
        prompt = f"""你是一位专业的股票分析师和科技观察家。请根据以下新闻生成深度分析评论。

新闻标题：{title}
新闻内容：{content}
关联股票：{codes_text}

要求：
1. 只从科技、AI、产业链、产品落地和资本市场映射角度评论，不要写时政、外交、军事和宏大叙事
{stock_rule}
3. 分析要有深度，2-4个要点
4. 最后要有一句话总结
5. 禁止、车轱辘话，要直接给出有价值的分析
6. 最多150字

评论格式示例：
{company}的{产品}又升级了，这次有一个关键变化：{变化}。${code}$
最新版本主要增加了几个功能：
- 功能1
- 功能2

表面看是{表面}，但背后有几个值得关注的趋势：
1、{趋势1}
2、{趋势2}

简单总结：{一句话总结}"""

        resp = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # 如果大模型调用失败，回退到简单模板
        pass
    
    # 回退逻辑
    codes_text = "、".join(stock_codes)
    codes_prefix = f"【{codes_text}】" if codes_text else ""
    sentiment = detect_sentiment(title, content)

    templates = {
        ("AI", "positive"): [
            "{prefix}AI 方向催化还在发酵，消息更像情绪提振，先看订单和落地节奏，追高别上头。",
            "{prefix}算力/AI 线继续有题材刺激，短线容易有资金回流，核心还是看兑现速度和业绩承接。",
        ],
        ("AI", "negative"): [
            "{prefix}AI 线今天偏分化，消息有热度但盘面承接一般，短线更适合等分歧后的确认。",
            "{prefix}题材还在，但市场更看重兑现，情绪上先别把单条快讯直接当成趋势反转。",
        ],
        ("TECH", "positive"): [
            "{prefix}科技链条又有新催化，偏交易层面先看板块共振，强的话会沿着龙头继续扩散。",
            "{prefix}这类消息对科技题材是加分项，短线看资金是否围绕核心标的继续抱团。",
        ],
        ("TECH", "negative"): [
            "{prefix}科技线有消息但盘面偏弱，先看有没有放量承接，别只看题材不看强度。",
            "{prefix}消息面不差，但市场风险偏好一般，短线更适合盯龙头反馈再决定跟不跟。",
        ],
        ("ENERGY", "positive"): [
            "{prefix}新能源/先进能源方向有增量催化，偏中期逻辑，短线先观察资金会不会聚焦到龙头。",
            "{prefix}如果政策和产业节奏能继续兑现，这条线后面还有反复交易的空间。",
        ],
        ("ENERGY", "negative"): [
            "{prefix}新能源题材有消息，但更像中线叙事，短线先看板块强度和成交配合。",
            "{prefix}消息出来不等于马上走趋势，先观察资金是否愿意回流这条线。",
        ],
        ("DEFAULT", "positive"): [
            "{prefix}消息面偏正向，短线值得放进观察池，先看市场有没有给到持续性反馈。",
        ],
        ("DEFAULT", "negative"): [
            "{prefix}有事件驱动，但市场反馈一般，先跟踪别急着下重手。",
        ],
        ("DEFAULT", "neutral"): [
            "{prefix}先记进观察池，后面重点看资金强弱、成交和后续跟进公告。",
        ],
    }
    choices = templates.get((category, sentiment)) or templates.get((category, "neutral")) or templates[("DEFAULT", "neutral")]
    return random.choice(choices).format(prefix=codes_prefix).strip()


def moderate_comment(title: str, comment: str, url: str) -> tuple[str, int]:
    if MODERATION_SCRIPT.exists():
        try:
            module = _load_module(MODERATION_SCRIPT, "content_moderation_runtime")
            moderator = module.ContentModerator()
            report = moderator.moderate(
                {
                    "title": title,
                    "content": comment,
                    "source": "华尔街见闻",
                    "url": url,
                }
            )
            return str(report.result.value), int(report.score)
        except Exception:
            pass

    risk_score = 0
    if any(token in comment for token in ("稳赚", "梭哈", "保本", "必涨")):
        risk_score += 90
    if any(token in comment for token in POLITICAL_EXCLUSION_KEYWORDS):
        risk_score += 100
    if "仅供参考" not in comment and "观察" not in comment:
        risk_score += 10
    return ("reject", risk_score) if risk_score >= 80 else ("pass", risk_score)


def build_digest(items: list[DigestItem], now_text: str) -> str:
    ai_items = [item for item in items if item.category in {"AI", "TECH"}]
    energy_items = [item for item in items if item.category == "ENERGY"]
    passed_count = sum(1 for item in items if item.moderation_result == "pass")
    warned_count = sum(1 for item in items if item.moderation_result == "warn")

    def render_section(title: str, section_items: list[DigestItem]) -> list[str]:
        lines = [title]
        if not section_items:
            lines.append("- (暂无相关内容)")
            return lines
        for item in section_items:
            source_label = "财联社" if item.source == "cls" else "华尔街见闻"
            time_str = item.time[-8:-3] if item.time else "--:--"
            lines.append(f"- [{time_str}] {item.title} . {source_label}")
            lines.append(f"  {item.comment}")
            result_label = "通过" if item.moderation_result == "pass" else "预警"
            lines.append(f"  审核结果: {result_label} (score={item.moderation_score})")
            lines.append(f"  {item.url}")
        return lines

    has_news = len(items) > 0
    
    if not has_news:
        lines = [
            f"华尔街见闻 / 财联社 科技快讯 ({now_text})",
            "",
            "过去1小时内没有新的科技/AI/产业相关新闻",
            "我们将继续关注，稍后为您更新",
            "",
            "---",
            "By 华尔街见闻完整流程系统",
        ]
    else:
        summary = f"审核摘要: 通过 {passed_count} 条"
        if warned_count:
            summary += f" . 预警 {warned_count} 条"
        lines = [
            f"华尔街见闻 / 财联社 科技快讯 ({now_text})",
            summary,
            "只保留科技 / AI / 产业相关新闻，时政与战争类内容已自动过滤。",
            "",
        ]
        lines.extend(render_section("AI/科技热点:", ai_items[:4]))
        lines.append("")
        lines.extend(render_section("新能源/科技:", energy_items[:3]))
        lines.extend(["", "---", "By 华尔街见闻完整流程系统"])
    return "\n".join(lines)


    score = 0
    if item.category == "AI":
        score += 30
    elif item.category == "TECH":
        score += 22
    elif item.category == "ENERGY":
        score += 14
    score += len(item.stock_codes) * 6
    if item.moderation_result == "pass":
        score += 4
    title_and_comment = f"{item.title} {item.comment}"
    for token in ("DeepSeek", "腾讯", "英伟达", "OpenAI", "Claude", "AI", "芯片", "大模型", "机器人"):
        if token in title_and_comment:
            score += 3
    return score


def _item_priority(item: DigestItem) -> tuple:
    score = 0
    # 通过的审核优先
    if item.moderation_result == "pass":
        score += 100
    # 热门优先
    hot_score = getattr(item, 'hot_score', None)
    if hot_score:
        score += min(hot_score / 100, 50)
    # AI 类优先
    if item.category == "AI":
        score += 20
    return (-score, item.time or "")


def pick_feature_item(items: list[DigestItem]) -> DigestItem | None:
    if not items:
        return None
    return sorted(items, key=_item_priority, reverse=True)[0]


def _ensure_sentence(text: str) -> str:
    clean = normalize_text(text)
    if not clean:
        return ""
    if clean.endswith(("。", "！", "？", "…")):
        return clean
    return clean + "。"


def _discussion_third_point(item: DigestItem) -> str:
    if item.category == "AI":
        return "这类新闻真正的看点，不是题材热度本身，而是模型、产品和生态能不能继续往商业化落地推进。"
    if item.category == "TECH":
        return "对科技线来说，后面最值得盯的不是情绪，而是产品节奏、客户落地和资金是否愿意继续给反馈。"
    if item.category == "ENERGY":
        return "这类赛道消息更偏中期逻辑，后续要看产业进度、订单兑现和资本开支有没有持续验证。"
    return "从交易上看，这类消息更适合先观察持续催化，再决定是不是值得进一步跟踪。"


def _discussion_stock_paragraph(stock_codes: list[str], item: DigestItem) -> str:
    if not stock_codes:
        return ""
    stock_line = " ".join(f"${code}$" if not code.startswith("$") else code for code in stock_codes)
    if item.category == "AI":
        return f"对{stock_line}来说，这条消息如果后面继续发酵，关键不是概念，而是看产品接入、订单兑现和生态合作能不能跟上。"
    if item.category == "TECH":
        return f"对{stock_line}来说，这条消息更值得看的，是有没有后续经营数据、产品节奏或者产业合作来验证。"
    if item.category == "ENERGY":
        return f"对{stock_line}来说，后面要盯的是产业链传导、项目推进和业绩兑现，不是单条消息本身。"
    return f"对{stock_line}来说，真正有意义的是后面有没有持续催化，而不是今天这条消息本身。"


def build_xueqiu_discussion(item: DigestItem, now_text: str) -> str:
    core_sentences = [
        sentence.strip()
        for sentence in re.split(r"[。！？!?]\s*", normalize_text(item.content))
        if sentence.strip()
    ]
    first_angle = core_sentences[0] if core_sentences else item.title
    second_angle = core_sentences[1] if len(core_sentences) > 1 else ""
    stock_paragraph = _discussion_stock_paragraph(item.stock_codes, item)

    lines = [
        f"{item.title}，这条消息的核心内容是：{normalize_text(first_angle)}。",
        "",
        "我自己的看法有三点：",
        "",
        f"第一，{_ensure_sentence(item.comment)}",
        f"第二，{_ensure_sentence(second_angle) if second_angle else '如果往产业链传导看，核心还是要盯住订单、落地和资金反馈，别只看题材热度。'}",
        f"第三，{_discussion_third_point(item)}",
        "",
        stock_paragraph,
        "",
        "一句话看，这类消息能不能从新闻变成行情，最后还是要看执行细节、产业反馈和业绩兑现。",
    ]
    return "\n".join(line for line in lines if line).strip()


def queue_xueqiu_confirmation(content: str, item: DigestItem, artifact_dir: str = "") -> dict[str, Any]:
    pending = create_pending_draft(
        content=content,
        title=item.title,
        source="wallstreet_digest",
        source_artifact_dir=artifact_dir,
        metadata={
            "featureTitle": item.title,
            "itemId": item.item_id,
            "stockCodes": item.stock_codes,
            "url": item.url,
        },
    )
    return {
        "status": "awaiting_confirmation",
        "draftId": pending["id"],
        "draftPath": pending["contentPath"],
        "message": "雪球草稿已生成，等待需求方在 iMessage 确认后发布。",
        "title": item.title,
        "content": content,
    }


def publish_to_xueqiu(content: str, mode: str = "publish", publisher_script: Path = XUEQIU_PUBLISHER, headless: bool = False) -> dict[str, Any]:
    if mode == "off":
        return {"status": "skipped", "reason": "xueqiu_disabled"}
    if not publisher_script.exists():
        return {
            "status": "blocked",
            "reason": "missing_xueqiu_publisher",
            "message": f"未找到雪球发布脚本: {publisher_script}",
        }

    XUEQIU_DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    draft_path = XUEQIU_DRAFT_DIR / f"wallstreet-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    draft_path.write_text(content, encoding="utf-8")

    command = [
        "node",
        str(publisher_script),
        "--site",
        "xueqiu",
        "--action",
        "discussion",
        "--content-file",
        str(draft_path),
        "--mode",
        mode,
    ]
    if headless:
        command.extend(["--headless", "true"])

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=420,
        )
    except Exception as exc:
        return {
            "status": "blocked",
            "reason": "xueqiu_publish_exec_failed",
            "message": str(exc),
            "draftPath": str(draft_path),
        }

    payload_text = (completed.stdout or completed.stderr or "").strip()
    result: dict[str, Any]
    try:
        result = json.loads(payload_text) if payload_text else {"status": "blocked", "reason": "empty_publisher_output"}
    except Exception:
        result = {
            "status": "blocked" if completed.returncode else "ok",
            "reason": "non_json_publisher_output",
            "message": payload_text,
        }
    result["draftPath"] = str(draft_path)
    result["command"] = " ".join(command)
    result["exitCode"] = completed.returncode
    return result


def _sort_news_key(item: dict[str, Any]) -> tuple[int, str]:
    time_value = str(item.get("time") or "")
    parts = [part for part in time_value.split(":") if part.isdigit()]
    if len(parts) >= 2:
        hh = int(parts[0])
        mm = int(parts[1])
        ss = int(parts[2]) if len(parts) >= 3 else 0
        return (hh * 3600 + mm * 60 + ss, str(item.get("id") or ""))
    return (0, str(item.get("id") or ""))


def fetch_source_news(channel: str, limit: int, sources: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    wanted = {source.strip().lower() for source in sources if source.strip()}
    if "wallstreet" in wanted:
        try:
            items.extend(fetch_news(channel, limit))
        except Exception:
            pass
    if "cls" in wanted:
        try:
            items.extend(fetch_cls_news(limit))
        except Exception:
            pass
    return sorted(items, key=_sort_news_key, reverse=True)


def run_pipeline(channel: str, limit: int, sources: list[str], input_json: Path | None = None) -> tuple[str, list[DigestItem], str]:
    raw_items = load_mock_news(input_json) if input_json else fetch_source_news(channel, limit, sources)
    filtered = filter_news(raw_items)

    # 去重：加载已发送新闻ID
    sent_ids = set() if input_json else load_sent_news()
    
    # 过滤掉已发送的新闻
    filtered = [item for item in filtered if item.get("id") not in sent_ids]
    
    if not filtered:
        return "⚠️ 过去1小时内无新新闻（均已发送过）", [], datetime.now().strftime("%Y年%-m月%-d日 %H:%M")

    digest_items: list[DigestItem] = []
    new_sent_ids: set[str] = set()
    for item in filtered[:6]:
        codes = extract_stock_codes(item["title"], item["content"])
        comment = generate_comment(item["title"], item["content"], item["category"], codes)
        url = item.get("source_url") or (f"https://wallstreetcn.com/livenews/{item['id']}" if str(item["id"]).startswith(("w", "wallstreet")) else LIVE_URL)
        if item.get("source") == "cls":
            url = CLS_TELEGRAPH_URL
        moderation_result, moderation_score = moderate_comment(item["title"], comment, url)
        if moderation_result == "reject":
            continue
        digest_items.append(
            DigestItem(
                time=item["time"],
                title=item["title"],
                content=item["content"],
                item_id=item["id"],
                source=str(item.get("source", "wallstreet")),
                category=item["category"],
                stock_codes=codes,
                comment=comment,
                moderation_result=moderation_result,
                moderation_score=moderation_score,
                url=url,
            )
        )
        # 记录已发送的新闻ID
        if item.get("id"):
            new_sent_ids.add(item["id"])

    # 保存新的sent_ids
    if new_sent_ids and not input_json:
        all_sent = sent_ids | new_sent_ids
        save_sent_news(all_sent)

    now_text = datetime.now().strftime("%Y年%-m月%-d日 %H:%M")
    return build_digest(digest_items, now_text), digest_items, now_text


def main() -> int:
    parser = argparse.ArgumentParser(description="WallstreetCN tech digest full pipeline")
    parser.add_argument("--channel", default="global", help="WallstreetCN channel")
    parser.add_argument("--limit", type=int, default=30, help="Fetch limit")
    parser.add_argument("--input-json", default="", help="Use local JSON file instead of live fetch")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of delivery text")
    parser.add_argument("--sources", default="wallstreet,cls", help="Comma-separated sources: wallstreet, cls")
    parser.add_argument("--xueqiu-mode", default="off", choices=["off", "preview", "confirm", "publish", "await_confirm"], help="Optionally publish the featured item to Xueqiu after digest generation")
    parser.add_argument("--xueqiu-headless", action="store_true", help="Run the Xueqiu publisher in headless mode")
    args = parser.parse_args()

    input_json = Path(args.input_json).expanduser() if args.input_json else None
    digest, items, now_text = run_pipeline(args.channel, args.limit, [part.strip() for part in args.sources.split(",")], input_json=input_json)
    xueqiu_result: dict[str, Any] | None = None
    if args.xueqiu_mode != "off":
        feature_item = pick_feature_item(items)
        if feature_item:
            discussion = build_xueqiu_discussion(feature_item, now_text)
            if args.xueqiu_mode == "await_confirm":
                xueqiu_result = queue_xueqiu_confirmation(
                    discussion,
                    feature_item,
                )
            else:
                xueqiu_result = publish_to_xueqiu(
                    discussion,
                    mode=args.xueqiu_mode,
                    headless=args.xueqiu_headless,
                )
        else:
            xueqiu_result = {
                "status": "skipped",
                "reason": "no_feature_item",
                "message": "当前没有可发布到雪球的候选快讯",
            }

    if args.json:
        print(
            json.dumps(
                {
                    "count": len(items),
                    "items": [item.__dict__ for item in items],
                    "digest": digest,
                    "xueqiu": xueqiu_result,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(digest)
        if xueqiu_result:
            print("")
            if xueqiu_result.get("status") == "awaiting_confirmation":
                print("=== 待确认雪球草稿 ===")
                print(f"草稿ID：{xueqiu_result.get('draftId')}")
                print(f"候选标题：{xueqiu_result.get('title')}")
                if xueqiu_result.get("draftPath"):
                    print(f"草稿文件：{xueqiu_result.get('draftPath')}")
                print("请先在 iMessage 确认正文，确认后回复：")
                print(f"确认发布雪球 {xueqiu_result.get('draftId')}")
                print("如果不发，回复：")
                print(f"取消雪球 {xueqiu_result.get('draftId')}")
                print("")
                print("---- BEGIN_XUEQIU_DRAFT ----")
                print(xueqiu_result.get("content", ""))
                print("---- END_XUEQIU_DRAFT ----")
            else:
                print("=== 雪球发布结果 ===")
                print(json.dumps(xueqiu_result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
