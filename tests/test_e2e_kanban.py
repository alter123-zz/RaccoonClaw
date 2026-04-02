#!/usr/bin/env python3
"""隔离回归测试 edict kanban 更新脚本的清洗与 API 流转。"""

from __future__ import annotations

import pathlib
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Raccoon" / "scripts"))

import kanban_update_edict as kb  # type: ignore


class KanbanE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.tasks: dict[str, dict] = {}
        self.progress_updates: dict[str, list[str]] = {}
        self.transition_updates: dict[str, list[dict]] = {}
        self.todo_updates: dict[str, list[dict]] = {}

        self.check_api_patcher = mock.patch.object(kb, "_check_api", return_value=True)
        self.api_post_patcher = mock.patch.object(kb, "_api_post", side_effect=self._fake_api_post)
        self.api_put_patcher = mock.patch.object(kb, "_api_put", side_effect=self._fake_api_put)
        self.agent_patcher = mock.patch.object(kb, "_infer_agent_id", return_value="planning")

        self.check_api_patcher.start()
        self.api_post_patcher.start()
        self.api_put_patcher.start()
        self.agent_patcher.start()

    def tearDown(self) -> None:
        self.agent_patcher.stop()
        self.api_put_patcher.stop()
        self.api_post_patcher.stop()
        self.check_api_patcher.stop()

    def _legacy_id_from_path(self, path: str) -> str:
        prefix = "/api/tasks/by-legacy/"
        remainder = path[len(prefix) :]
        return remainder.split("/", 1)[0]

    def _fake_api_post(self, path: str, data: dict) -> dict:
        if path == "/api/tasks":
            legacy_id = str((data.get("tags") or [""])[0])
            self.tasks[legacy_id] = {
                "title": data.get("title"),
                "description": data.get("description"),
                "priority": data.get("priority"),
                "assignee_org": data.get("assignee_org"),
                "creator": data.get("creator"),
                "meta": data.get("meta") or {},
            }
            return {"task_id": f"task-{legacy_id}"}

        legacy_id = self._legacy_id_from_path(path)
        if path.endswith("/transition"):
            self.transition_updates.setdefault(legacy_id, []).append(data)
            return {"ok": True}
        if path.endswith("/progress"):
            self.progress_updates.setdefault(legacy_id, []).append(str(data.get("content") or ""))
            return {"ok": True}
        raise AssertionError(f"unexpected POST path: {path}")

    def _fake_api_put(self, path: str, data: dict) -> dict:
        legacy_id = self._legacy_id_from_path(path)
        if path.endswith("/todos"):
            self.todo_updates[legacy_id] = list(data.get("todos") or [])
            return {"ok": True}
        raise AssertionError(f"unexpected PUT path: {path}")

    def test_dirty_title_cleaned_before_create(self) -> None:
        kb.cmd_create(
            "JJC-TEST-E2E-01",
            "全面审查/Users/example/clawd/RaccoonClaw-OSS/这个项目\nConversation info (xxx)",
            "Planning",
            "产品规划部",
            "产品规划负责人",
            "总裁办整理需求",
        )

        task = self.tasks["JJC-TEST-E2E-01"]
        self.assertNotIn("/Users", task["title"])
        self.assertNotIn("Conversation", task["title"])
        self.assertEqual(task["assignee_org"], "产品规划部")

    def test_pure_path_rejected(self) -> None:
        kb.cmd_create(
            "JJC-TEST-E2E-02",
            "/Users/example/clawd/RaccoonClaw-OSS/",
            "Planning",
            "产品规划部",
            "产品规划负责人",
        )

        self.assertNotIn("JJC-TEST-E2E-02", self.tasks)

    def test_short_title_rejected(self) -> None:
        kb.cmd_create("JJC-TEST-E2E-03", "好的", "Planning", "产品规划部", "产品规划负责人")
        self.assertNotIn("JJC-TEST-E2E-03", self.tasks)

    def test_prefix_stripped(self) -> None:
        kb.cmd_create(
            "JJC-TEST-E2E-04",
            "传旨：帮我写技术博客文章关于智能体架构",
            "Planning",
            "产品规划部",
            "产品规划负责人",
        )

        self.assertEqual(self.tasks["JJC-TEST-E2E-04"]["title"], "帮我写技术博客文章关于智能体架构")

    def test_flow_remark_cleaned(self) -> None:
        kb.cmd_flow(
            "JJC-TEST-E2E-05",
            "总裁办",
            "产品规划部",
            "需求传达：审查/Users/example/clawd/xxx项目 Conversation blah",
        )

        updates = self.progress_updates["JJC-TEST-E2E-05"]
        self.assertEqual(len(updates), 1)
        self.assertNotIn("/Users", updates[0])
        self.assertNotIn("Conversation", updates[0])
        self.assertIn("总裁办", updates[0])
        self.assertIn("产品规划部", updates[0])

    def test_state_update_posts_transition(self) -> None:
        kb.cmd_state("JJC-TEST-E2E-06", "ReviewControl", "方案提交评审质控部审议")

        transition = self.transition_updates["JJC-TEST-E2E-06"][0]
        self.assertEqual(transition["new_state"], "review_control")
        self.assertEqual(transition["agent"], "planning")
        self.assertEqual(transition["reason"], "方案提交评审质控部审议")

    def test_done_posts_done_transition(self) -> None:
        kb.cmd_done("JJC-TEST-E2E-07", "/tmp/output.md", "任务已完成")

        transition = self.transition_updates["JJC-TEST-E2E-07"][0]
        self.assertEqual(transition["new_state"], "done")
        self.assertEqual(transition["reason"], "任务已完成")

    def test_progress_sanitizes_text_and_updates_todos(self) -> None:
        kb.cmd_progress(
            "JJC-TEST-E2E-08",
            "已完成第一轮排查 /Users/example/trace.log Conversation detail",
            "梳理问题✅|复现实验🔄|补充报告",
        )

        progress = self.progress_updates["JJC-TEST-E2E-08"][0]
        todos = self.todo_updates["JJC-TEST-E2E-08"]
        self.assertNotIn("/Users", progress)
        self.assertNotIn("Conversation", progress)
        self.assertEqual(
            todos,
            [
                {"id": "1", "title": "梳理问题", "status": "completed"},
                {"id": "2", "title": "复现实验", "status": "in-progress"},
                {"id": "3", "title": "补充报告", "status": "not-started"},
            ],
        )

    def test_todo_invalid_status_falls_back_to_not_started(self) -> None:
        kb.cmd_todo("JJC-TEST-E2E-09", "2", "补充复盘", "unknown")

        progress = self.progress_updates["JJC-TEST-E2E-09"][0]
        self.assertEqual(progress, "Todo #2: 补充复盘 → not-started")


if __name__ == "__main__":
    unittest.main(verbosity=2)
