"""FastAPI app exposing the engine over HTTP."""
import argparse
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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


def create_app(download_dir, auth_token: str | None = None,
               db_path=None, max_concurrent: int = 2,
               update_fn=None) -> FastAPI:
    app = FastAPI(title="suravidl engine")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^chrome-extension://[a-p]+$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    manager = JobManager(download_dir=download_dir, db_path=db_path,
                         max_concurrent=max_concurrent)

    def require_auth(
        creds: HTTPAuthorizationCredentials | None = Security(HTTPBearer(auto_error=False)),
    ):
        if auth_token and (creds is None or creds.credentials != auth_token):
            raise HTTPException(status_code=401, detail="unauthorized")
        return manager

    @app.get("/health")
    def health():
        return {"ok": True, "version": __version__}

    @app.get("/version")
    def version(_mgr: JobManager = Depends(require_auth)):
        import yt_dlp.version

        return {"engine": __version__, "yt_dlp": yt_dlp.version.__version__}

    @app.post("/update")
    def update(_mgr: JobManager = Depends(require_auth)):
        from . import updater

        # sync endpoint -> runs in FastAPI's worker thread; pip may take a while
        return (update_fn or updater.self_update)()

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
