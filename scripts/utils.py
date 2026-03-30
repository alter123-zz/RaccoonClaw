#!/usr/bin/env python3
"""
现代公司架构 · 公共工具函数
避免 read_json / now_iso 等基础函数在多个脚本中重复定义
"""
import json, pathlib, datetime
from zoneinfo import ZoneInfo


BEIJING_TZ = ZoneInfo('Asia/Shanghai')


def read_json(path, default=None):
    """安全读取 JSON 文件，失败返回 default"""
    try:
        return json.loads(pathlib.Path(path).read_text())
    except Exception:
        return default if default is not None else {}


def now_iso():
    """返回 UTC ISO 8601 时间字符串（末尾 Z）"""
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')


def beijing_now():
    """返回北京时间 aware datetime。"""
    return datetime.datetime.now(BEIJING_TZ)


def parse_datetime(value):
    """解析时间值，并统一转为北京时间。"""
    if value is None or value == '':
        return None

    if isinstance(value, datetime.datetime):
        return value.astimezone(BEIJING_TZ) if value.tzinfo else value.replace(tzinfo=BEIJING_TZ)

    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day, tzinfo=BEIJING_TZ)

    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.datetime.fromtimestamp(ts, tz=BEIJING_TZ)

    raw = str(value).strip()
    if not raw:
        return None

    normalized = raw
    if raw.endswith('Z'):
        normalized = raw.replace('Z', '+00:00')
    elif ' ' in raw and 'T' not in raw:
        normalized = raw.replace(' ', 'T')

    try:
        parsed = datetime.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.astimezone(BEIJING_TZ) if parsed.tzinfo else parsed.replace(tzinfo=BEIJING_TZ)


def format_beijing(value, fmt='%Y-%m-%d %H:%M:%S'):
    """将时间值格式化为北京时间字符串。"""
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    return parsed.strftime(fmt)


def today_str(fmt='%Y%m%d'):
    """返回北京时间今天日期字符串，默认 YYYYMMDD"""
    return beijing_now().strftime(fmt)


def safe_name(s: str) -> bool:
    """检查名称是否只含安全字符（字母、数字、下划线、连字符、中文）"""
    import re
    return bool(re.match(r'^[a-zA-Z0-9_\-\u4e00-\u9fff]+$', s))


def validate_url(url: str, allowed_schemes=('https',), allowed_domains=None) -> bool:
    """校验 URL 合法性，防 SSRF"""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if parsed.scheme not in allowed_schemes:
            return False
        if allowed_domains and parsed.hostname not in allowed_domains:
            return False
        if not parsed.hostname:
            return False
        # 禁止内网地址
        import ipaddress
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_reserved:
                return False
        except ValueError:
            pass  # hostname 不是 IP，放行
        return True
    except Exception:
        return False
