"""v0.45.23 "the wait" — the handoff waits for a booting engine.

Field report (2026-10-08, Android): "the toast happened literally seconds
after download from sniffing". Mechanically true: the engine's token is
written at service start (instantly), but the Python engine boots on a
background thread — chaquopy warm-up, module import, DB load — before its
port listens, and the in-app browser is usable throughout by design (a
shell that cannot get an answer shows everything, never hides on a
guess). A tap in that window failed at connect speed and read as "the
engine refused it — is it still running?".

The repair: the browser queues through Handoff.downloadWhenReady, which
retries a failure ONLY when it provably happened before the request body
was written — the engine's door was shut and nothing ever reached it, so
a retry cannot double-queue. A request already on the wire is never
retried: its outcome is unknown, and a surprise duplicate would be worse
than one rare "try again".
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KT = ROOT / "android" / "app" / "src" / "main" / "java" / "com" / "suravidl" / "app"
BROWSER = (KT / "BrowserActivity.kt").read_text(encoding="utf-8")
HANDOFF = (KT / "Handoff.kt").read_text(encoding="utf-8")


def test_the_browser_queues_patiently():
    assert "Handoff.downloadWhenReady(" in BROWSER
    assert "Handoff.download(engineOrigin(), token, c.url, headers)" not in BROWSER, \
        "the impatient call must be gone from the queue path"


def test_retry_only_when_nothing_reached_the_engine():
    # the safety contract lives in postOutcome: `sent` flips only when the
    # request body was written, and an unsent failure is the only retryable one
    assert "var sent = false" in HANDOFF
    assert "sent = true" in HANDOFF
    assert "null to !sent" in HANDOFF, "only pre-send failures may retry"


def test_the_wait_is_bounded_and_patient():
    assert "attempts: Int = 24" in HANDOFF and "delayMs: Long = 1500" in HANDOFF, \
        "a bounded wait: ~36s covers a cold chaquopy boot"
    assert "Thread.sleep(delayMs)" in HANDOFF
    # and classify/rank keep the plain post (their callers never queue work)
    assert "postOutcome(base, token, path, body).first" in HANDOFF
