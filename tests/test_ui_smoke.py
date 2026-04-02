"""Optional browser smoke test for a running workbench instance."""

from __future__ import annotations

import os
import pathlib
import subprocess
import shutil
import unittest


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ui_smoke.py"


@unittest.skipUnless(os.environ.get("WORKBENCH_UI_SMOKE_URL"), "set WORKBENCH_UI_SMOKE_URL to run browser smoke")
class UISmokeTests(unittest.TestCase):
    def test_ui_smoke_script(self) -> None:
        env = os.environ.copy()
        python_bin = env.get("WORKBENCH_UI_SMOKE_PYTHON") or shutil.which("python3") or "python3"
        result = subprocess.run(
            [python_bin, str(SCRIPT)],
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout or result.stderr)


if __name__ == "__main__":
    unittest.main()
