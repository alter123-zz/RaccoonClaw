"""Regression checks for task_store_repair and deliverable path contract."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import runtime_paths  # type: ignore
import task_store_repair as repair  # type: ignore


class TaskStoreRepairTests(unittest.TestCase):
    def test_canonical_deliverables_root_uses_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            with mock.patch.object(runtime_paths, "canonical_data_dir", return_value=data_dir):
                root = runtime_paths.canonical_deliverables_root()

        self.assertEqual(root, data_dir / "deliverables")

    def test_repair_migrates_legacy_output_and_closes_callback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            openclaw_home = temp_root / ".openclaw"
            workspace = openclaw_home / "workspace-chief_of_staff"
            data_dir = workspace / "data"
            canonical_root = data_dir / "deliverables"
            legacy_root = workspace / "deliverables"
            task_id = "F-1"

            legacy_task_dir = legacy_root / task_id
            legacy_task_dir.mkdir(parents=True, exist_ok=True)
            source_file = legacy_task_dir / "report.md"
            source_file.write_text("# 报告\n\n真实内容。", encoding="utf-8")

            tasks_file = data_dir / "tasks_source.json"
            report_file = data_dir / "task_store_repair_report.json"
            data_dir.mkdir(parents=True, exist_ok=True)
            tasks_file.write_text(
                json.dumps(
                    [
                        {
                            "id": task_id,
                            "title": "历史 full 任务",
                            "state": "Done",
                            "org": "完成",
                            "now": "收到专项团队执行结果，正在整理摘要并回传总裁办",
                            "output": str(source_file),
                            "todos": [
                                {"id": "1", "title": "交付执行", "status": "completed"},
                                {"id": "2", "title": "回传总裁办", "status": "in-progress"},
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
            self.assertEqual(migrated_output.read_text(encoding="utf-8"), source_file.read_text(encoding="utf-8"))
            self.assertIn(str(canonical_root / task_id), str(migrated_output))
            self.assertEqual(payload["now"], "已完成：回传总裁办")
            self.assertEqual(payload["todos"][-1]["status"], "completed")
            self.assertIn(task_id, stats["changedTaskIds"])
            self.assertIn(task_id, stats["migratedTaskIds"])

    def test_repair_downgrades_done_task_without_real_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            openclaw_home = temp_root / ".openclaw"
            workspace = openclaw_home / "workspace-chief_of_staff"
            data_dir = workspace / "data"
            canonical_root = data_dir / "deliverables"
            legacy_root = workspace / "deliverables"
            task_id = "F-2"

            tasks_file = data_dir / "tasks_source.json"
            report_file = data_dir / "task_store_repair_report.json"
            data_dir.mkdir(parents=True, exist_ok=True)
            tasks_file.write_text(
                json.dumps(
                    [
                        {
                            "id": task_id,
                            "title": "坏归档任务",
                            "state": "Done",
                            "org": "完成",
                            "now": "收到专项团队执行结果，正在整理摘要并回传总裁办",
                            "output": str(legacy_root / task_id / "missing.md"),
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

        self.assertEqual(stats["blockedTasks"], 1)
        self.assertEqual(payload["state"], "Blocked")
        self.assertEqual(payload["org"], "总裁办")
        self.assertEqual(payload["block"], repair.MISSING_OUTPUT_SUMMARY)
        self.assertEqual(payload["now"], repair.MISSING_OUTPUT_SUMMARY)

    def test_repair_writes_report_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = pathlib.Path(tmp)
            openclaw_home = temp_root / ".openclaw"
            workspace = openclaw_home / "workspace-chief_of_staff"
            data_dir = workspace / "data"
            canonical_root = data_dir / "deliverables"
            legacy_root = workspace / "deliverables"
            report_file = data_dir / "task_store_repair_report.json"
            task_id = "F-3"

            legacy_task_dir = legacy_root / task_id
            legacy_task_dir.mkdir(parents=True, exist_ok=True)
            source_file = legacy_task_dir / "report.md"
            source_file.write_text("# 历史报告", encoding="utf-8")

            tasks_file = data_dir / "tasks_source.json"
            data_dir.mkdir(parents=True, exist_ok=True)
            tasks_file.write_text(
                json.dumps(
                    [{"id": task_id, "state": "Done", "org": "完成", "output": str(source_file), "todos": [{"id": "1", "title": "回传总裁办", "status": "in-progress"}]}],
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
                repair.repair_task_store()

            report = json.loads(report_file.read_text(encoding="utf-8"))

        self.assertEqual(report["changed"], 1)
        self.assertIn(task_id, report["changedTaskIds"])


if __name__ == "__main__":
    unittest.main()
