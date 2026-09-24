"""FastAPI app exposing the engine over HTTP."""
import argparse
import json
import os
import secrets
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .jobs import JobManager
from .probe import probe


class JobRequest(BaseModel):
    url: str
    fmt: str | None = None
    headers: dict | None = None


class ProbeRequest(BaseModel):
    url: str
    headers: dict | None = None


def _web_dir() -> Path:
    """Location of the bundled web UI (differs in PyInstaller-frozen builds)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
        for cand in (base / "suravidl_engine" / "web", base / "web"):
            if (cand / "index.html").exists():
                return cand
    return Path(__file__).parent / "web"


def create_app(download_dir, auth_token: str | None = None,
               db_path=None, max_concurrent: int = 2,
               update_fn=None, update_check_fn=None,
               settings_path=None, desktop_actions: dict | None = None) -> FastAPI:
    from .settings import Settings

    app = FastAPI(title="suravidl engine")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^chrome-extension://[a-p]+$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    if settings_path is None and db_path:
        settings_path = Path(db_path).parent / "settings.json"
    settings = Settings(path=settings_path, default_download_dir=download_dir,
                        default_max_concurrent=max_concurrent)
    manager = JobManager(
        download_dir=settings.get()["download_dir"],
        db_path=db_path,
        max_concurrent=settings.get()["max_concurrent"],
    )
    acts = desktop_actions or {}

    if acts.get("reveal"):
        def _maybe_reveal(job):
            if settings.get()["open_dir_on_complete"] and job.get("filepath"):
                acts["reveal"](job["filepath"])

        manager.on_complete = _maybe_reveal

    def require_auth(
        creds: HTTPAuthorizationCredentials | None = Security(HTTPBearer(auto_error=False)),
    ):
        if auth_token and (creds is None or creds.credentials != auth_token):
            raise HTTPException(status_code=401, detail="unauthorized")
        return manager

    @app.get("/health")
    def health():
        return {"ok": True, "version": __version__,
                "download_dir": str(download_dir)}

    @app.get("/", response_class=HTMLResponse)
    def index():
        html = (_web_dir() / "index.html").read_text(encoding="utf-8")
        cfg = json.dumps({"token": auth_token or "",
                          "downloadDir": str(download_dir)})
        return HTMLResponse(html.replace('"__CFG__"', cfg))

    app.mount("/static", StaticFiles(directory=str(_web_dir())), name="static")

    @app.get("/version")
    def version(_mgr: JobManager = Depends(require_auth)):
        import yt_dlp.version

        return {"engine": __version__, "yt_dlp": yt_dlp.version.__version__}

    @app.post("/update")
    def update(_mgr: JobManager = Depends(require_auth)):
        from . import updater

        # sync endpoint -> runs in FastAPI's worker thread; pip may take a while
        return (update_fn or updater.self_update)()

    @app.get("/update-check")
    def update_check(_mgr: JobManager = Depends(require_auth)):
        from . import updater

        if update_check_fn:
            return update_check_fn()
        return updater.check_update(__version__)

    @app.get("/settings")
    def get_settings(_mgr: JobManager = Depends(require_auth)):
        return settings.get()

    @app.post("/settings")
    def post_settings(body: dict, _mgr: JobManager = Depends(require_auth)):
        try:
            updated = settings.update(body)
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if "download_dir" in body:
            manager.set_download_dir(updated["download_dir"])
        if "max_concurrent" in body:
            manager.set_capacity(updated["max_concurrent"])
        return updated

    @app.get("/app/info")
    def app_info(_mgr: JobManager = Depends(require_auth)):
        return {"desktop": bool(acts.get("quit") or acts.get("minimize")),
                "can_minimize": bool(acts.get("minimize"))}

    def _window_action(name: str):
        fn = acts.get(name)
        if not fn:
            raise HTTPException(status_code=501,
                                detail="not running in the desktop app")
        fn()
        return {"ok": True}

    @app.post("/app/minimize")
    def app_minimize(_mgr: JobManager = Depends(require_auth)):
        return _window_action("minimize")

    @app.post("/app/quit")
    def app_quit(_mgr: JobManager = Depends(require_auth)):
        return _window_action("quit")

    @app.post("/probe")
    def probe_endpoint(body: ProbeRequest, mgr: JobManager = Depends(require_auth)):
        try:
            return probe(body.url, extra_headers=body.headers)
        except Exception as e:  # noqa: BLE001 - error goes to the client
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/jobs")
    def create_job(body: JobRequest, mgr: JobManager = Depends(require_auth)):
        return mgr.create(body.url, fmt=body.fmt, extra_headers=body.headers)

    @app.get("/jobs")
    def list_jobs(mgr: JobManager = Depends(require_auth)):
        return {"jobs": mgr.list()}

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str, mgr: JobManager = Depends(require_auth)):
        try:
            return mgr.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None

    @app.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, mgr: JobManager = Depends(require_auth)):
        try:
            return mgr.cancel(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from None

    @app.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str, mgr: JobManager = Depends(require_auth)):
        try:
            return mgr.retry(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from None

    return app


def main() -> None:  # console entry: python -m suravidl_engine.api
    import uvicorn

    p = argparse.ArgumentParser(description="suravidl engine server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--download-dir", default=Path.home() / "Downloads")
    p.add_argument("--db", default=Path.home() / ".suravidl" / "jobs.db")
    args = p.parse_args()
    token = os.environ.get("SURAVIDL_TOKEN") or secrets.token_hex(16)
    if not os.environ.get("SURAVIDL_TOKEN"):
        print(f"Generated API token: {token}")
    uvicorn.run(
        create_app(download_dir=args.download_dir, auth_token=token,
                   db_path=args.db),
        host=args.host, port=args.port,
    )


if __name__ == "__main__":
    main()
