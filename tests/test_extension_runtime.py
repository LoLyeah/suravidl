"""M4: the extension's own logic, run for real (Node, stubbed chrome API).

The emulator can host the Android shell but not a Chrome extension, and a real
browser test would drag xvfb into CI. So `extension/test_harness.mjs` loads the
background script into Node with just enough `chrome` to be honest — storage,
three webRequest listeners, a badge — and fires it with realistic requests.
What gets remembered, what gets captured, and what the engine is asked are all
asserted there; this wrapper makes it part of the suite.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HARNESS = ROOT / "extension/test_harness.mjs"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_extensions_logic_runs():
    out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True,
                         cwd=str(ROOT), timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "all checks passed" in out.stdout
