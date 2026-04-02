"""Regression checks for desktop bootstrap and task routing.

These tests avoid pytest so they can run with plain `python3`.
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import tempfile
import time
import unittest
import types
from types import SimpleNamespace
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "edict" / "backend"))

if "pydantic_settings" not in sys.modules:
    pydantic_settings = types.ModuleType("pydantic_settings")

    class _BaseSettings:
        def __init__(self, **kwargs):
            annotations = getattr(self.__class__, "__annotations__", {})
            for field in annotations:
                if field in kwargs:
                    value = kwargs[field]
                else:
                    value = getattr(self.__class__, field, None)
                setattr(self, field, value)

    pydantic_settings.BaseSettings = _BaseSettings
    sys.modules["pydantic_settings"] = pydantic_settings

import server as dashboard_server  # type: ignore
from app import main as backend_main  # type: ignore
from app.services import legacy_server_bridge as bridge  # type: ignore
from app.services import runtime_bootstrap as bootstrap  # type: ignore


class DesktopRegressionTests(unittest.TestCase):
    def test_backend_lifespan_warms_live_status_once(self) -> None:
        class _FakeTask:
            def cancel(self) -> None:
                return None

            def __await__(self):
                async def _done():
                    return None

                return _done().__await__()

        bus = SimpleNamespace(close=mock.AsyncMock())

        async def _run() -> None:
            def _fake_create_task(coro):
                coro.close()
                return _FakeTask()

            with mock.patch.object(backend_main, "ensure_live_status_fresh", return_value={"tasks": []}) as warmup, mock.patch.object(
                backend_main, "get_event_bus", new=mock.AsyncMock(return_value=bus)
            ), mock.patch.object(
                backend_main.asyncio, "create_task", side_effect=_fake_create_task
            ), mock.patch.object(
                backend_main, "write_startup_probe"
            ):
                async with backend_main.lifespan(backend_main.app):
                    pass
                warmup.assert_called_once()

        asyncio.run(_run())

    def test_desktop_scheduler_scan_blocks_until_startup_ready(self) -> None:
        startup = {
            "ready": False,
            "summary": "组织配置未导入",
            "detail": "需要先完成组织配置导入",
        }
        with mock.patch.object(bridge, "_desktop_mode_enabled", return_value=True), mock.patch.object(
            bridge,
            "get_desktop_startup_status",
            return_value=startup,
        ), mock.patch.object(bridge, "load_legacy_server_module") as load_server:
            result = bridge.scheduler_scan(180)

        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertIn("组织配置未导入", result["message"])
        load_server.assert_not_called()

    def test_desktop_scheduler_scan_matches_web_after_startup_ready(self) -> None:
        fake_server = SimpleNamespace(handle_scheduler_scan=mock.Mock(return_value={"ok": True, "count": 2}))
        with mock.patch.object(bridge, "_desktop_mode_enabled", return_value=True), mock.patch.object(
            bridge,
            "get_desktop_startup_status",
            return_value={"ready": True},
        ), mock.patch.object(bridge, "load_legacy_server_module", return_value=fake_server):
            result = bridge.scheduler_scan(180)

        self.assertTrue(result["ok"])
        self.assertEqual(result["count"], 2)
        fake_server.handle_scheduler_scan.assert_called_once_with(180)

    def test_desktop_backend_source_always_starts_scheduler_loop(self) -> None:
        source = (ROOT / "edict" / "backend" / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('scheduler_task = asyncio.create_task(scheduler_loop())', source)
        self.assertNotIn('if not desktop_mode:\n        scheduler_task = asyncio.create_task(scheduler_loop())', source)

    def test_desktop_root_is_blocked_before_serving_dashboard(self) -> None:
        with mock.patch.object(backend_main, "_desktop_setup_block_response", return_value=backend_main.HTMLResponse("blocked", status_code=503)):
            response = asyncio.run(backend_main.dashboard_root())

        self.assertEqual(response.status_code, 503)
        self.assertIn(b"blocked", response.body)

    def test_desktop_setup_block_page_exposes_bootstrap_action(self) -> None:
        startup_status = {
            "ready": False,
            "summary": "组织配置未导入",
            "detail": "需要导入组织配置",
            "recommendedAction": "bootstrap",
            "cliInstalled": True,
            "statusOutput": "gateway not ready",
        }
        with mock.patch.object(backend_main, "_desktop_mode_enabled", return_value=True), mock.patch.object(
            backend_main,
            "get_desktop_startup_status",
            return_value=startup_status,
        ):
            response = backend_main._desktop_setup_block_response()

        self.assertIsNotNone(response)
        assert response is not None
        body = response.body.decode("utf-8")
        self.assertIn("/api/bootstrap/provision", body)
        self.assertIn("一键初始化并导入 OpenClaw 工作台", body)

    def test_desktop_startup_keeps_bootstrap_gate_when_gateway_ok(self) -> None:
        bootstrap_status = {
            "ok": True,
            "ready": False,
            "recommendedAction": "bootstrap",
            "summary": "组织配置未导入",
            "detail": "需要导入组织配置",
            "cliInstalled": True,
            "cliPath": "/usr/local/bin/openclaw",
            "runtimeAgentIds": [],
            "chiefOfStaffRuntimeReady": False,
            "configExists": True,
            "openclawHome": "/tmp/openclaw-home",
            "missingAgents": ["chief_of_staff"],
            "missingWorkspaces": [],
            "missingSoul": [],
            "missingScripts": [],
            "missingSkills": [],
            "missingDataFiles": [],
        }
        gateway_status = {
            "gatewayStatusOk": True,
            "gatewayReachable": True,
            "gatewayDashboardUrl": "http://127.0.0.1:18789",
            "gatewaySummary": "gateway 已就绪",
            "gatewayDetail": "ok",
            "gatewayRecommendedAction": "none",
            "gatewayOutput": "ok",
        }
        with mock.patch.object(bootstrap, "get_bootstrap_status", return_value=bootstrap_status), mock.patch.object(
            bootstrap, "_gateway_status_details", return_value=gateway_status
        ):
            status = bootstrap.get_desktop_startup_status()

        self.assertFalse(status["ready"])
        self.assertEqual(status["recommendedAction"], "bootstrap")
        self.assertEqual(status["summary"], "组织配置未导入")
        self.assertTrue(status["gatewayStatusOk"])

    def test_dashboard_api_source_exposes_bootstrap_routes(self) -> None:
        source = (ROOT / "edict" / "backend" / "app" / "api" / "dashboard.py").read_text(encoding="utf-8")
        self.assertIn('@router.get("/bootstrap-status")', source)
        self.assertIn('@router.post("/bootstrap/provision")', source)
        self.assertIn('@router.post("/scheduler-retry")', source)

    def test_runtime_script_sync_includes_task_ids_dependency(self) -> None:
        self.assertIn("task_ids.py", bootstrap.WORKSPACE_RUNTIME_SCRIPTS)
        import sync_agent_config  # type: ignore

        self.assertIn("task_ids.py", sync_agent_config._WORKSPACE_RUNTIME_SCRIPTS)
        self.assertNotIn("take_screenshots.py", sync_agent_config._WORKSPACE_RUNTIME_SCRIPTS)
        self.assertNotIn("fetch_morning_news.py", sync_agent_config._WORKSPACE_RUNTIME_SCRIPTS)

    def test_sync_agent_config_prunes_unmanaged_runtime_scripts(self) -> None:
        import sync_agent_config  # type: ignore

        with tempfile.TemporaryDirectory() as tmp:
            ws_scripts = pathlib.Path(tmp) / "scripts"
            ws_scripts.mkdir(parents=True, exist_ok=True)
            project_script = pathlib.Path(tmp) / "kanban_update.py"
            project_script.write_text("print('ok')\n", encoding="utf-8")
            (ws_scripts / "take_screenshots.py").write_text("legacy\n", encoding="utf-8")

            changed = sync_agent_config._sync_scripts_into(ws_scripts, [project_script])

            self.assertGreaterEqual(changed, 2)
            self.assertTrue((ws_scripts / "kanban_update.py").exists())
            self.assertFalse((ws_scripts / "take_screenshots.py").exists())

    def test_chat_formal_request_creates_jjc_instead_of_runtime_chat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "chat_sessions.json").write_text(json.dumps({"sessions": []}), encoding="utf-8")

            with mock.patch.object(bridge, "data_dir", return_value=data_dir):
                created = bridge.create_chat_session("")
                session_id = created["session"]["id"]

                council = {
                    "classification": "create_task",
                    "dispatchOrg": "产品规划部",
                    "dispatchAgent": "planning",
                    "flowMode": "full",
                    "titleHint": "调研 Minimax M2.7 模型能力与适用场景报告",
                }

                with mock.patch.object(bridge, "_analyze_chat_route", return_value=council), mock.patch.object(
                    bridge,
                    "create_task",
                    return_value={"ok": True, "taskId": "JJC-TEST-001"},
                ), mock.patch.object(bridge, "_run_toolbox_command") as runtime_call:
                    result = bridge.send_chat_message(session_id, "调研 Minimax M2.7")

                self.assertTrue(result["ok"])
                assistant = result["session"]["messages"][-1]
                self.assertIn("JJC-TEST-001", assistant["content"])
                self.assertEqual(assistant["meta"]["routeMode"], "create_task")
                runtime_call.assert_not_called()

    def test_chat_direct_request_answers_without_creating_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "chat_sessions.json").write_text(json.dumps({"sessions": []}), encoding="utf-8")
            (data_dir / "tasks_source.json").write_text("[]", encoding="utf-8")

            with mock.patch.object(bridge, "data_dir", return_value=data_dir):
                created = bridge.create_chat_session("")
                session_id = created["session"]["id"]

                council = {
                    "classification": "direct_handle",
                    "flowMode": "direct",
                    "routeMode": "direct_handle",
                }
                runtime_payload = {
                    "result": {
                        "payloads": [{"text": "We will get back to you by next Monday."}],
                        "meta": {},
                    }
                }

                with mock.patch.object(bridge, "_analyze_chat_route", return_value=council), mock.patch.object(
                    bridge,
                    "create_task",
                ) as create_task_mock, mock.patch.object(
                    bridge,
                    "_run_toolbox_command",
                    return_value={"ok": True, "stdout": json.dumps(runtime_payload, ensure_ascii=False), "stderr": "", "message": "", "code": 0},
                ):
                    result = bridge.send_chat_message(session_id, "把这句话翻译成英文：我们会在下周一前给你答复")

                self.assertTrue(result["ok"])
                assistant = result["session"]["messages"][-1]
                self.assertIn("We will get back to you by next Monday.", assistant["content"])
                create_task_mock.assert_not_called()

    def test_chat_session_syncs_task_completion_notice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            session_id = "chat-test-001"
            (data_dir / "chat_sessions.json").write_text(
                json.dumps(
                    {
                        "sessions": [
                            {
                                "id": session_id,
                                "title": "新对话",
                                "createdAt": "2026-03-28T20:00:00",
                                "updatedAt": "2026-03-28T20:00:00",
                                "messages": [],
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data_dir / "tasks_source.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "L-20260328-003",
                            "title": "整理产品发布朋友圈文案",
                            "state": "Done",
                            "updatedAt": "2026-03-28T20:10:00",
                            "output": "/tmp/output.md",
                            "sourceMeta": {
                                "chatSessionId": session_id,
                                "flowMode": "light",
                            },
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with mock.patch.object(bridge, "data_dir", return_value=data_dir):
                result = bridge.get_chat_session(session_id)

            self.assertTrue(result["ok"])
            messages = result["session"]["messages"]
            self.assertEqual(len(messages), 1)
            self.assertIn("任务 L-20260328-003 已完成", messages[0]["content"])
            self.assertEqual(messages[0]["meta"]["taskId"], "L-20260328-003")
            self.assertTrue(messages[0]["meta"]["taskCompletion"])

    def test_analyze_chat_route_reloads_council_modules(self) -> None:
        stale_intake = types.ModuleType("intake_guard")
        fresh_intake = types.ModuleType("intake_guard")
        stale_council = types.ModuleType("chief_of_staff_council")
        fresh_council = types.ModuleType("chief_of_staff_council")
        stale_council.analyze_with_council = lambda message: {"flowMode": "full", "classification": "create_task"}
        fresh_council.analyze_with_council = lambda message: {"flowMode": "direct", "classification": "direct_execute"}

        def fake_reload(module):
            if module.__name__ == "intake_guard":
                return fresh_intake
            if module.__name__ == "chief_of_staff_council":
                return fresh_council
            return module

        with mock.patch.dict(
            sys.modules,
            {"intake_guard": stale_intake, "chief_of_staff_council": stale_council},
            clear=False,
        ), mock.patch.object(bridge.importlib, "invalidate_caches"), mock.patch.object(
            bridge.importlib, "reload", side_effect=fake_reload
        ):
            result = bridge._analyze_chat_route("统一更新所有智能体提示词，新增浏览器 CLI 回退规则")

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["flowMode"], "direct")
        self.assertEqual(result["classification"], "direct_execute")

    def test_create_task_dispatches_to_chief_of_staff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            data_dir = temp_root / "data"
            deliverables_dir = temp_root / "deliverables"
            data_dir.mkdir(parents=True, exist_ok=True)
            deliverables_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "tasks_source.json").write_text("[]", encoding="utf-8")
            (data_dir / "live_status.json").write_text("{}", encoding="utf-8")
            (data_dir / "agent_config.json").write_text("{}", encoding="utf-8")

            with mock.patch.object(dashboard_server, "DATA", data_dir), mock.patch.object(
                dashboard_server, "DELIVERABLES_ROOT", deliverables_dir
            ), mock.patch.object(dashboard_server, "_check_gateway_alive", return_value=True), mock.patch.object(
                dashboard_server,
                "_run_delegate_agent",
                return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""),
            ), mock.patch.object(
                dashboard_server,
                "_run_maintenance_script",
                return_value=None,
            ):
                result = dashboard_server.handle_create_task(
                    "调研 MiniMax M2.7 模型能力、适用场景、优缺点与建议",
                    org="产品规划部",
                    official="产品规划负责人",
                )

                self.assertTrue(result["ok"])
                task_id = result["taskId"]

                deadline = time.time() + 2.0
                task = None
                while time.time() < deadline:
                    tasks = json.loads((data_dir / "tasks_source.json").read_text(encoding="utf-8"))
                    task = next((item for item in tasks if item.get("id") == task_id), None)
                    if task and ((task.get("_scheduler") or {}).get("lastDispatchStatus") == "success"):
                        break
                    time.sleep(0.05)

            self.assertIsNotNone(task)
            self.assertEqual(task["state"], "ChiefOfStaff")
            scheduler = task.get("_scheduler") or {}
            self.assertEqual(scheduler.get("lastDispatchAgent"), "chief_of_staff")
            self.assertEqual(scheduler.get("lastDispatchStatus"), "success")
            flow_log = task.get("flow_log") or []
            remarks = "\n".join(str(item.get("remark") or "") for item in flow_log)
            self.assertIn("已入队派发：ChiefOfStaff → chief_of_staff", remarks)
            self.assertIn("派发成功：chief_of_staff", remarks)

    def test_create_task_uses_flow_prefixes_for_new_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            data_dir = temp_root / "data"
            deliverables_dir = temp_root / "deliverables"
            data_dir.mkdir(parents=True, exist_ok=True)
            deliverables_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "tasks_source.json").write_text("[]", encoding="utf-8")
            (data_dir / "live_status.json").write_text("{}", encoding="utf-8")
            (data_dir / "agent_config.json").write_text("{}", encoding="utf-8")

            with mock.patch.object(dashboard_server, "DATA", data_dir), mock.patch.object(
                dashboard_server, "DELIVERABLES_ROOT", deliverables_dir
            ), mock.patch.object(dashboard_server, "_check_gateway_alive", return_value=True), mock.patch.object(
                dashboard_server,
                "_run_delegate_agent",
                return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""),
            ), mock.patch.object(
                dashboard_server,
                "_run_maintenance_script",
                return_value=None,
            ):
                with mock.patch.object(dashboard_server, "dispatch_for_state", return_value=None):
                    direct = dashboard_server.handle_create_task("查询明天宁波天气并回传结果", flow_mode="direct")
                    light = dashboard_server.handle_create_task("整理一版产品发布朋友圈文案", flow_mode="light")
                    full = dashboard_server.handle_create_task("调研多 Agent 框架并给出落地建议", flow_mode="full")

            self.assertTrue(direct["ok"])
            self.assertTrue(light["ok"])
            self.assertTrue(full["ok"])
            self.assertRegex(str(direct["taskId"]), r"^D-\d{8}-\d{3}$")
            self.assertRegex(str(light["taskId"]), r"^L-\d{8}-\d{3}$")
            self.assertRegex(str(full["taskId"]), r"^F-\d{8}-\d{3}$")

    def test_light_task_dispatches_to_explicit_specialist_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            data_dir = temp_root / "data"
            deliverables_dir = temp_root / "deliverables"
            data_dir.mkdir(parents=True, exist_ok=True)
            deliverables_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "tasks_source.json").write_text("[]", encoding="utf-8")
            (data_dir / "live_status.json").write_text("{}", encoding="utf-8")
            (data_dir / "agent_config.json").write_text("{}", encoding="utf-8")

            with mock.patch.object(dashboard_server, "DATA", data_dir), mock.patch.object(
                dashboard_server, "DELIVERABLES_ROOT", deliverables_dir
            ), mock.patch.object(dashboard_server, "_check_gateway_alive", return_value=True), mock.patch.object(
                dashboard_server,
                "_run_delegate_agent",
                return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""),
            ), mock.patch.object(
                dashboard_server,
                "_run_maintenance_script",
                return_value=None,
            ):
                result = dashboard_server.handle_create_task(
                    "整理一版产品发布朋友圈文案",
                    flow_mode="light",
                    target_dept="品牌内容部",
                    params={"dispatchAgent": "brand_content", "dispatchOrg": "品牌内容部"},
                )

                self.assertTrue(result["ok"])
                task_id = result["taskId"]

                deadline = time.time() + 2.0
                task = None
                while time.time() < deadline:
                    tasks = json.loads((data_dir / "tasks_source.json").read_text(encoding="utf-8"))
                    task = next((item for item in tasks if item.get("id") == task_id), None)
                    if task and ((task.get("_scheduler") or {}).get("lastDispatchStatus") == "success"):
                        break
                    time.sleep(0.05)

            self.assertIsNotNone(task)
            scheduler = task.get("_scheduler") or {}
            self.assertEqual(scheduler.get("lastDispatchAgent"), "brand_content")
            self.assertEqual(scheduler.get("lastDispatchStatus"), "success")

    def test_dispatch_thread_keeps_temp_data_root_after_patch_scope_exits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            data_dir = temp_root / "data"
            deliverables_dir = temp_root / "deliverables"
            data_dir.mkdir(parents=True, exist_ok=True)
            deliverables_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "tasks_source.json").write_text("[]", encoding="utf-8")
            (data_dir / "live_status.json").write_text("{}", encoding="utf-8")
            (data_dir / "agent_config.json").write_text("{}", encoding="utf-8")

            with mock.patch.object(dashboard_server, "DATA", data_dir), mock.patch.object(
                dashboard_server, "DELIVERABLES_ROOT", deliverables_dir
            ), mock.patch.object(dashboard_server, "_check_gateway_alive", return_value=True), mock.patch.object(
                dashboard_server,
                "_run_delegate_agent",
                return_value=SimpleNamespace(returncode=0, stdout="ok", stderr=""),
            ), mock.patch.object(
                dashboard_server,
                "_run_maintenance_script",
                return_value=None,
            ):
                result = dashboard_server.handle_create_task(
                    "整理一版产品发布朋友圈文案",
                    flow_mode="light",
                    target_dept="品牌内容部",
                    params={"dispatchAgent": "brand_content", "dispatchOrg": "品牌内容部"},
                )
                self.assertTrue(result["ok"])
                task_id = result["taskId"]

            deadline = time.time() + 2.0
            task = None
            while time.time() < deadline:
                tasks = json.loads((data_dir / "tasks_source.json").read_text(encoding="utf-8"))
                task = next((item for item in tasks if item.get("id") == task_id), None)
                if task and ((task.get("_scheduler") or {}).get("lastDispatchStatus") == "success"):
                    break
                time.sleep(0.05)

            self.assertIsNotNone(task)
            scheduler = task.get("_scheduler") or {}
            self.assertEqual(scheduler.get("lastDispatchAgent"), "brand_content")
            self.assertEqual(scheduler.get("lastDispatchStatus"), "success")


if __name__ == "__main__":
    unittest.main()
