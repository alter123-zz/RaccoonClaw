"""Task 模型 — 现代公司架构任务核心表。

对应当前 tasks_source.json 中的每一条任务记录。
state 对应现代公司流程状态机：
  ChiefOfStaff → Planning → ReviewControl → Assigned → Doing → Review → Done
"""

import enum
import json
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Index,
    String,
    Text,
    Boolean,
    Integer,
    text,
    JSON,
)

from ..db import Base


WORKFLOW_PATH = Path(__file__).parents[4] / "shared" / "workflow-config.json"


class TaskState(str, enum.Enum):
    """任务状态枚举 — 映射现代公司协作流程。"""
    ChiefOfStaff = "ChiefOfStaff"           # 总裁办分诊
    Planning = "Planning"     # 产品规划部规划
    ReviewControl = "ReviewControl"         # 评审质控部审核
    Assigned = "Assigned"     # 交付运营部已将任务派发
    Next = "Next"             # 待执行
    Doing = "Doing"           # 专项团队执行中
    Review = "Review"         # 交付复核汇总
    Done = "Done"             # 完成
    Blocked = "Blocked"       # 阻塞
    Cancelled = "Cancelled"   # 取消
    Pending = "Pending"       # 待处理


@lru_cache(maxsize=1)
def _load_workflow_config() -> dict[str, object]:
    try:
        return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "terminalStates": ["Done", "Cancelled"],
            "stateTransitions": {
                "Pending": ["ChiefOfStaff", "Cancelled"],
                "ChiefOfStaff": ["Planning", "Cancelled"],
                "Planning": ["ReviewControl", "Cancelled", "Blocked"],
                "ReviewControl": ["Assigned", "Planning", "Cancelled"],
                "Assigned": ["Doing", "Next", "Cancelled", "Blocked"],
                "Next": ["Doing", "Cancelled"],
                "Doing": ["Review", "Done", "Blocked", "Cancelled"],
                "Review": ["Done", "Doing", "Cancelled"],
                "Blocked": ["ChiefOfStaff", "Planning", "ReviewControl", "Assigned", "Doing"]
            },
            "stateAgentMap": {
                "Pending": "planning",
                "ChiefOfStaff": "chief_of_staff",
                "Planning": "planning",
                "ReviewControl": "review_control",
                "Assigned": "delivery_ops",
                "Review": "delivery_ops"
            }
        }


def _task_state(name: str) -> TaskState:
    return TaskState(name)


# 终态集合
TERMINAL_STATES = {_task_state(state) for state in _load_workflow_config()["terminalStates"]}

# 状态流转合法路径
STATE_TRANSITIONS = {
    _task_state(state): {_task_state(next_state) for next_state in next_states}
    for state, next_states in _load_workflow_config()["stateTransitions"].items()
}

# 状态 → Agent 映射
STATE_AGENT_MAP = {
    _task_state(state): agent_id
    for state, agent_id in _load_workflow_config()["stateAgentMap"].items()
    if agent_id
}

REGISTRY_PATH = Path(__file__).parents[4] / "shared" / "agent-registry.json"


@lru_cache(maxsize=1)
def _load_org_agent_map() -> dict[str, str]:
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {
            "经营分析部": "business_analysis",
            "品牌内容部": "brand_content",
            "安全运维部": "secops",
            "合规测试部": "compliance_test",
            "工程研发部": "engineering",
            "人力组织部": "people_ops",
        }
    return {agent["label"]: agent["id"] for agent in registry}


# 组织 → Agent 映射（专项团队）
ORG_AGENT_MAP = _load_org_agent_map()


class Task(Base):
    """现代公司架构任务表。"""
    __tablename__ = "tasks"

    id = Column(String(32), primary_key=True, comment="任务ID, e.g. JJC-20260301-001")
    title = Column(Text, nullable=False, comment="任务标题")
    state = Column(Enum(TaskState, name="task_state"), nullable=False, default=TaskState.ChiefOfStaff, index=True)
    org = Column(String(32), nullable=False, default="总裁办", comment="当前执行团队")
    official = Column(String(32), default="", comment="责任角色")
    now = Column(Text, default="", comment="当前进展描述")
    eta = Column(String(64), default="-", comment="预计完成时间")
    block = Column(Text, default="无", comment="阻塞原因")
    output = Column(Text, default="", comment="最终产出")
    priority = Column(String(16), default="normal", comment="优先级")
    archived = Column(Boolean, default=False, index=True)

    # JSON 灵活字段
    flow_log = Column(JSON, default=list, comment="流转日志 [{at, from, to, remark}]")
    progress_log = Column(JSON, default=list, comment="进展日志 [{at, agent, text, todos}]")
    todos = Column(JSON, default=list, comment="子任务 [{id, title, status, detail}]")
    scheduler = Column(JSON, default=dict, comment="调度器元数据")
    template_id = Column(String(64), default="", comment="模板ID")
    template_params = Column(JSON, default=dict, comment="模板参数")
    ac = Column(Text, default="", comment="验收标准")
    target_dept = Column(String(64), default="", comment="目标部门")

    # 时间戳
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_tasks_state_archived", "state", "archived"),
        Index("ix_tasks_updated_at", "updated_at"),
    )

    def to_dict(self) -> dict:
        """序列化为 API 响应格式（兼容旧 live_status 格式）。"""
        return {
            "id": self.id,
            "title": self.title,
            "state": self.state.value if self.state else "",
            "org": self.org,
            "official": self.official,
            "now": self.now,
            "eta": self.eta,
            "block": self.block,
            "output": self.output,
            "priority": self.priority,
            "archived": self.archived,
            "flow_log": self.flow_log or [],
            "progress_log": self.progress_log or [],
            "todos": self.todos or [],
            "templateId": self.template_id,
            "templateParams": self.template_params or {},
            "ac": self.ac,
            "targetDept": self.target_dept,
            "_scheduler": self.scheduler or {},
            "createdAt": self.created_at.isoformat() if self.created_at else "",
            "updatedAt": self.updated_at.isoformat() if self.updated_at else "",
        }
