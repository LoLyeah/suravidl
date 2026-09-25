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
from .auth import cookie_session
from .download_opts import probe_extra_opts
from .jobs import JobManager, redact_job
from .probe import probe


class JobRequest(BaseModel):
    url: str
    fmt: str | None = None
    headers: dict | None = None
    preset: str | None = None
    playlist_items: str | None = None
    raw_args: str | None = None


class OpenUrlRequest(BaseModel):
    url: str


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
    archive_path = (Path(db_path).parent / "archive.txt") if db_path else None

    def _download_opts(dl_dir, raw_args=None):
        from .download_opts import build_download_opts

        return build_download_opts(settings.get(), dl_dir,
                                   archive_path=archive_path,
                                   raw_args=raw_args)

    manager = JobManager(
        download_dir=settings.get()["download_dir"],
        db_path=db_path,
        max_concurrent=settings.get()["max_concurrent"],
        auto_resume=settings.get()["auto_resume"],
        cookie_session=lambda: cookie_session(settings.get()),
        download_opts=_download_opts,
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
                          "downloadDir": str(manager.download_dir),
                          "theme": settings.get()["theme"],
                          "glass": settings.get()["glass"]})
        # Stamp the asset URLs with the version: embedded WebViews (Android,
        # pywebview) happily keep old styles.css/app.js cached under the same
        # URL, which showed a v0.13 HTML wearing the v0.11 CSS. A new URL per
        # release makes a stale copy impossible.
        for asset in ("style.css", "app.js", "icon.png"):
            html = html.replace(f"/static/{asset}", f"/static/{asset}?v={__version__}")
        return HTMLResponse(html.replace('"__CFG__"', cfg))

    @app.middleware("http")
    async def _no_store_ui_assets(request, call_next):
        """Never let a WebView serve yesterday's UI from its cache."""
        resp = await call_next(request)
        if request.url.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    app.mount("/static", StaticFiles(directory=str(_web_dir())), name="static")

    @app.get("/options")
    def list_options(_mgr: JobManager = Depends(require_auth)):
        """The full yt-dlp option catalogue (generated, never hand-written)."""
        from .options_catalogue import build_catalogue

        catalogue = build_catalogue()
        return {"count": len(catalogue), "options": catalogue}

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
                "can_minimize": bool(acts.get("minimize")),
                "can_pick_file": bool(acts.get("pick_file")),
                "can_open_url": bool(acts.get("open_url"))}

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

    @app.post("/app/pick-file")
    def app_pick_file(_mgr: JobManager = Depends(require_auth)):
        """Native file picker (desktop app only). Returns {"path": str|None}."""
        fn = acts.get("pick_file")
        if not fn:
            raise HTTPException(status_code=501,
                                detail="file picking is only available in the desktop app")
        try:
            return {"path": fn()}
        except Exception:  # noqa: BLE001 - a cancelled/broken dialog is not an error
            return {"path": None}

    @app.post("/app/open-url")
    def app_open_url(body: OpenUrlRequest,
                     _mgr: JobManager = Depends(require_auth)):
        """Open an https link in the user's real browser (desktop only).

        pywebview windows cannot honour target=_blank, and Android WebViews
        have no tabs — this is the way out of the app shell for links like
        release pages.
        """
        from urllib.parse import urlparse

        url = str(body.url or "").strip()
        if len(url) > 500 or urlparse(url).scheme != "https" \
                or not urlparse(url).hostname:
            raise HTTPException(status_code=400,
                                detail="only https links can be opened")
        fn = acts.get("open_url")
        if not fn:
            raise HTTPException(status_code=501,
                                detail="not running in the desktop app")
        try:
            fn(url)
        except Exception as e:  # noqa: BLE001 - report, don't crash the app
            raise HTTPException(status_code=502,
                                detail=f"could not open the browser: {e}") from e
        return {"opened": url}

    @app.post("/probe")
    def probe_endpoint(body: ProbeRequest, mgr: JobManager = Depends(require_auth)):
        try:
            with cookie_session(settings.get()) as cookie_opts:
                return probe(body.url, extra_headers=body.headers,
                             cookie_opts=cookie_opts,
                             extra_opts=probe_extra_opts(settings.get()))
        except Exception as e:  # noqa: BLE001 - error goes to the client
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.post("/jobs")
    def create_job(body: JobRequest, mgr: JobManager = Depends(require_auth)):
        s = settings.get()
        raw = body.raw_args
        if raw is not None and not s["raw_args_enabled"]:
            raise HTTPException(
                status_code=400,
                detail="raw yt-dlp arguments are disabled in Settings → Advanced")
        if raw is None and s["raw_args_enabled"]:
            # snapshot the global arguments onto the job so retry/resume
            # re-run exactly what ran the first time
            raw = s["raw_args"] or None
        try:
            return redact_job(mgr.create(body.url, fmt=body.fmt,
                                         extra_headers=body.headers,
                                         preset=body.preset,
                                         playlist_items=body.playlist_items,
                                         raw_args=raw))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/files/summary")
    def files_summary(_mgr: JobManager = Depends(require_auth)):
        """How much lives in the download folder (the UI shows this before a wipe)."""
        d = Path(manager.download_dir)
        files = [p for p in d.rglob("*") if p.is_file()] if d.exists() else []
        return {"dir": str(d), "files": len(files),
                "bytes": sum(p.stat().st_size for p in files)}

    @app.post("/files/clear")
    def files_clear(mgr: JobManager = Depends(require_auth)):
        """Delete every downloaded file (sidecars included).

        This exists because on Android the download folder is app-private —
        a file manager cannot open Android/data, so the app has to offer the
        cleanup itself. Completed job rows go with their files; errored jobs
        stay so they can be retried.
        """
        d = Path(manager.download_dir)
        deleted = freed = 0
        if d.exists():
            for p in sorted(d.rglob("*"), key=lambda q: len(q.parts), reverse=True):
                if p.is_file():
                    try:
                        freed += p.stat().st_size
                        p.unlink()
                        deleted += 1
                    except OSError:
                        pass
                elif p.is_dir():
                    try:
                        p.rmdir()
                    except OSError:
                        pass
        pruned = mgr.clear_completed()
        return {"deleted": deleted, "freed_bytes": freed,
                "cleared_jobs": pruned, "dir": str(d)}

    @app.get("/jobs")
    def list_jobs(mgr: JobManager = Depends(require_auth)):
        return {"jobs": [redact_job(j) for j in mgr.list()]}

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str, mgr: JobManager = Depends(require_auth)):
        try:
            return redact_job(mgr.get(job_id))
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None

    @app.post("/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, mgr: JobManager = Depends(require_auth)):
        try:
            return redact_job(mgr.cancel(job_id))
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from None

    @app.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str, mgr: JobManager = Depends(require_auth)):
        try:
            return redact_job(mgr.retry(job_id))
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from None

    @app.post("/jobs/{job_id}/reveal")
    def reveal_job(job_id: str, mgr: JobManager = Depends(require_auth)):
        try:
            job = mgr.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        if not job.get("filepath"):
            raise HTTPException(status_code=409,
                                detail="this job has no file yet")
        if not acts.get("reveal"):
            raise HTTPException(status_code=501,
                                detail="not running in the desktop app")
        acts["reveal"](job["filepath"])
        return {"ok": True}

    @app.post("/jobs/{job_id}/delete")
    def delete_job_endpoint(job_id: str, mgr: JobManager = Depends(require_auth)):
        """The trash button: delete one download's file(s) and forget its row."""
        try:
            return mgr.delete_job(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        except (ValueError, PermissionError) as e:
            raise HTTPException(status_code=409, detail=str(e)) from None

    app.state.manager = manager
    app.state.download_dir = Path(manager.download_dir)
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
