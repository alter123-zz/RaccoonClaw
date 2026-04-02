"""Tests for the mechanical helpers in scripts/chief_of_staff_council.py
and backward-compatible deprecated stubs.
"""

from __future__ import annotations

import pathlib
import re
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import chief_of_staff_council as council  # type: ignore
import intake_guard  # type: ignore


class GenIdTests(unittest.TestCase):
    """Test the gen-id subcommand."""

    def _fake_empty_tasks(self, name, default):
        if name == "tasks_source.json":
            return []
        return default

    def test_gen_id_full_returns_f_prefix(self) -> None:
        with mock.patch.object(council, "read_preferred_json", side_effect=self._fake_empty_tasks):
            result = council._gen_task_id("full")
        self.assertTrue(result["ok"])
        self.assertRegex(result["taskId"], r"^F-\d{8}-001$")

    def test_gen_id_light_returns_l_prefix(self) -> None:
        with mock.patch.object(council, "read_preferred_json", side_effect=self._fake_empty_tasks):
            result = council._gen_task_id("light")
        self.assertTrue(result["ok"])
        self.assertRegex(result["taskId"], r"^L-\d{8}-001$")

    def test_gen_id_direct_returns_d_prefix(self) -> None:
        with mock.patch.object(council, "read_preferred_json", side_effect=self._fake_empty_tasks):
            result = council._gen_task_id("direct")
        self.assertTrue(result["ok"])
        self.assertRegex(result["taskId"], r"^D-\d{8}-001$")

    def test_gen_id_sequential(self) -> None:
        fake_tasks = [{"id": "F-20260401-003", "state": "Done"}]
        def fake_read(name, default):
            if name == "tasks_source.json":
                return fake_tasks
            return default

        with mock.patch.object(council, "read_preferred_json", side_effect=fake_read):
            result = council._gen_task_id("full")
        self.assertTrue(result["ok"])
        self.assertTrue(result["taskId"].startswith("F-"), f"Expected F-prefix, got {result['taskId']}")

    def test_gen_id_flow_mode_echoed(self) -> None:
        with mock.patch.object(council, "read_preferred_json", side_effect=self._fake_empty_tasks):
            result = council._gen_task_id("light")
        self.assertEqual(result["flowMode"], "light")


class TitleHintTests(unittest.TestCase):
    """Test the title-hint subcommand."""

    def test_basic_title_hint(self) -> None:
        result = council._cmd_title_hint("帮我写一篇关于AI的文章")
        self.assertTrue(result["ok"])
        self.assertTrue(len(result["titleHint"]) > 0)

    def test_framework_comparison(self) -> None:
        result = council._cmd_title_hint("对比 React 和 Vue 的优劣")
        self.assertIn("对比", result["titleHint"])

    def test_multi_agent_framework(self) -> None:
        result = council._cmd_title_hint("分析 CrewAI、AutoGen、LangGraph 多 Agent 框架")
        self.assertIn("CrewAI", result["titleHint"])


class CheckInstallTests(unittest.TestCase):
    """Test the check-install subcommand."""

    def test_no_duplicate_when_no_tasks(self) -> None:
        def fake_read(name, default):
            if name == "tasks_source.json":
                return []
            return default

        with mock.patch.object(council, "read_preferred_json", side_effect=fake_read):
            result = council._cmd_check_install("安装 keyoku-ai 项目")
        self.assertTrue(result["ok"])
        self.assertFalse(result["duplicate"])

    def test_no_duplicate_for_non_install_message(self) -> None:
        result = council._cmd_check_install("帮我写一篇文章")
        self.assertTrue(result["ok"])
        self.assertFalse(result["duplicate"])

    def test_detects_duplicate_install(self) -> None:
        fake_tasks = [
            {
                "id": "F-20260321-003",
                "state": "Done",
                "title": "安装 keyoku-ai/keyoku 项目",
                "output": "/tmp/keyoku",
                "detail": "https://github.com/keyoku-ai/keyoku",
            }
        ]

        def fake_read(name, default):
            if name == "tasks_source.json":
                return fake_tasks
            return default

        with mock.patch.object(council, "read_preferred_json", side_effect=fake_read):
            result = council._cmd_check_install("安装下这个 https://github.com/keyoku-ai/keyoku")
        self.assertTrue(result["ok"])
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["match"]["taskId"], "F-20260321-003")


class DeprecatedStubsTests(unittest.TestCase):
    """Test that deprecated stubs return valid payloads."""

    def test_analyze_with_council_returns_empty_classification(self) -> None:
        result = council.analyze_with_council("测试消息")
        # Empty classification makes dashboard fall through to agent
        self.assertEqual(result["classification"], "")
        self.assertFalse(result["shouldCreateTask"])
        self.assertIn("council", result)

    def test_analyze_with_council_has_required_fields(self) -> None:
        result = council.analyze_with_council("任意消息")
        required_fields = [
            "classification", "shouldCreateTask", "flowMode",
            "dispatchAgent", "dispatchOrg", "skipPlanning", "skipReview",
        ]
        for field in required_fields:
            self.assertIn(field, result, f"Missing field: {field}")

    def test_analyze_with_council_stub_flow_mode_is_empty(self) -> None:
        result = council.analyze_with_council("任何内容")
        # Empty flowMode so dashboard won't intercept
        self.assertEqual(result["flowMode"], "")

    def test_intake_guard_analyze_message_returns_valid(self) -> None:
        result = intake_guard.analyze_message("你好")
        # classification may be empty (semantic done by deputy agent), but fields must be present
        self.assertIn("semanticProfile", result)
        self.assertFalse(result["shouldCreateTask"])


class ImportChainTests(unittest.TestCase):
    """Verify the import chain still works."""

    def test_council_importable(self) -> None:
        import chief_of_staff_council
        self.assertTrue(hasattr(chief_of_staff_council, "analyze_with_council"))
        self.assertTrue(hasattr(chief_of_staff_council, "_gen_task_id"))
        self.assertTrue(hasattr(chief_of_staff_council, "_title_hint"))

    def test_intake_guard_importable(self) -> None:
        import intake_guard
        self.assertTrue(hasattr(intake_guard, "analyze_message"))
        self.assertTrue(hasattr(intake_guard, "_title_hint"))
        self.assertTrue(hasattr(intake_guard, "_next_task_id"))

    def test_council_imports_analyze_message(self) -> None:
        """council.py re-exports analyze_message from intake_guard."""
        self.assertTrue(hasattr(council, "analyze_message"))


class OrgMappingTests(unittest.TestCase):
    """Test the agent-to-org mapping."""

    def test_known_agents(self) -> None:
        self.assertEqual(council._org_for_agent("engineering"), "工程研发部")
        self.assertEqual(council._org_for_agent("planning"), "产品规划部")
        self.assertEqual(council._org_for_agent("brand_content"), "品牌内容部")
        self.assertEqual(council._org_for_agent("chief_of_staff"), "总裁办")

    def test_unknown_agent_returns_empty(self) -> None:
        self.assertEqual(council._org_for_agent("nonexistent"), "")


if __name__ == "__main__":
    unittest.main()
