"""Dashboard compatibility endpoints backed by legacy JSON/runtime helpers."""

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid

from ..config import get_settings
from ..services.legacy_dashboard import (
    ensure_live_status_fresh,
    get_agents_status,
    read_json_file,
)
from ..services.legacy_server_bridge import (
    add_model_catalog_entry,
    add_remote_skill,
    add_skill,
    advance_state,
    archive_task,
    delete_im_channel,
    create_chat_session,
    remove_chat_attachment,
    upload_chat_attachments,
    connect_feishu_channel,
    create_task,
    get_chat_session,
    get_toolbox_status,
    get_available_skills_catalog,
    list_chat_sessions,
    open_local_path,
    get_im_channels_status,
    get_remote_skills_list,
    get_scheduler_state,
    get_task_activity,
    test_im_channel,
    queue_model_change,
    read_skill_content,
    remove_remote_skill,
    review_action,
    run_toolbox_action,
    scheduler_escalate,
    scheduler_retry,
    scheduler_rollback,
    scheduler_scan,
    send_chat_message,
    task_action,
    test_model_connection,
    toggle_im_channel,
    upsert_im_channel,
    update_remote_skill,
    update_task_todos,
    wake_agent,
)
from ..services.runtime_bootstrap import (
    get_bootstrap_status,
    get_desktop_startup_status,
    provision_openclaw_runtime,
)


router = APIRouter()

# --- Pydantic Models ---

class SetModelBody(BaseModel):
    agentId: str
    model: str


class AddModelBody(BaseModel):
    vendorKey: str
    modelId: str
    modelName: str
    vendorLabel: str = ""
    baseUrl: str = ""
    apiProtocol: str = "openai"
    apiKey: str = ""
    authHeader: bool = True
    reasoning: bool = False
    contextWindow: Optional[int] = None
    maxTokens: Optional[int] = None


class TestModelBody(BaseModel):
    baseUrl: str
    apiProtocol: str = "openai"
    modelId: str
    apiKey: str = ""

class AgentWakeBody(BaseModel):
    agentId: str
    message: str = ""

class TaskActionBody(BaseModel):
    taskId: str
    action: str
    reason: Optional[str] = ""

class ReviewActionBody(BaseModel):
    taskId: str
    action: str
    comment: Optional[str] = ""

class AdvanceStateBody(BaseModel):
    taskId: str
    comment: Optional[str] = ""

class ArchiveTaskBody(BaseModel):
    taskId: str = ""
    archived: bool = True
    archiveAllDone: bool = False

class TaskTodosBody(BaseModel):
    taskId: str
    todos: List[dict]

class CreateTaskBody(BaseModel):
    title: str
    org: str = "产品规划部"
    official: str = "产品规划负责人"
    priority: str = "normal"
    templateId: str = ""
    params: dict = Field(default_factory=dict)
    targetDept: str = ""
    modeId: str = ""
    flowMode: str = "full"

class AddSkillBody(BaseModel):
    agentId: str
    skillName: str = ""
    name: str = ""
    description: str = ""
    trigger: str = ""

class AddRemoteSkillBody(BaseModel):
    agentId: str
    skillName: str
    sourceUrl: str
    description: str = ""


class ImChannelBody(BaseModel):
    channelKey: str
    enabled: Optional[bool] = True
    setupMode: str = ""
    config: dict = Field(default_factory=dict)


class ImChannelToggleBody(BaseModel):
    channelKey: str
    enabled: bool


class ImChannelDeleteBody(BaseModel):
    channelKey: str

# --- Core Routes ---

@router.get("/live-status")
async def live_status():
    return ensure_live_status_fresh()

@router.get("/agent-config")
async def agent_config():
    return read_json_file("agent_config.json", {"agents": []})

@router.get("/available-skills")
async def available_skills():
    return get_available_skills_catalog()


@router.get("/im-channels/status")
async def im_channels_status():
    return get_im_channels_status()


@router.get("/public-config")
async def public_config_route():
    settings = get_settings()
    return {
        "edition": "community",
        "dataProfile": settings.raccoonclaw_data_profile,
        "features": {
            "imChannels": bool(settings.raccoonclaw_enable_im_channels),
            "toolbox": bool(settings.raccoonclaw_enable_toolbox),
            "scheduledTasks": bool(settings.raccoonclaw_enable_scheduled_tasks),
            "automationMirrors": bool(settings.raccoonclaw_enable_automation_mirrors),
        },
    }

# --- Skill Routes (FULLY RESTORED) ---

@router.post("/add-skill")
async def add_skill_route(body: AddSkillBody):
    return add_skill(body.agentId.strip(), (body.skillName or body.name).strip(), body.description.strip(), body.trigger.strip())

@router.post("/add-remote-skill")
async def add_remote_skill_route(body: AddRemoteSkillBody):
    return add_remote_skill(body.agentId.strip(), body.skillName.strip(), body.sourceUrl.strip(), body.description.strip())

@router.post("/remove-remote-skill")
async def remove_remote_skill_route(body: dict):
    return remove_remote_skill(body.get("agentId", "").strip(), body.get("skillName", "").strip())

@router.get("/skill-content/{agent_id}/{skill_name}")
async def skill_content(agent_id: str, skill_name: str):
    return read_skill_content(agent_id, skill_name)

# --- Chat Routes (FULLY RESTORED) ---

@router.get("/chat/sessions")
async def chat_sessions():
    return list_chat_sessions()

@router.post("/chat/sessions")
async def chat_new_session(body: dict = None):
    title = body.get("title", "") if body else ""
    return create_chat_session(title)

@router.get("/chat/sessions/{session_id}")
async def chat_session_detail(session_id: str):
    return get_chat_session(session_id)

@router.post("/chat/sessions/{session_id}/attachments")
async def chat_session_upload_attachments(session_id: str, files: List[UploadFile] = File(...)):
    payload: list[dict] = []
    for item in files:
        payload.append(
            {
                "filename": item.filename or "attachment",
                "contentType": item.content_type or "",
                "content": await item.read(),
            }
        )
    return upload_chat_attachments(session_id, payload)

@router.post("/chat/sessions/{session_id}/attachments/remove")
async def chat_session_remove_attachment(session_id: str, body: dict):
    return remove_chat_attachment(session_id, body.get("attachmentId", ""))

@router.post("/chat/sessions/{session_id}/send")
async def chat_session_send(session_id: str, body: dict):
    return send_chat_message(session_id, body.get("content", ""))

# --- Task & Scheduler Routes (FULLY RESTORED) ---

@router.post("/create-task")
async def create_task_route(body: CreateTaskBody):
    return create_task(
        body.title.strip(), body.org.strip(), body.official.strip(),
        body.priority.strip(), body.templateId, body.params,
        body.targetDept.strip(), body.modeId.strip(), body.flowMode.strip()
    )

@router.post("/task-action")
async def task_action_route(body: TaskActionBody):
    return task_action(body.taskId.strip(), body.action.strip(), body.reason.strip() if body.reason else "")

@router.post("/review-action")
async def review_action_route(body: ReviewActionBody):
    return review_action(body.taskId.strip(), body.action.strip(), body.comment.strip() if body.comment else "")

@router.post("/advance-state")
async def advance_state_route(body: AdvanceStateBody):
    return advance_state(body.taskId.strip(), body.comment.strip() if body.comment else "")

@router.post("/task-todos")
async def task_todos_route(body: TaskTodosBody):
    return update_task_todos(body.taskId.strip(), body.todos)

@router.post("/scheduler-scan")
async def scheduler_scan_route(body: dict):
    return scheduler_scan(body.get("thresholdSec", 180))

@router.post("/scheduler-retry")
async def scheduler_retry_route(body: dict):
    return scheduler_retry(body.get("taskId", "").strip(), body.get("reason", "").strip())

@router.post("/scheduler-escalate")
async def scheduler_escalate_route(body: dict):
    return scheduler_escalate(body.get("taskId", "").strip(), body.get("reason", "").strip())

@router.post("/scheduler-rollback")
async def scheduler_rollback_route(body: dict):
    return scheduler_rollback(body.get("taskId", "").strip(), body.get("reason", "").strip())

@router.post("/open-path")
async def open_path_route(body: dict):
    return open_local_path(body.get("path", ""))

@router.post("/archive-task")
async def archive_task_route(body: ArchiveTaskBody):
    return archive_task(body.taskId.strip(), body.archived, body.archiveAllDone)

# --- Management Routes ---

@router.post("/set-model")
async def set_model_route(body: SetModelBody):
    return queue_model_change(body.agentId.strip(), body.model.strip())


@router.post("/add-model")
async def add_model_route(body: AddModelBody):
    return add_model_catalog_entry(
        body.vendorKey.strip(),
        body.modelId.strip(),
        body.modelName.strip(),
        body.vendorLabel.strip(),
        body.baseUrl.strip(),
        body.apiProtocol.strip(),
        body.apiKey.strip(),
        body.authHeader,
        body.reasoning,
        body.contextWindow,
        body.maxTokens,
    )


@router.post("/test-model")
async def test_model_route(body: TestModelBody):
    return test_model_connection(
        body.baseUrl.strip(),
        body.apiProtocol.strip(),
        body.modelId.strip(),
        body.apiKey.strip(),
    )

@router.post("/agent-wake")
async def agent_wake_route(body: AgentWakeBody):
    return wake_agent(body.agentId.strip(), body.message.strip())

@router.post("/toolbox/action")
async def toolbox_action_route(body: dict):
    return run_toolbox_action(body.get("action", ""))


@router.post("/im-channels/upsert")
async def im_channels_upsert_route(body: ImChannelBody):
    return upsert_im_channel(
        body.channelKey.strip(),
        bool(body.enabled),
        body.setupMode.strip(),
        body.config,
    )


@router.post("/im-channels/toggle")
async def im_channels_toggle_route(body: ImChannelToggleBody):
    return toggle_im_channel(body.channelKey.strip(), body.enabled)


@router.post("/im-channels/delete")
async def im_channels_delete_route(body: ImChannelDeleteBody):
    return delete_im_channel(body.channelKey.strip())


@router.post("/im-channels/test")
async def im_channels_test_route(body: ImChannelBody):
    return test_im_channel(body.channelKey.strip(), body.config)

@router.get("/toolbox/status")
async def toolbox_status_route():
    return get_toolbox_status()

@router.get("/bootstrap-status")
async def bootstrap_status_route():
    return get_bootstrap_status()


@router.post("/bootstrap/provision")
async def bootstrap_provision_route():
    return provision_openclaw_runtime()


@router.get("/desktop/startup-status")
async def desktop_startup_status():
    return get_desktop_startup_status()

@router.get("/officials-stats")
async def officials_stats():
    return read_json_file("officials_stats.json", {"officials": []})
