"""任务服务层 — CRUD + 状态机逻辑。"""

import json
import logging
from datetime import datetime, timezone
from typing import Any
from pathlib import Path
import sys

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.task import Task, TaskState, STATE_TRANSITIONS, TERMINAL_STATES
from .event_bus import (
    EventBus,
    TOPIC_TASK_CREATED,
    TOPIC_TASK_STATUS,
    TOPIC_TASK_COMPLETED,
    TOPIC_TASK_DISPATCH,
)

log = logging.getLogger("edict.task_service")

# 寻找 tasks_source.json 的可能位置
PROJECT_ROOT = Path(__file__).parents[4]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from runtime_paths import canonical_data_dir  # type: ignore

JSON_DATA_PATH = PROJECT_ROOT / "docker" / "demo_data" / "tasks_source.json"
RUNTIME_DATA_PATH = canonical_data_dir() / "tasks_source.json"

class TaskService:
    def __init__(self, db: AsyncSession, event_bus: EventBus):
        self.db = db
        self.bus = event_bus

    async def sync_from_json(self):
        """从 JSON 文件同步新任务到数据库（兼容旧脚本逻辑）。"""
        paths = [RUNTIME_DATA_PATH, JSON_DATA_PATH]
        synced_count = 0
        
        for p in paths:
            if not p.exists():
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                for item in data:
                    task_id = item.get("id")
                    if not task_id: continue
                    
                    # 检查是否已存在
                    existing = await self.db.get(Task, task_id)
                    if not existing:
                        task = Task(
                            id=task_id,
                            title=item.get("title", "无标题"),
                            state=TaskState(item.get("state", "ChiefOfStaff")),
                            org=item.get("org", "总裁办"),
                            official=item.get("official", ""),
                            now=item.get("now", ""),
                            eta=item.get("eta", "-"),
                            block=item.get("block", "无"),
                            output=item.get("output", ""),
                            flow_log=item.get("flow_log", []),
                            todos=item.get("todos", []),
                            ac=item.get("ac", ""),
                            target_dept=item.get("targetDept", ""),
                        )
                        self.db.add(task)
                        synced_count += 1
                
                if synced_count > 0:
                    await self.db.commit()
                    log.info(f"Synced {synced_count} tasks from {p.name}")
            except Exception as exc:
                log.warning(f"Failed to sync from {p}: {exc}")
        return synced_count

    # ── 创建 ──

    async def create_task(
        self,
        id: str,
        title: str,
        state: TaskState = TaskState.ChiefOfStaff,
        org: str = "总裁办",
        official: str = "",
        priority: str = "normal",
        **kwargs
    ) -> Task:
        """创建任务并发布 task.created 事件。"""
        now = datetime.now(timezone.utc)

        task = Task(
            id=id,
            title=title,
            state=state,
            org=org,
            official=official,
            priority=priority,
            created_at=now,
            updated_at=now,
            flow_log=[
                {
                    "from": None,
                    "to": state.value,
                    "agent": "system",
                    "reason": "任务创建",
                    "ts": now.isoformat(),
                }
            ],
            **kwargs
        )
        self.db.add(task)
        await self.db.flush()

        # 发布事件
        await self.bus.publish(
            topic=TOPIC_TASK_CREATED,
            trace_id=id,
            event_type="task.created",
            producer="task_service",
            payload={
                "task_id": id,
                "title": title,
                "state": state.value,
                "priority": priority,
                "org": org,
            },
        )

        await self.db.commit()
        log.info(f"Created task {id}: {title} [{state.value}]")
        return task

    # ── 状态流转 ──

    async def transition_state(
        self,
        task_id: str,
        new_state: TaskState,
        agent: str = "system",
        reason: str = "",
    ) -> Task:
        """执行状态流转，校验合法性。"""
        task = await self._get_task(task_id)
        old_state = task.state

        # 校验合法流转
        allowed = STATE_TRANSITIONS.get(old_state, set())
        if new_state not in allowed:
            log.warning(f"Unexpected transition: {old_state.value} → {new_state.value}")

        task.state = new_state
        task.updated_at = datetime.now(timezone.utc)

        # 记入 flow_log
        flow_entry = {
            "from": old_state.value,
            "to": new_state.value,
            "agent": agent,
            "reason": reason,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if task.flow_log is None:
            task.flow_log = []
        task.flow_log = [*task.flow_log, flow_entry]

        # 发布状态变更事件
        topic = TOPIC_TASK_COMPLETED if new_state in TERMINAL_STATES else TOPIC_TASK_STATUS
        await self.bus.publish(
            topic=topic,
            trace_id=task_id,
            event_type=f"task.state.{new_state.value}",
            producer=agent,
            payload={
                "task_id": task_id,
                "from": old_state.value,
                "to": new_state.value,
                "reason": reason,
            },
        )

        await self.db.commit()
        log.info(f"Task {task_id} state: {old_state.value} → {new_state.value} by {agent}")
        return task

    # ── 查询 ──

    async def get_task(self, task_id: str) -> Task:
        return await self._get_task(task_id)

    async def list_tasks(
        self,
        state: TaskState | None = None,
        org: str | None = None,
        priority: str | None = None,
        archived: bool = False,
        limit: int = 100,
    ) -> list[Task]:
        stmt = select(Task).where(Task.archived == archived)
        if state:
            stmt = stmt.where(Task.state == state)
        if org:
            stmt = stmt.where(Task.org == org)
        if priority:
            stmt = stmt.where(Task.priority == priority)
        
        stmt = stmt.order_by(Task.updated_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_live_status(self) -> dict[str, Any]:
        """生成兼容旧 live_status.json 格式的全局状态。"""
        # 先尝试同步
        await self.sync_from_json()
        
        tasks = await self.list_tasks(limit=300)
        
        return {
            "tasks": [t.to_dict() for t in tasks],
            "syncStatus": {"ok": True, "lastSync": datetime.now().isoformat()},
            "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # ── 内部 ──

    async def _get_task(self, task_id: str) -> Task:
        task = await self.db.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        return task
