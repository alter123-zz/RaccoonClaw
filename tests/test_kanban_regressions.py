"""Regression checks for scripts/kanban_update.py."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kanban_update as kb  # type: ignore


class KanbanRegressionTests(unittest.TestCase):
    def test_full_flow_task_cannot_enter_done_before_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_file = pathlib.Path(tmp) / "tasks_source.json"
            tasks_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "T-3",
                            "title": "full flow test",
                            "state": "Assigned",
                            "org": "交付运营部",
                            "sourceMeta": {
                                "flowMode": "full",
                                "requiredStages": ["planning", "review", "dispatch", "execution"],
                            },
                            "todos": [
                                {"id": "1", "title": "分析需求", "status": "completed"},
                                {"id": "2", "title": "起草方案", "status": "completed"},
                                {"id": "3", "title": "评审质控", "status": "completed"},
                                {"id": "4", "title": "交付执行", "status": "completed"},
                                {"id": "5", "title": "回传总裁办", "status": "in-progress"},
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            original = kb.TASKS_FILE
            kb.TASKS_FILE = tasks_file
            try:
                result = kb.cmd_state("T-3", "Done", "执行完成")
                tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
            finally:
                kb.TASKS_FILE = original

        self.assertEqual(result, 2)
        self.assertEqual(tasks[0]["state"], "Assigned")
        self.assertEqual(tasks[0]["todos"][-1]["status"], "in-progress")

    def test_full_flow_task_can_enter_done_after_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_file = pathlib.Path(tmp) / "tasks_source.json"
            tasks_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "T-4",
                            "title": "full flow done test",
                            "state": "Assigned",
                            "org": "交付运营部",
                            "sourceMeta": {
                                "flowMode": "full",
                                "requiredStages": ["planning", "review", "dispatch", "execution"],
                            },
                            "todos": [
                                {"id": "1", "title": "分析需求", "status": "completed"},
                                {"id": "2", "title": "起草方案", "status": "completed"},
                                {"id": "3", "title": "评审质控", "status": "completed"},
                                {"id": "4", "title": "交付执行", "status": "completed"},
                                {"id": "5", "title": "回传总裁办", "status": "completed"},
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            original = kb.TASKS_FILE
            kb.TASKS_FILE = tasks_file
            try:
                result = kb.cmd_state("T-4", "Done", "执行完成")
                tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
            finally:
                kb.TASKS_FILE = original

        self.assertEqual(result, 0)
        self.assertEqual(tasks[0]["state"], "Done")
        self.assertEqual(tasks[0]["org"], "完成")

    def test_done_prefers_single_referenced_deliverable_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            workspace = temp_root / "workspace-delivery_ops"
            deliverables_dir = workspace / "deliverables"
            archive_dir = temp_root / "archive" / "F-1"
            deliverables_dir.mkdir(parents=True, exist_ok=True)
            archive_dir.mkdir(parents=True, exist_ok=True)

            actual_file = deliverables_dir / "F-1-真实产出.md"
            actual_file.write_text("# 真正产出\n\n这是一页摘要。", encoding="utf-8")

            tasks_file = temp_root / "tasks_source.json"
            tasks_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "F-1",
                            "title": "full flow output test",
                            "state": "Doing",
                            "org": "执行中",
                            "todos": [{"id": "1", "title": "回传总裁办", "status": "completed"}],
                            "sourceMeta": {"flowMode": "full"},
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            original_tasks_file = kb.TASKS_FILE
            kb.TASKS_FILE = tasks_file
            try:
                with mock.patch.object(kb, "canonical_task_deliverables_dir", return_value=archive_dir):
                    current_cwd = pathlib.Path.cwd()
                    try:
                        os.chdir(workspace)
                        result = kb.cmd_done(
                            "F-1",
                            "真正交付物已完成，详见 deliverables/F-1-真实产出.md",
                            "真实交付已完成",
                        )
                    finally:
                        os.chdir(current_cwd)
                tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
            finally:
                kb.TASKS_FILE = original_tasks_file

            self.assertEqual(result, 0)
            archived_output = pathlib.Path(tasks[0]["output"])
            self.assertEqual(archived_output.name, "F-1-真实产出.md")
            self.assertEqual(archived_output.read_text(encoding="utf-8"), actual_file.read_text(encoding="utf-8"))

    def test_progress_cannot_regress_done_callback_todo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_file = pathlib.Path(tmp) / "tasks_source.json"
            tasks_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "F-2",
                            "title": "done task",
                            "state": "Done",
                            "org": "完成",
                            "now": "已完成：回传总裁办",
                            "todos": [
                                {"id": "1", "title": "交付执行", "status": "completed"},
                                {"id": "2", "title": "回传总裁办", "status": "completed"},
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            original = kb.TASKS_FILE
            kb.TASKS_FILE = tasks_file
            try:
                result = kb.cmd_progress("F-2", "收到专项团队执行结果，正在整理摘要并回传总裁办", "交付执行✅|回传总裁办🔄")
                tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
            finally:
                kb.TASKS_FILE = original

        self.assertEqual(result, 0)
        self.assertEqual(tasks[0]["now"], "已完成：回传总裁办")
        self.assertEqual(tasks[0]["todos"][-1]["status"], "completed")

    def test_todo_cannot_regress_done_callback_todo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tasks_file = pathlib.Path(tmp) / "tasks_source.json"
            tasks_file.write_text(
                json.dumps(
                    [
                        {
                            "id": "F-3",
                            "title": "done task",
                            "state": "Done",
                            "org": "完成",
                            "now": "已完成：回传总裁办",
                            "todos": [
                                {"id": "5", "title": "回传总裁办", "status": "completed", "detail": "旧详情"},
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            original = kb.TASKS_FILE
            kb.TASKS_FILE = tasks_file
            try:
                result = kb.cmd_todo("F-3", "5", "回传总裁办", "in-progress")
                tasks = json.loads(tasks_file.read_text(encoding="utf-8"))
            finally:
                kb.TASKS_FILE = original

        self.assertEqual(result, 0)
        self.assertEqual(tasks[0]["todos"][0]["status"], "completed")
        self.assertEqual(tasks[0]["todos"][0]["detail"], "旧详情")


if __name__ == "__main__":
    unittest.main()
