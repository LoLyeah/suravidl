"""v0.38.6 — the straight answer.

Report (phone, 2026-10-01): a probe of an unsupported site showed the
humanized line "the site wants a signed-in session — load cookies..." over
a details block that plainly said "Unsupported URL ... no extractor". Two
defects:

1. humanErr's sign-in regex had a bare `age` alternative — it matched
   "page" (and "storage") in every unsupported-URL message, so the wrong
   branch won.
2. The engine ALREADY sends a structured verdict (detail.unsupported with
   a hint — auth.py) and the api() helper already carries it on the Error
   (err.detail) — but the UI re-guessed from the text instead of letting
   the engine's verdict lead.

The regex path stays for plain job errors; the structured path leads
wherever it exists.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "src" / "suravidl_engine" / "web" / "app.js").read_text()
NODE = shutil.which("node")

VIDOVR = ("ERROR: Unsupported URL: https://vidovr.com/d/gx85ppdotgwb — "
          "yt-dlp has no extractor for this page — open it in the browser, "
          "press play for a second, and pick the stream suravidl finds "
          "(on desktop the extension does the same).")


def _human_err_source() -> str:
    src = APP
    i = src.find("function humanErr")
    assert i != -1, "humanErr not found"
    depth, j = 0, i
    while True:
        ch = src[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return src[i:j + 1]


def _run(cases):
    script = (_human_err_source()
              + "\nconst cases = " + json.dumps(cases) + ";"
              + "\nconsole.log(JSON.stringify(cases.map(([s, d]) => humanErr(s, d))));")
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True,
                       timeout=20)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ---------- 1. behaviour (real JS, run in node) ----------
def test_the_verdicts_are_truthful():
    if NODE is None:
        import pytest
        pytest.skip("node not available")
    cases = [
        # the engine's structured verdict leads: the unsupported flag can
        # never be read as a sign-in wall whatever the text says
        [VIDOVR, {"unsupported": True, "hint": "x"}],
        # the plain-text path (job errors): unsupported beats the age/„page" trap
        [VIDOVR, None],
        # real sign-in walls still say cookies
        ["ERROR: Sign in to confirm you're not a bot. Use --cookies", None],
        ["ERROR: This video is age-restricted", None],
        # "age" must never match inside page/storage
        ["ERROR: Scraping this page failed", None],
        ["ERROR: unable to write file: no space left on storage", None],
        # the classics keep working
        ["ERROR: HTTP Error 403: Forbidden", None],
        ["ERROR: HTTP Error 429: Too Many Requests", None],
        ["ERROR: no suitable extractor found", None],
    ]
    out = _run(cases)
    unsupported, plain, signin, agerestricted, page, storage, e403, e429, suitable = out
    for got in (unsupported, plain, suitable):
        assert "cookies" not in got, got
        assert "play" in got and "Scan" in got, got
    assert "cookies" in signin and "Scan" not in signin
    assert "cookies" in agerestricted
    assert "cookies" not in page, page
    assert "cookies" not in storage, storage
    assert "403" in e403
    assert "429" in e429


# ---------- 2. the wiring pins ----------
def test_the_probe_passes_the_structured_verdict_through():
    assert "humanErr(e.message, e.detail)" in APP


def test_unsupported_is_classified_before_the_signin_family():
    fn = _human_err_source()
    assert fn.find("unsupported url") != -1
    assert fn.find("unsupported url") < fn.find("sign[ -]?in"), \
        "the unsupported branch must win before any sign-in guess"


def test_every_signin_alternative_has_boundaries():
    fn = _human_err_source()
    assert r"\bsign[ -]?in\b" in fn
    assert r"\blog[ -]?in\b" in fn
    assert r"\bage\b" in fn
    # the old bare alternative is what matched "page"
    assert not re.search(r"sign \?in\|log \?in", fn)