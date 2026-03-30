"""Regression checks for chat attachment upload/remove lifecycle."""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "edict" / "backend"))

from app.services import legacy_server_bridge as bridge  # type: ignore


class ChatAttachmentRegressionTests(unittest.TestCase):
    def test_upload_and_remove_attachment_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "chat_sessions.json").write_text(json.dumps({"sessions": []}, ensure_ascii=False), encoding="utf-8")
            (data_dir / "tasks_source.json").write_text("[]", encoding="utf-8")

            with mock.patch.object(bridge, "data_dir", return_value=data_dir):
                created = bridge.create_chat_session("")
                self.assertTrue(created["ok"])
                session_id = created["session"]["id"]

                uploaded = bridge.upload_chat_attachments(
                    session_id,
                    [
                        {
                            "filename": "需求说明.md",
                            "contentType": "text/markdown",
                            "content": "# 标题\n\n这里是附件正文。\n".encode("utf-8"),
                        }
                    ],
                )
                self.assertTrue(uploaded["ok"])
                attachment = uploaded["attachments"][0]
                self.assertEqual(attachment["kind"], "document")
                self.assertIn("这里是附件正文", attachment["textExcerpt"])
                self.assertTrue(pathlib.Path(attachment["path"]).exists())

                removed = bridge.remove_chat_attachment(session_id, attachment["id"])
                self.assertTrue(removed["ok"])
                self.assertFalse(pathlib.Path(attachment["path"]).exists())

                session = bridge.get_chat_session(session_id)
                self.assertTrue(session["ok"])
                self.assertEqual(session["session"]["pendingAttachments"], [])

    def test_remove_missing_attachment_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = pathlib.Path(tmp) / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "chat_sessions.json").write_text(
                json.dumps({"sessions": [{"id": "chat-1", "title": "新对话", "messages": [], "pendingAttachments": []}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (data_dir / "tasks_source.json").write_text("[]", encoding="utf-8")

            with mock.patch.object(bridge, "data_dir", return_value=data_dir):
                result = bridge.remove_chat_attachment("chat-1", "att-missing")

        self.assertFalse(result["ok"])
        self.assertIn("未找到待删除附件", result["error"])


if __name__ == "__main__":
    unittest.main()
