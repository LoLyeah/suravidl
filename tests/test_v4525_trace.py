"""v0.45.25 "the trace" — an unhandled error names itself.

A bare FastAPI 500 reaches the app's UI as the literal string "500" —
the owner sees "could not delete: 500" and has nothing to act on
(2026-10-08, twice). Any unhandled exception now answers with its type
and message as JSON (the toast carries them) and the full traceback
lands in the engine log behind Settings -> View log.
"""
from fastapi.testclient import TestClient

from suravidl_engine.api import create_app


def test_an_unhandled_error_answers_with_its_cause(tmp_path):
    app = create_app(str(tmp_path / "dl"), auth_token="t")

    @app.get("/__boom")
    def boom():
        raise RuntimeError("kaboom on purpose")

    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/__boom", headers={"Authorization": "Bearer t"})
    assert r.status_code == 500
    detail = r.json()["detail"]
    assert "RuntimeError" in detail and "kaboom on purpose" in detail, detail

    from suravidl_engine import logcap
    assert any("kaboom on purpose" in ln for ln in logcap.lines()), \
        "the traceback must reach the log the app can show"
