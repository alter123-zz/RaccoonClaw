"""通知服务 — 对接 channels 库与现有 IM 配置。

订阅以下事件 topic，触发对应渠道通知：
- task.completed  → 任务完成通知
- task.escalated  → 任务升级通知
- task.created    → 新建任务通知（可选）
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .event_bus import EventBus, TOPIC_TASK_COMPLETED, TOPIC_TASK_ESCALATED, TOPIC_TASK_CREATED
from .legacy_dashboard import data_dir
from ..channels import get_channel, get_channel_info


log = logging.getLogger("edict.notification")

NOTIFICATION_TOPICS = {
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_ESCALATED,
    TOPIC_TASK_CREATED,
}


class NotificationService:
    """事件驱动的通知服务。"""

    def __init__(self, bus: EventBus):
        self.bus = bus
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        """启动通知服务（订阅各 topic）。"""
        await self.bus.connect()
        self._running = True
        log.info("📬 Notification service started")

        for topic in NOTIFICATION_TOPICS:
            t = asyncio.create_task(self._subscribe(topic))
            self._tasks.append(t)

    async def stop(self):
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        log.info("📬 Notification service stopped")

    async def _subscribe(self, topic: str):
        """持续订阅单个 topic，收到事件后发送通知。"""
        group = f"notif-{topic.replace('.', '_')}"
        await self.bus.ensure_consumer_group(topic, group)

        while self._running:
            try:
                events = await self.bus.consume(topic, group, f"notif-1", count=5, block_ms=3000)
                for entry_id, event in events:
                    try:
                        await self._handle_event(topic, event)
                        await self.bus.ack(topic, group, entry_id)
                    except Exception as e:
                        log.error(f"Notification handler error: {e}")
            except Exception as e:
                log.error(f"Subscribe error for {topic}: {e}")
                await asyncio.sleep(2)

    async def _handle_event(self, topic: str, event: dict):
        """根据 topic 构造通知内容并发送。"""
        payload = event.get("payload", {})
        event_type = event.get("event_type", "")

        if topic == TOPIC_TASK_COMPLETED:
            title = "✅ 任务已完成"
            content = self._format_completed(payload)
        elif topic == TOPIC_TASK_ESCALATED:
            title = "🔺 任务已升级"
            content = self._format_escalated(payload)
        elif topic == TOPIC_TASK_CREATED:
            title = "🆕 新任务创建"
            content = self._format_created(payload)
        else:
            return

        await self._notify_all_channels(title, content)

    # ── 内容格式化 ────────────────────────────────────────────────────────────

    def _format_completed(self, payload: dict) -> str:
        task_id = payload.get("task_id", "?")
        title = payload.get("title", payload.get("task_id", ""))
        state = payload.get("state", "Done")
        return f"**{title}**\n任务ID: `{task_id}`\n最终状态: {state}"

    def _format_escalated(self, payload: dict) -> str:
        task_id = payload.get("task_id", "?")
        reason = payload.get("reason", "未明确原因")
        return f"**任务升级提醒**\n任务ID: `{task_id}`\n原因: {reason}"

    def _format_created(self, payload: dict) -> str:
        task_id = payload.get("task_id", "?")
        title = payload.get("title", "?")
        priority = payload.get("priority", "中")
        return f"**{title}**\n任务ID: `{task_id}`\n优先级: {priority}"

    # ── 渠道分发 ──────────────────────────────────────────────────────────────

    async def _notify_all_channels(self, title: str, content: str, url: str | None = None):
        """从 IM 配置读取所有已启用渠道，逐一发送。"""
        channels_cfg = self._load_im_channels()
        sent = 0
        for channel_key, channel_cfg in channels_cfg.items():
            if not self._is_channel_enabled(channel_cfg):
                continue
            webhook = self._get_webhook(channel_key, channel_cfg)
            if not webhook:
                continue
            ch = get_channel(channel_key)
            if ch is None:
                continue
            try:
                ok = ch.send(webhook, title, content, url)
                if ok:
                    sent += 1
                    log.info(f"Notification sent via {channel_key}")
                else:
                    log.warning(f"Failed to send via {channel_key}")
            except Exception as e:
                log.error(f"Error sending via {channel_key}: {e}")
        log.info(f"Notified {sent} channels for: {title[:40]}")

    # ── IM 配置读取 ───────────────────────────────────────────────────────────

    def _load_im_channels(self) -> dict[str, Any]:
        try:
            import json
            path = data_dir() / "im_channels.json"
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return data.get("channels", {})
        except Exception:
            pass
        return {}

    def _is_channel_enabled(self, cfg: dict) -> bool:
        return bool(cfg.get("enabled", False))

    def _get_webhook(self, channel_key: str, cfg: dict) -> str | None:
        """从渠道配置中提取 webhook URL。"""
        # 飞书/企微用 webhook
        if channel_key in ("feishu", "wecom"):
            return cfg.get("webhook") or cfg.get("url") or None
        # Telegram 用 bot token + chat_id
        if channel_key == "telegram":
            bot_token = cfg.get("botToken") or cfg.get("token")
            chat_id = cfg.get("chatId") or cfg.get("chat_id")
            if bot_token and chat_id:
                return f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}"
        # Discord 用 webhook URL
        if channel_key == "discord":
            return cfg.get("webhookUrl") or cfg.get("webhook") or None
        # Slack 用 webhook URL
        if channel_key == "slack":
            return cfg.get("webhookUrl") or cfg.get("webhook") or None
        # Generic webhook
        return cfg.get("webhook") or cfg.get("url") or None
