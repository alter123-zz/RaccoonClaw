#!/usr/bin/env python3
"""Manage queued Xueqiu discussion drafts that require manual confirmation."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from file_lock import atomic_json_read, atomic_json_write
from runtime_paths import canonical_data_dir
from utils import beijing_now


OCLAW_HOME = Path.home() / ".openclaw"
STATE_FILE = canonical_data_dir() / "xueqiu_pending_publish.json"
PENDING_DIR = OCLAW_HOME / "playwright-community-publisher" / "pending"
PUBLISHER_SCRIPT = OCLAW_HOME / "workspace-chief_of_staff" / "skills" / "playwright-community-publisher" / "scripts" / "community_publisher.mjs"


def _default_state() -> dict[str, Any]:
    return {"generatedAt": None, "items": []}


def _load_state() -> dict[str, Any]:
    data = atomic_json_read(STATE_FILE, _default_state())
    if not isinstance(data, dict):
        return _default_state()
    items = data.get("items")
    if not isinstance(items, list):
        data["items"] = []
    return data


def _save_state(state: dict[str, Any]) -> None:
    state["generatedAt"] = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    atomic_json_write(STATE_FILE, state)


def _next_draft_id(items: list[dict[str, Any]]) -> str:
    prefix = beijing_now().strftime("XQ-%Y%m%d-")
    max_seq = 0
    for item in items:
        draft_id = str(item.get("id") or "")
        if not draft_id.startswith(prefix):
            continue
        try:
            seq = int(draft_id.split("-")[-1])
        except Exception:
            continue
        max_seq = max(max_seq, seq)
    return f"{prefix}{max_seq + 1:03d}"


def _find_item(items: list[dict[str, Any]], draft_id: str | None = None, latest: bool = False) -> dict[str, Any] | None:
    if draft_id:
        for item in items:
            if str(item.get("id") or "") == draft_id:
                return item
        return None
    if latest:
        pending = [item for item in items if str(item.get("status") or "") == "pending"]
        if pending:
            return sorted(pending, key=lambda item: str(item.get("createdAt") or ""))[-1]
    return None


def create_pending_draft(
    *,
    content: str,
    title: str = "",
    source: str = "manual",
    source_artifact_dir: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = _load_state()
    items = state.setdefault("items", [])
    draft_id = _next_draft_id(items)
    created_at = beijing_now().strftime("%Y-%m-%d %H:%M:%S")

    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    content_path = PENDING_DIR / f"{draft_id}.txt"
    content_path.write_text(content.strip() + "\n", encoding="utf-8")

    item = {
        "id": draft_id,
        "title": title.strip(),
        "status": "pending",
        "source": source,
        "sourceArtifactDir": source_artifact_dir,
        "contentPath": str(content_path),
        "contentPreview": content.strip()[:240],
        "createdAt": created_at,
        "updatedAt": created_at,
        "metadata": metadata or {},
    }
    items.append(item)
    _save_state(state)
    return item


def _publish_item(item: dict[str, Any], headless: bool = False) -> dict[str, Any]:
    content_path = Path(str(item.get("contentPath") or "")).expanduser()
    if not content_path.exists():
        return {
            "status": "blocked",
            "reason": "missing_pending_draft",
            "message": f"待发布草稿不存在: {content_path}",
            "draftId": item.get("id"),
        }
    if not PUBLISHER_SCRIPT.exists():
        return {
            "status": "blocked",
            "reason": "missing_publisher_script",
            "message": f"未找到雪球发布脚本: {PUBLISHER_SCRIPT}",
            "draftId": item.get("id"),
        }

    command = [
        "node",
        str(PUBLISHER_SCRIPT),
        "--site",
        "xueqiu",
        "--action",
        "discussion",
        "--content-file",
        str(content_path),
        "--mode",
        "publish",
    ]
    if headless:
        command.extend(["--headless", "true"])

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=420,
        )
    except Exception as exc:
        return {
            "status": "blocked",
            "reason": "publish_exec_failed",
            "message": str(exc),
            "draftId": item.get("id"),
        }

    payload_text = (completed.stdout or completed.stderr or "").strip()
    try:
        result = json.loads(payload_text) if payload_text else {"status": "blocked", "reason": "empty_publisher_output"}
    except Exception:
        result = {
            "status": "blocked" if completed.returncode else "ok",
            "reason": "non_json_publisher_output",
            "message": payload_text,
        }

    result["draftId"] = item.get("id")
    result["contentPath"] = str(content_path)
    result["exitCode"] = completed.returncode
    return result


def publish_pending_draft(draft_id: str | None = None, latest: bool = False, headless: bool = False) -> dict[str, Any]:
    state = _load_state()
    items = state.setdefault("items", [])
    item = _find_item(items, draft_id=draft_id, latest=latest)
    if not item:
        return {
            "status": "blocked",
            "reason": "pending_draft_not_found",
            "message": "未找到待确认的雪球草稿",
        }

    if str(item.get("status") or "") != "pending":
        return {
            "status": "blocked",
            "reason": "pending_draft_not_publishable",
            "message": f"草稿当前状态不可发布: {item.get('status')}",
            "draftId": item.get("id"),
        }

    result = _publish_item(item, headless=headless)
    item["updatedAt"] = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    item["lastResult"] = result
    item["status"] = "published" if result.get("status") == "published" else "blocked"
    _save_state(state)
    return result


def cancel_pending_draft(draft_id: str | None = None, latest: bool = False) -> dict[str, Any]:
    state = _load_state()
    items = state.setdefault("items", [])
    item = _find_item(items, draft_id=draft_id, latest=latest)
    if not item:
        return {
            "status": "blocked",
            "reason": "pending_draft_not_found",
            "message": "未找到待确认的雪球草稿",
        }

    item["status"] = "cancelled"
    item["updatedAt"] = beijing_now().strftime("%Y-%m-%d %H:%M:%S")
    _save_state(state)
    return {
        "status": "cancelled",
        "draftId": item.get("id"),
        "message": "已取消该雪球待发布草稿",
    }


def show_pending_draft(draft_id: str | None = None, latest: bool = False) -> dict[str, Any]:
    state = _load_state()
    items = state.setdefault("items", [])
    item = _find_item(items, draft_id=draft_id, latest=latest)
    if not item:
        return {
            "status": "blocked",
            "reason": "pending_draft_not_found",
            "message": "未找到待确认的雪球草稿",
        }
    content_path = Path(str(item.get("contentPath") or "")).expanduser()
    content = ""
    if content_path.exists():
        try:
            content = content_path.read_text(encoding="utf-8")
        except Exception:
            content = ""

    return {
        "status": "ok",
        "draftId": item.get("id"),
        "title": item.get("title"),
        "contentPath": item.get("contentPath"),
        "contentPreview": item.get("contentPreview"),
        "content": content,
        "createdAt": item.get("createdAt"),
        "updatedAt": item.get("updatedAt"),
        "source": item.get("source"),
        "sourceArtifactDir": item.get("sourceArtifactDir"),
        "metadata": item.get("metadata") or {},
    }


def _cli_create(args: argparse.Namespace) -> dict[str, Any]:
    content_path = Path(args.content_file).expanduser()
    if not content_path.exists():
        return {
            "status": "blocked",
            "reason": "missing_content_file",
            "message": f"内容文件不存在: {content_path}",
        }
    metadata = {}
    if args.metadata_json:
        metadata = json.loads(Path(args.metadata_json).expanduser().read_text(encoding="utf-8"))
    item = create_pending_draft(
        content=content_path.read_text(encoding="utf-8"),
        title=args.title,
        source=args.source,
        source_artifact_dir=args.source_artifact_dir,
        metadata=metadata,
    )
    return {
        "status": "awaiting_confirmation",
        "draftId": item["id"],
        "contentPath": item["contentPath"],
        "createdAt": item["createdAt"],
        "message": "雪球草稿已入队，等待人工确认后发布。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage pending Xueqiu discussion drafts")
    sub = parser.add_subparsers(dest="command", required=True)

    create_parser = sub.add_parser("create", help="Create a pending draft")
    create_parser.add_argument("--content-file", required=True, help="Draft content file")
    create_parser.add_argument("--title", default="", help="Draft title")
    create_parser.add_argument("--source", default="manual", help="Draft source")
    create_parser.add_argument("--source-artifact-dir", default="", help="Artifact directory that generated this draft")
    create_parser.add_argument("--metadata-json", default="", help="Optional JSON file with extra metadata")

    publish_parser = sub.add_parser("publish", help="Publish a pending draft")
    publish_parser.add_argument("--id", default="", help="Draft id")
    publish_parser.add_argument("--latest", action="store_true", help="Use latest pending draft")
    publish_parser.add_argument("--headless", action="store_true", help="Use headless browser")

    cancel_parser = sub.add_parser("cancel", help="Cancel a pending draft")
    cancel_parser.add_argument("--id", default="", help="Draft id")
    cancel_parser.add_argument("--latest", action="store_true", help="Use latest pending draft")

    show_parser = sub.add_parser("show", help="Show a pending draft")
    show_parser.add_argument("--id", default="", help="Draft id")
    show_parser.add_argument("--latest", action="store_true", help="Use latest pending draft")

    args = parser.parse_args()
    if args.command == "create":
        result = _cli_create(args)
    elif args.command == "publish":
        result = publish_pending_draft(draft_id=args.id or None, latest=args.latest, headless=args.headless)
    elif args.command == "cancel":
        result = cancel_pending_draft(draft_id=args.id or None, latest=args.latest)
    else:
        result = show_pending_draft(draft_id=args.id or None, latest=args.latest)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") not in {"blocked"} else 4


if __name__ == "__main__":
    raise SystemExit(main())
