#!/usr/bin/env python3
"""Install an exported mode pack into a target directory for reuse."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from runtime_paths import openclaw_home
from utils import beijing_now


DEFAULT_DEST = openclaw_home() / "mode-packs"


def install_mode_pack(pack_dir: Path, dest_root: Path) -> Path:
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"找不到 manifest.json: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mode = manifest.get("mode") if isinstance(manifest, dict) else {}
    mode_key = str(mode.get("key") or "")
    if not mode_key:
        raise SystemExit("manifest.json 缺少 mode.key")

    target = dest_root / mode_key
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(pack_dir, target)
    (target / "installed.json").write_text(
        json.dumps(
            {
                "installedAt": beijing_now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": str(pack_dir),
                "modeKey": mode_key,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Install an exported workbench mode pack")
    parser.add_argument("--pack", required=True, help="Path to exported mode pack")
    parser.add_argument("--dest", default=str(DEFAULT_DEST), help="Destination root directory")
    args = parser.parse_args()

    target = install_mode_pack(Path(args.pack).expanduser(), Path(args.dest).expanduser())
    print(str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
