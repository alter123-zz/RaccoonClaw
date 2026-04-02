"""Regression checks for scheduled task automation."""

from __future__ import annotations

import importlib
import json
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "dashboard"))
sys.path.insert(0, str(ROOT / "scripts"))


class ScheduledJobsRegressionTests(unittest.TestCase):
    def _load_server(self, home_dir: pathlib.Path):
        with mock.patch.dict("os.environ", {"OPENCLAW_HOME": str(home_dir)}, clear=False):
            for name in ("server", "cron_jobs"):
                sys.modules.pop(name, None)
            import server as srv  # type: ignore

            srv = importlib.reload(srv)
            srv._run_maintenance_script = lambda *args, **kwargs: None
            return srv

    def test_create_recurring_task_materializes_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "live_status.json").write_text("{}")
            (data_dir / "agent_config.json").write_text("{}")
            (data_dir / "tasks_source.json").write_text("[]")

            srv = self._load_server(root / ".openclaw")
            srv.DATA = data_dir
            srv.dispatch_for_state = lambda *args, **kwargs: None

            result = srv.handle_create_task(
                title="每日科技新闻总结与推送",
                org="总裁办",
                target_dept="工程研发部",
                priority="normal",
                flow_mode="light",
                params={
                    "userBrief": "抓取指定站点并生成摘要",
                    "taskKind": "recurring",
                    "scheduleMode": "daily",
                    "scheduleLabel": "定时任务 · 每日 09:00",
                    "scheduleTime": "09:00",
                },
            )

            tasks = json.loads((data_dir / "tasks_source.json").read_text())
            task = tasks[0]
            jobs_payload = json.loads(srv.CRON_JOBS_PATH.read_text())
            job = jobs_payload["jobs"][0]

            self.assertTrue(result["ok"])
            self.assertEqual(task["state"], "Assigned")
            self.assertEqual(task["org"], "调度器")
            self.assertEqual(task["sourceMeta"]["automationJobId"], f"task-{task['id']}")
            self.assertEqual(job["taskId"], task["id"])
            self.assertEqual(job["schedule"]["expr"], "0 9 * * *")

    def test_due_recurring_job_dispatches_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "live_status.json").write_text("{}")
            (data_dir / "agent_config.json").write_text("{}")
            (data_dir / "tasks_source.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "L-20260328-005",
                            "title": "每日科技新闻总结与推送",
                            "state": "Assigned",
                            "org": "调度器",
                            "now": "等待调度执行：定时任务 · 每日 09:00",
                            "block": "无",
                            "output": "定时任务 · 每日 09:00",
                            "targetDept": "工程研发部",
                            "updatedAt": "2026-03-28T00:00:00Z",
                            "flow_log": [{"at": "2026-03-28T00:00:00Z", "from": "需求方", "to": "总裁办", "remark": "发起"}],
                            "sourceMeta": {
                                "flowMode": "light",
                                "dispatchAgent": "engineering",
                                "dispatchOrg": "工程研发部",
                                "taskKind": "recurring",
                                "scheduleMode": "daily",
                                "scheduleTime": "09:00",
                                "scheduleLabel": "定时任务 · 每日 09:00",
                            },
                        }
                    ]
                )
            )

            srv = self._load_server(root / ".openclaw")
            srv.DATA = data_dir
            task = json.loads((data_dir / "tasks_source.json").read_text())[0]
            srv.upsert_job_for_task(task)
            jobs_payload = json.loads(srv.CRON_JOBS_PATH.read_text())
            jobs_payload["jobs"][0]["state"]["nextRunAtMs"] = int(time.time() * 1000) - 1000
            jobs_payload["jobs"][0]["state"]["running"] = False
            srv.CRON_JOBS_PATH.write_text(json.dumps(jobs_payload, ensure_ascii=False, indent=2))

            dispatched: list[tuple[str, str, str]] = []

            def fake_dispatch(task_id, task_obj, state, trigger=""):
                dispatched.append((task_id, state, trigger))

            srv.dispatch_for_state = fake_dispatch
            result = srv.handle_run_due_scheduled_jobs()
            tasks = json.loads((data_dir / "tasks_source.json").read_text())
            task = tasks[0]
            jobs_payload = json.loads(srv.CRON_JOBS_PATH.read_text())

            self.assertTrue(result["ok"])
            self.assertEqual(result["count"], 1)
            self.assertEqual(dispatched, [("L-20260328-005", "Doing", "cron-due")])
            self.assertEqual(task["state"], "Doing")
            self.assertEqual(task["org"], "工程研发部")
            self.assertIn("调度触发执行", task["now"])
            self.assertEqual(jobs_payload["jobs"][0]["state"]["lastRunStatus"], "queued")

    def test_recurring_done_task_returns_to_waiting_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "live_status.json").write_text("{}")
            (data_dir / "agent_config.json").write_text("{}")
            (data_dir / "tasks_source.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "L-20260328-005",
                            "title": "每日科技新闻总结与推送",
                            "state": "Done",
                            "org": "完成",
                            "now": "✅ 已完成",
                            "block": "",
                            "output": "/tmp/out.md",
                            "updatedAt": "2026-03-29T10:05:00Z",
                            "flow_log": [{"at": "2026-03-29T10:00:00Z", "from": "需求方", "to": "总裁办", "remark": "发起"}],
                            "sourceMeta": {
                                "flowMode": "light",
                                "dispatchAgent": "engineering",
                                "taskKind": "recurring",
                                "scheduleMode": "daily",
                                "scheduleTime": "09:00",
                                "scheduleLabel": "定时任务 · 每日 09:00",
                            },
                        }
                    ]
                )
            )

            srv = self._load_server(root / ".openclaw")
            srv.DATA = data_dir
            srv.handle_run_due_scheduled_jobs()
            tasks = json.loads((data_dir / "tasks_source.json").read_text())
            task = tasks[0]

            self.assertEqual(task["state"], "Assigned")
            self.assertEqual(task["org"], "调度器")
            self.assertEqual(task["now"], "等待调度执行：定时任务 · 每日 09:00")

    def test_cancelled_recurring_task_stays_cancelled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "live_status.json").write_text("{}")
            (data_dir / "agent_config.json").write_text("{}")
            (data_dir / "tasks_source.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "L-20260328-005",
                            "title": "每日科技新闻总结与推送",
                            "state": "Assigned",
                            "org": "调度器",
                            "now": "等待调度执行：定时任务 · 每日 09:00",
                            "block": "无",
                            "output": "定时任务 · 每日 09:00",
                            "updatedAt": "2026-03-28T00:00:00Z",
                            "flow_log": [{"at": "2026-03-28T00:00:00Z", "from": "需求方", "to": "总裁办", "remark": "发起"}],
                            "sourceMeta": {
                                "flowMode": "light",
                                "dispatchAgent": "engineering",
                                "dispatchOrg": "工程研发部",
                                "taskKind": "recurring",
                                "scheduleMode": "daily",
                                "scheduleTime": "09:00",
                                "scheduleLabel": "定时任务 · 每日 09:00",
                            },
                        }
                    ]
                )
            )

            srv = self._load_server(root / ".openclaw")
            srv.DATA = data_dir
            srv.dispatch_for_state = lambda *args, **kwargs: None

            task = json.loads((data_dir / "tasks_source.json").read_text())[0]
            job_id = srv.upsert_job_for_task(task)
            cancel_result = srv.handle_task_action("L-20260328-005", "cancel", "不再需要")
            reconcile_result = srv.handle_run_due_scheduled_jobs()

            tasks = json.loads((data_dir / "tasks_source.json").read_text())
            task = tasks[0]
            jobs_payload = json.loads(srv.CRON_JOBS_PATH.read_text())
            job = next(item for item in jobs_payload["jobs"] if item["id"] == job_id)

            self.assertTrue(cancel_result["ok"])
            self.assertTrue(reconcile_result["ok"])
            self.assertEqual(task["state"], "Cancelled")
            self.assertEqual(task["org"], "调度器")
            self.assertFalse(job["enabled"])
            self.assertIsNone(job["state"]["nextRunAtMs"])
            self.assertFalse(task["sourceMeta"]["jobEnabled"])


if __name__ == "__main__":
    unittest.main()
