"""Regression checks for community runtime seed script."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import seed_runtime_data as seed  # type: ignore


class SeedRuntimeDataTests(unittest.TestCase):
    def test_clean_profile_creates_local_runtime_and_empty_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = pathlib.Path(tmp) / "repo"
            openclaw_home = repo_dir / ".openclaw"
            repo_dir.mkdir(parents=True, exist_ok=True)

            seed.seed_profile(openclaw_home, repo_dir / "data", "clean", force=True)

            self.assertTrue((openclaw_home / "openclaw.json").exists())
            self.assertTrue((repo_dir / "data" / "tasks_source.json").exists())
            self.assertTrue((openclaw_home / "workspace-chief_of_staff" / "data" / "tasks_source.json").exists())

            jobs_payload = json.loads((openclaw_home / "cron" / "jobs.json").read_text(encoding="utf-8"))
            self.assertEqual(jobs_payload["jobs"], [])

    def test_demo_profile_seeds_deliverable_and_recurring_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_dir = pathlib.Path(tmp) / "repo"
            openclaw_home = repo_dir / ".openclaw"
            repo_dir.mkdir(parents=True, exist_ok=True)

            seed.seed_profile(openclaw_home, repo_dir / "data", "demo", force=True)

            tasks = json.loads((repo_dir / "data" / "tasks_source.json").read_text(encoding="utf-8"))
            self.assertEqual(len(tasks), 2)
            self.assertEqual(tasks[0]["id"], "L-20260101-001")
            self.assertEqual(tasks[1]["sourceMeta"]["taskKind"], "recurring")

            deliverable_path = pathlib.Path(tasks[0]["output"])
            self.assertTrue(deliverable_path.exists())

            jobs_payload = json.loads((openclaw_home / "cron" / "jobs.json").read_text(encoding="utf-8"))
            self.assertEqual(len(jobs_payload["jobs"]), 1)
            job = jobs_payload["jobs"][0]
            self.assertEqual(job["taskId"], "L-20260101-002")
            self.assertEqual(job["schedule"]["kind"], "recurring")


if __name__ == "__main__":
    unittest.main()
