"""Redis Streams 事件总线 — 可靠的事件发布/消费。"""

import json
import logging
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any

try:
    import redis.asyncio as aioredis
    RedisResponseError = aioredis.ResponseError
except ModuleNotFoundError:
    aioredis = None
    class RedisResponseError(Exception): pass

from ..config import get_settings

log = logging.getLogger("edict.event_bus")

# Topic 常量
TOPIC_TASK_CREATED = "task.created"
TOPIC_TASK_PLANNING_REQUEST = "task.planning.request"
TOPIC_TASK_PLANNING_COMPLETE = "task.planning.complete"
TOPIC_TASK_REVIEW_REQUEST = "task.review.request"
TOPIC_TASK_REVIEW_RESULT = "task.review.result"
TOPIC_TASK_DISPATCH = "task.dispatch"
TOPIC_TASK_STATUS = "task.status"
TOPIC_TASK_COMPLETED = "task.completed"
TOPIC_TASK_CLOSED = "task.closed"
TOPIC_TASK_REPLAN = "task.replan"
TOPIC_TASK_STALLED = "task.stalled"
TOPIC_TASK_ESCALATED = "task.escalated"

TOPIC_AGENT_THOUGHTS = "agent.thoughts"
TOPIC_AGENT_TODO_UPDATE = "agent.todo.update"
TOPIC_AGENT_HEARTBEAT = "agent.heartbeat"

STREAM_PREFIX = "edict:stream:"

class EventBus:
    """具备 Redis 自动降级能力的事件总线。"""

    def __init__(self, redis_url: str | None = None):
        self._redis_url = redis_url or get_settings().redis_url
        self._redis: Any | None = None
        self._is_mock = False

    async def connect(self):
        """建立 Redis 连接，失败则进入 Mock 模式。"""
        if aioredis is None:
            log.warning("redis package not installed, entering MOCK mode")
            self._is_mock = True
            return

        try:
            self._redis = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                max_connections=20,
                socket_timeout=2.0,
                socket_connect_timeout=2.0
            )
            # 真实探测
            await asyncio.wait_for(self._redis.ping(), timeout=2.0)
            log.info(f"EventBus connected to Redis: {self._redis_url}")
            self._is_mock = False
        except Exception as e:
            log.warning(f"EventBus failed to connect to Redis: {e}. Entering MOCK mode (events will not be persisted/distributed).")
            self._is_mock = True
            self._redis = None

    async def close(self):
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    @property
    def redis(self) -> Any:
        return self._redis

    def _stream_key(self, topic: str) -> str:
        return f"{STREAM_PREFIX}{topic}"

    async def publish(
        self,
        topic: str,
        trace_id: str,
        event_type: str,
        producer: str,
        payload: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> str:
        event = {
            "event_id": str(uuid.uuid4()),
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "topic": topic,
            "event_type": event_type,
            "producer": producer,
            "payload": json.dumps(payload or {}, ensure_ascii=False),
            "meta": json.dumps(meta or {}, ensure_ascii=False),
        }
        
        if self._is_mock or not self._redis:
            log.debug(f"[MOCK] Published {topic}/{event_type} trace={trace_id}")
            return f"mock-{uuid.uuid4()}"

        try:
            stream_key = self._stream_key(topic)
            entry_id = await self._redis.xadd(stream_key, event, maxlen=10000)
            await self._redis.publish(f"edict:pubsub:{topic}", json.dumps(event, ensure_ascii=False))
            return entry_id
        except Exception as e:
            log.error(f"EventBus publish error: {e}")
            return "error"

    async def ensure_consumer_group(self, topic: str, group: str):
        if self._is_mock or not self._redis: return
        stream_key = self._stream_key(topic)
        try:
            await self._redis.xgroup_create(stream_key, group, id="0", mkstream=True)
        except RedisResponseError as e:
            if "BUSYGROUP" not in str(e): raise

    async def consume(self, topic: str, group: str, consumer: str, count: int = 10, block_ms: int = 5000) -> list:
        if self._is_mock or not self._redis: 
            await asyncio.sleep(block_ms / 1000.0)
            return []
        # ... 保持原 consume 逻辑 ...
        stream_key = self._stream_key(topic)
        results = await self._redis.xreadgroup(groupname=group, consumername=consumer, streams={stream_key: ">"}, count=count, block=block_ms)
        events = []
        if results:
            for _stream, messages in results:
                for entry_id, data in messages:
                    if "payload" in data: data["payload"] = json.loads(data["payload"])
                    if "meta" in data: data["meta"] = json.loads(data["meta"])
                    events.append((entry_id, data))
        return events

    async def ack(self, topic: str, group: str, entry_id: str):
        if self._is_mock or not self._redis: return
        await self._redis.xack(self._stream_key(topic), group, entry_id)

    async def claim_stale(
        self,
        topic: str,
        group: str,
        consumer: str,
        min_idle_ms: int = 60000,
        count: int = 10,
    ) -> list[tuple[str, dict]]:
        """认领超时未确认的消息（用于 worker 故障恢复）。"""
        if self._is_mock or not self._redis:
            return []
        stream_key = self._stream_key(topic)
        try:
            pending = await self._redis.xpending_range(
                stream_key, group, min="-", max="+", count=count
            )
            stale_ids = []
            for entry in pending:
                if entry.get("time_since_delivered", 0) >= min_idle_ms:
                    stale_ids.append(entry["message_id"])
            if not stale_ids:
                return []
            claimed = await self._redis.xclaim(
                stream_key, group, consumer, min_idle_ms, stale_ids
            )
            results = []
            for entry_id, data in claimed:
                if "payload" in data and isinstance(data["payload"], str):
                    data["payload"] = json.loads(data["payload"])
                if "meta" in data and isinstance(data["meta"], str):
                    data["meta"] = json.loads(data["meta"])
                results.append((entry_id, data))
            return results
        except Exception as e:
            log.error(f"EventBus claim_stale error: {e}")
            return []

    async def get_pending(
        self,
        topic: str,
        group: str,
        count: int = 20,
    ) -> list[dict]:
        """获取消费者组中待处理消息的摘要信息。"""
        if self._is_mock or not self._redis:
            return []
        stream_key = self._stream_key(topic)
        try:
            pending = await self._redis.xpending_range(
                stream_key, group, min="-", max="+", count=count
            )
            return [
                {
                    "message_id": entry.get("message_id", ""),
                    "consumer": entry.get("consumer", ""),
                    "idle_ms": entry.get("time_since_delivered", 0),
                    "delivery_count": entry.get("times_delivered", 0),
                }
                for entry in pending
            ]
        except Exception as e:
            log.error(f"EventBus get_pending error: {e}")
            return []

# ── 全局单例 ──
_bus: EventBus | None = None
_bus_lock = asyncio.Lock()


async def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        async with _bus_lock:
            if _bus is None:
                _bus = EventBus()
                await _bus.connect()
    return _bus
