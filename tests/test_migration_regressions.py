"""Regression checks for legacy task ids and deliverable migration compatibility."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_live_data as refresh  # type: ignore
import task_store_repair as repair  # type: ignore


class MigrationRegressionTests(unittest.TestCase):
    def test_repair_migrates_legacy_jjc_output_to_canonical_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            openclaw_home = temp_root / ".openclaw"
            workspace = openclaw_home / "workspace-chief_of_staff"
            data_dir = workspace / "data"
            legacy_root = workspace / "deliverables"
            canonical_root = data_dir / "deliverables"
            task_id = "JJC-20260327-019"

            legacy_task_dir = legacy_root / task_id
            legacy_task_dir.mkdir(parents=True, exist_ok=True)
            source_file = legacy_task_dir / f"{task_id}_旧报告.md"
            source_file.write_text("历史交付物", encoding="utf-8")

            tasks_file = data_dir / "tasks_source.json"
            report_file = data_dir / "task_store_repair_report.json"
            data_dir.mkdir(parents=True, exist_ok=True)
            tasks_file.write_text(
                json.dumps(
                    [
                        {
                            "id": task_id,
                            "title": "历史旧前缀任务",
                            "state": "Done",
                            "org": "完成",
                            "now": "收到专项团队执行结果，正在整理摘要并回传总裁办",
                            "output": str(source_file),
                            "todos": [
                                {"id": "1", "title": "回传总裁办", "status": "in-progress"},
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            def canonical_task_dir(_: str) -> pathlib.Path:
                target = canonical_root / task_id
                target.mkdir(parents=True, exist_ok=True)
                return target

            with mock.patch.object(repair, "TASKS_FILE", tasks_file), mock.patch.object(
                repair, "REPORT_FILE", report_file
            ), mock.patch.object(
                repair, "OCLAW_HOME", openclaw_home
            ), mock.patch.object(
                repair, "candidate_deliverables_roots", return_value=[canonical_root, legacy_root]
            ), mock.patch.object(
                repair, "canonical_task_deliverables_dir", side_effect=canonical_task_dir
            ):
                stats = repair.repair_task_store()

            payload = json.loads(tasks_file.read_text(encoding="utf-8"))[0]
            migrated_output = pathlib.Path(payload["output"])
            self.assertEqual(stats["changed"], 1)
            self.assertTrue(migrated_output.exists())
            self.assertIn(str(canonical_root / task_id), str(migrated_output))
            self.assertEqual(payload["now"], "已完成：回传总裁办")

    def test_discover_task_artifacts_prefers_canonical_for_legacy_jjc_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            openclaw_home = temp_root / ".openclaw"
            workspace = openclaw_home / "workspace-chief_of_staff"
            canonical_root = workspace / "data" / "deliverables"
            legacy_root = workspace / "deliverables"
            task_id = "JJC-20260327-019"

            legacy_task_dir = legacy_root / task_id
            canonical_task_dir = canonical_root / task_id
            legacy_task_dir.mkdir(parents=True, exist_ok=True)
            canonical_task_dir.mkdir(parents=True, exist_ok=True)

            legacy = legacy_task_dir / f"{task_id}_legacy.md"
            canonical = canonical_task_dir / f"{task_id}_canonical.md"
            legacy.write_text("legacy", encoding="utf-8")
            canonical.write_text("canonical", encoding="utf-8")

            with mock.patch.object(refresh, "OCLAW_HOME", openclaw_home), mock.patch.object(
                refresh, "CANONICAL_DELIVERABLES_ROOT", canonical_root
            ):
                artifacts = refresh.discover_task_artifacts()

        self.assertIn(task_id, artifacts)
        self.assertGreaterEqual(len(artifacts[task_id]), 2)
        self.assertEqual(pathlib.Path(artifacts[task_id][0]["path"]).name, canonical.name)
        self.assertTrue(artifacts[task_id][0]["isCanonical"])


if __name__ == "__main__":
    unittest.main()
