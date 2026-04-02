"""Regression checks for browser CLI fallback and obsolete skill cleanup."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import blocker_utils  # type: ignore
import sync_agent_config  # type: ignore


class BrowserCliRegressionTests(unittest.TestCase):
    def test_agent_skill_listing_hides_obsolete_zhipu_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = pathlib.Path(tmp)
            skills_dir = workspace / "skills"
            (skills_dir / "zhipu-web-search").mkdir(parents=True)
            (skills_dir / "zhipu-web-search" / "SKILL.md").write_text("# obsolete", encoding="utf-8")
            (skills_dir / "browser-cli-helper").mkdir(parents=True)
            (skills_dir / "browser-cli-helper" / "SKILL.md").write_text("# current", encoding="utf-8")

            skills = sync_agent_config.get_skills(str(workspace))
            names = {item["name"] for item in skills}

            self.assertNotIn("zhipu-web-search", names)
            self.assertIn("browser-cli-helper", names)

    def test_obsolete_skill_cleanup_removes_zhipu_search_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws_skills = pathlib.Path(tmp) / "skills"
            obsolete = ws_skills / "zhipu-web-search"
            obsolete.mkdir(parents=True)
            (obsolete / "SKILL.md").write_text("obsolete", encoding="utf-8")

            removed = sync_agent_config._cleanup_builtin_skill_copies(ws_skills, [])

            self.assertEqual(removed, 1)
            self.assertFalse(obsolete.exists())

    def test_blocker_feedback_prefers_browser_cli_for_search_failures(self) -> None:
        report = blocker_utils.detect_blocker_report(
            [
                "auth_error ZHIPU_API_KEY not set or still placeholder",
                "DuckDuckGo returned a bot-detection challenge.",
            ]
        )

        self.assertIsNotNone(report)
        assert report is not None
        self.assertEqual(report["kind"], "search")
        self.assertFalse(report["awaitingUserAction"])
        actions = "\n".join(report["actions"])
        self.assertIn("browser_cli.py search", actions)

    def test_browser_cli_script_is_synced_to_workspaces(self) -> None:
        self.assertIn("browser_cli.py", sync_agent_config._WORKSPACE_RUNTIME_SCRIPTS)
        self.assertTrue((ROOT / "scripts" / "browser_cli.py").exists())


if __name__ == "__main__":
    unittest.main()
