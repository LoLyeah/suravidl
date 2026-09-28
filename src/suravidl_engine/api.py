"""FastAPI app exposing the engine over HTTP."""
import argparse
import json
import os
import re
import secrets
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__
from .auth import (check_auth, cookie_session, explain_download_error,
                   unsupported_error)
from .classify import classify, patterns, rank
from .download_opts import probe_extra_opts
from .jobs import JobManager, redact_job
from .probe import probe
from . import site_memory


class JobRequest(BaseModel):
    url: str
    fmt: str | None = None
    headers: dict | None = None
    preset: str | None = None
    playlist_items: str | None = None
    raw_args: str | None = None
    # "this download only": a validated patch over the saved settings
    overrides: dict | None = None


class OpenUrlRequest(BaseModel):
    url: str


class ProbeRequest(BaseModel):
    url: str
    headers: dict[str, str] | None = None


class ClassifyRequest(BaseModel):
    url: str
    headers: dict | None = None


class RankRequest(BaseModel):
    urls: list[str] = []


class AuthCheckRequest(BaseModel):
    url: str | None = None


class FilesClearRequest(BaseModel):
    """The bulk wipe is destructive: it takes the word, not just a button."""
    confirm: str = ""


class BatchJobRequest(BaseModel):
    """Several links in one go — the "paste 10 links, queue them all" flow."""
    urls: list[str]
    fmt: str | None = None
    headers: dict | None = None
    preset: str | None = None
    playlist_items: str | None = None
    raw_args: str | None = None
    overrides: dict | None = None


class ArchiveForgetRequest(BaseModel):
    entry: str = ""


class RetryRequest(BaseModel):
    """Edits for a retry: anything left out is reused from the original job."""
    fmt: str | None = None
    preset: str | None = None
    overrides: dict | None = None
    raw_args: str | None = None


# one batch is a click, not a crawl: a bigger paste belongs in several goes
BATCH_MAX = 20

_MEDIA_TYPES = {
    ".mp4": "video/mp4", ".m4v": "video/x-m4v", ".webm": "video/webm",
    ".mkv": "video/x-matroska", ".mov": "video/quicktime",
    ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".aac": "audio/aac",
    ".opus": "audio/ogg", ".ogg": "audio/ogg", ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".srt": "text/plain; charset=utf-8", ".vtt": "text/vtt",
}


def _media_type(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def _range_span(size: int, header: str | None) -> tuple[int, int] | None:
    """Parse a single `Range: bytes=…` header into an inclusive (start, end).

    `None` means "serve the whole file". A syntactically valid but
    unsatisfiable range raises ValueError so the caller can answer 416.

    This exists because Starlette only learned to honour Range in its
    `FileResponse` at 0.39 — and the Android build pins `fastapi==0.99.1`,
    i.e. starlette 0.27, where a Range request quietly gets the WHOLE body
    with 200 (verified against 0.27.0 in a scratch venv). On that stack the
    in-app player could not seek at all: every scrub replayed from byte 0.
    """
    if not header:
        return None
    m = re.match(r"bytes=(\d*)-(\d*)\s*$", header.strip())
    if not m or (m.group(1) == "" and m.group(2) == ""):
        return None                      # unknown form: serve the whole file
    first, last = m.group(1), m.group(2)
    if first == "":                      # suffix range: the final N bytes
        n = int(last)
        if n <= 0 or size == 0:
            raise ValueError("empty or unsatisfiable range")
        return (max(0, size - n), size - 1)
    start = int(first)
    if start >= size:
        raise ValueError("range starts past the end")
    if last == "":
        return (start, size - 1)
    end = min(int(last), size - 1)
    if end < start:
        raise ValueError("inverted range")
    return (start, end)


def _stream_file(path: Path, request: Request):
    """One file, streamed with Range support (v0.22 review #10).

    Range is implemented here rather than handed to `FileResponse`, because
    the Android build's starlette (0.27, via fastapi 0.99.1) ignores Range
    and would answer every seek with the whole file. Both the job player and
    the folder sheet stream through this.
    """
    size = path.stat().st_size
    try:
        span = _range_span(size, request.headers.get("range"))
    except ValueError:
        return Response(status_code=416,
                        headers={"Content-Range": f"bytes */{size}",
                                 "Accept-Ranges": "bytes"})
    if span is None:
        start, end, status = 0, size - 1, 200
        headers = {"Accept-Ranges": "bytes"}
    else:
        start, end = span
        status = 206
        headers = {"Accept-Ranges": "bytes",
                   "Content-Range": f"bytes {start}-{end}/{size}"}
    headers["Content-Length"] = str(max(0, end - start + 1))
    # HTTP headers are latin-1: a raw non-ASCII name (CJK, Cyrillic, emoji)
    # made starlette raise UnicodeEncodeError and the file could not be
    # opened at all. RFC 5987: an ASCII fallback plus the UTF-8 form.
    from urllib.parse import quote

    ascii_name = path.name.encode("ascii", "replace").decode("ascii")
    headers["Content-Disposition"] = (
        f'inline; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(path.name)}")

    def body():
        with path.open("rb") as fh:
            fh.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = fh.read(min(64 * 1024, left))
                if not chunk:
                    break
                left -= len(chunk)
                yield chunk

    return StreamingResponse(body(), status_code=status, headers=headers,
                             media_type=_media_type(path))


# What the folder sheet calls media, subtitles, and everything else — and
# what it refuses to call a download at all: work files (a partial download,
# yt-dlp's control files) and the sidecars it wrote for itself (thumbnails,
# info json). A subtitle the user asked for IS a download and stays.
_FILE_KINDS = {
    "video": {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".3gp", ".avi", ".flv",
              ".ts"},
    "audio": {".m4a", ".mp3", ".opus", ".ogg", ".oga", ".wav", ".aac", ".flac",
              ".weba"},
    "subtitle": {".srt", ".vtt", ".ass", ".lrc"},
}
_FILE_SKIP_SUFFIXES = (".part", ".ytdl", ".temp", ".json", ".description",
                       ".xml", ".jpg", ".jpeg", ".png", ".webp")
FILE_LIST_MAX = 400                          # a page of files, not the disk


def _file_kind(path: Path) -> str:
    ext = path.suffix.lower()
    for kind, exts in _FILE_KINDS.items():
        if ext in exts:
            return kind
    return "other"


def _file_entries(root: Path) -> dict:
    """The download folder's own files, newest first, for the folder sheet.

    Android/data is closed to every file manager on Android 11+, so "open
    folder" has to show the folder inside the app (2026-09-27 report). The
    list is capped: an opaque folder with thousands of files is not more
    useful than its newest page in a phone-sized sheet.
    """
    out: list[dict] = []
    try:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            name = p.name
            if (name.startswith(".") or name.endswith(_FILE_SKIP_SUFFIXES)
                    or ".part-" in name):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            out.append({"name": p.relative_to(root).as_posix(),
                        "path": str(p), "bytes": st.st_size,
                        "mtime": st.st_mtime, "kind": _file_kind(p)})
    except OSError:
        pass
    out.sort(key=lambda f: f["mtime"], reverse=True)
    return {"total": len(out), "files": out[:FILE_LIST_MAX]}


def _looks_like_url(text: str) -> bool:
    """Is this paste item even a link?

    The single-link box can afford to hand yt-dlp anything (it answers with
    its own "not a valid URL"), but a paste of twenty lines usually carries a
    stray word or a blank: those are named and skipped instead of queued to
    fail later.
    """
    if not text or any(ch.isspace() for ch in text):
        return False
    if re.match(r"^[a-z][a-z0-9+.\-]*://", text, re.I):     # https://, ftp://
        return True
    if re.match(r"^[a-z][a-z0-9+.\-]*:[^/\s]", text, re.I):  # magnet:, ytsearch:
        return True
    return "." in text.split("/")[0]                        # bare host/path


def _web_dir() -> Path:
    """Location of the bundled web UI (differs in PyInstaller-frozen builds)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
        for cand in (base / "suravidl_engine" / "web", base / "web"):
            if (cand / "index.html").exists():
                return cand
    return Path(__file__).parent / "web"


def default_cache_dir() -> Path:
    """Where yt-dlp's own cache belongs.

    The shell decides: Android exports `SURAVIDL_CACHE_DIR` pointing at the
    app's cache bucket, so the system's Clear-cache button governs it and
    storage pressure may evict it. Without a shell it is the XDG cache home
    — the same place yt-dlp would use anyway, except the engine now owns the
    directory and can count and clear it (v0.24.9).
    """
    env = os.environ.get("SURAVIDL_CACHE_DIR", "").strip()
    if env:
        return Path(env)
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "suravidl"


def create_app(download_dir, auth_token: str | None = None,
               db_path=None, max_concurrent: int = 2,
               update_fn=None, update_check_fn=None,
               settings_path=None, desktop_actions: dict | None = None,
               page_key: str | None = None, cache_dir=None) -> FastAPI:
    from .settings import Settings
    from .presets import PresetStore, split_patch

    app = FastAPI(title="suravidl engine")
    app.add_middleware(
        CORSMiddleware,
        # both extension families talk to the engine: Chrome MV3 sends
        # `chrome-extension://<id>`, the Firefox build `moz-extension://<uuid>`
        # (the v0.21.2 audit found the Firefox origin getting a 400 preflight)
        allow_origin_regex=r"^(chrome-extension://[a-p]+|moz-extension://[0-9a-fA-F-]+)$",
        allow_credentials=False,
        # DELETE is a real method here: `DELETE /presets/{name}`
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    if settings_path is None and db_path:
        settings_path = Path(db_path).parent / "settings.json"
    settings = Settings(path=settings_path, default_download_dir=download_dir,
                        default_max_concurrent=max_concurrent)
    archive_path = (Path(db_path).parent / "archive.txt") if db_path else None
    # The engine's cache directory. Never created here: yt-dlp makes it when
    # it first caches something, and a test run must not leave a
    # ~/.cache/suravidl behind just by building an app.
    cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
    presets = PresetStore(
        (Path(settings_path).parent / "presets.json") if settings_path else None)

    def _download_opts(dl_dir, raw_args=None, overrides=None):
        from .download_opts import build_download_opts

        effective = settings.get()
        if overrides:
            # a per-download ("this download only") or preset-supplied patch
            # wins over the saved settings for this job alone
            effective = {**effective, **overrides}
        return build_download_opts(effective, dl_dir,
                                   archive_path=archive_path,
                                   raw_args=raw_args,
                                   cache_dir=cache_dir)

    manager = JobManager(
        download_dir=settings.get()["download_dir"],
        db_path=db_path,
        max_concurrent=settings.get()["max_concurrent"],
        auto_resume=settings.get()["auto_resume"],
        cookie_session=lambda: cookie_session(settings.get()),
        download_opts=_download_opts,
    )
    acts = desktop_actions or {}

    def remember_site_quality(url: str, fmt: str | None) -> None:
        """A quality pick is also a preference for that site (M20).

        Memory is a nicety: a broken settings file must never fail a download,
        so write failures are swallowed and the offer simply stays as it was.
        """
        try:
            memory = site_memory.record(
                settings.get().get("site_quality"), url, fmt)
            if memory is not None:
                settings.update({"site_quality": memory})
        except (ValueError, OSError):
            pass

    if acts.get("reveal"):
        def _maybe_reveal(job):
            if settings.get()["open_dir_on_complete"] and job.get("filepath"):
                acts["reveal"](job["filepath"])

        manager.on_complete = _maybe_reveal

    def require_auth(
        creds: HTTPAuthorizationCredentials | None = Security(HTTPBearer(auto_error=False)),
    ):
        if auth_token and (creds is None or not secrets.compare_digest(
                creds.credentials, auth_token)):
            raise HTTPException(status_code=401, detail="unauthorized")
        return manager

    @app.get("/health")
    def health():
        return {"ok": True, "version": __version__,
                "download_dir": str(download_dir)}

    @app.get("/", response_class=HTMLResponse)
    def index(k: str | None = None):
        # The page inlines the API token, and loopback is shared: on Android
        # any other installed app can open a socket to 127.0.0.1:8787. When the
        # shell sets a page key, only a request carrying it gets the page, so
        # the token stops being readable by whoever asks (v0.21.1 audit). The
        # desktop shells keep today's behaviour by not setting one.
        if page_key and k != page_key:
            raise HTTPException(status_code=401,
                                detail="this page needs its shell's key")
        html = (_web_dir() / "index.html").read_text(encoding="utf-8")
        cfg = json.dumps({"token": auth_token or "",
                          "downloadDir": str(manager.download_dir),
                          "theme": settings.get()["theme"],
                          "glass": settings.get()["glass"]})
        # < and & are escaped so a download folder containing "</script>" can
        # never close the element it is inlined into (v0.21.1 audit; json.dumps
        # alone escapes quotes only)
        cfg = cfg.replace("<", "\\u003c").replace("&", "\\u0026")
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

    @app.get("/whats-new")
    def whats_new(_mgr: JobManager = Depends(require_auth)):
        """The release notes behind the UI's one-time card after an update."""
        from . import whatsnew

        return whatsnew.payload()

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
        try:
            fn()
        except Exception as e:  # noqa: BLE001 - the window may be gone
            # a dead window is not a server error: say what happened (501,
            # same as an unwired action) instead of a 500 stack trace
            raise HTTPException(
                status_code=501,
                detail=f"the desktop window could not {name}: {e}") from e
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

    @app.post("/app/reveal-dir")
    def app_reveal_dir(_mgr: JobManager = Depends(require_auth)):
        """Open the download folder in the OS file manager (desktop only).

        Android cannot do this — no file manager may open Android/data — so
        the UI falls back to the folder sheet there (2026-09-27 report:
        "Add the open folder button too, below copy path").
        """
        fn = acts.get("reveal")
        if not fn:
            raise HTTPException(status_code=501,
                                detail="no file manager on this shell")
        try:
            fn(str(manager.download_dir))
        except Exception as e:  # noqa: BLE001 - the shell's dialog is best-effort
            raise HTTPException(
                status_code=501,
                detail=f"the file manager could not be opened: {e}") from e
        return {"ok": True}

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
                info = probe(body.url, extra_headers=body.headers,
                             cookie_opts=cookie_opts,
                             extra_opts=probe_extra_opts(settings.get()))
        except Exception as e:  # noqa: BLE001 - error goes to the client
            # one explanation for every shell: the engine owns the "this looks
            # like a sign-in wall" judgement, the UI does not guess
            raise HTTPException(status_code=400,
                                detail=(unsupported_error(str(e))
                                        or explain_download_error(str(e)))) from e
        # the site's remembered quality rides along as an offer (M20): the UI
        # marks that chip, the user still decides
        site = site_memory.host_of(body.url)
        if site:
            info["site"] = site
            info["site_quality"] = site_memory.clean(
                settings.get().get("site_quality") or {}).get(site)
        return info

    @app.post("/classify")
    def classify_endpoint(body: ClassifyRequest,
                          mgr: JobManager = Depends(require_auth)):
        """What is this URL? A sniffer asks before it shows anything."""
        try:
            return classify(body.url, headers=body.headers)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.get("/sniff/patterns")
    def sniff_patterns(mgr: JobManager = Depends(require_auth)):
        """The one media-pattern list: shells prefilter, the engine decides."""
        return patterns()

    @app.post("/sniff/rank")
    def sniff_rank(body: RankRequest, mgr: JobManager = Depends(require_auth)):
        """Which of these finds is worth showing? (manifest over fragments)

        Every shell asks the same question, so the answer lives here: fragments
        whose playlist was among the finds are hidden, with a reason, and
        nothing else is touched.
        """
        return rank(body.urls[:200])

    @app.post("/auth/check")
    def auth_check(body: AuthCheckRequest, mgr: JobManager = Depends(require_auth)):
        """Test cookies: is anything configured, and does it actually work?

        With a URL the answer is proven by a real extraction; without one only
        the cookies file itself can be read (values never leave the engine).
        """
        return check_auth(settings.get(), (body.url or "").strip() or None)

    def _queue_one(body: JobRequest, mgr: JobManager) -> dict:
        """Validate and queue one job — the shared heart of /jobs and /jobs/batch.

        Both paths must enforce the identical rules (raw-args gate, preset
        expansion, override whitelist): a batch endpoint that skips them is a
        way around the gate.
        """
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
        preset = body.preset
        overrides = body.overrides or None
        if preset:
            entry = presets.get(preset)
            if entry is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"unknown preset: {preset!r}")
            # v0.29.0: built-in and user presets expand the same way — an
            # intent preset is {"preset": name}, a bundle carries its options,
            # and both become (intent, per-job patch). Before this, a built-in
            # that was not a bare intent would have died as an unknown preset.
            intent, patch = split_patch(entry["patch"])
            preset = intent
            overrides = {**(overrides or {}), **patch} or None
        job = mgr.create(body.url, fmt=body.fmt,
                         extra_headers=body.headers,
                         preset=preset,
                         playlist_items=body.playlist_items,
                         raw_args=raw,
                         overrides=overrides)
        remember_site_quality(body.url, body.fmt)
        return redact_job(job)

    @app.post("/jobs")
    def create_job(body: JobRequest, mgr: JobManager = Depends(require_auth)):
        try:
            return _queue_one(body, mgr)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/jobs/batch")
    def create_jobs(body: BatchJobRequest, mgr: JobManager = Depends(require_auth)):
        """Queue several links at once (the v0.22 feature review's #5).

        One bad link must not cost the user the good ones: each is queued on
        its own and the refusals come back in `skipped`, with the reason.
        """
        urls = [str(u or "").strip() for u in body.urls]
        urls = [u for u in urls if u]
        if not urls:
            raise HTTPException(status_code=400,
                                detail="no links found in that paste")
        if len(urls) > BATCH_MAX:
            raise HTTPException(
                status_code=400,
                detail=f"at most {BATCH_MAX} links at a time "
                       f"(you sent {len(urls)})")
        # Body-level refusals fail the whole batch: they are about the request,
        # not about one link — and POST /jobs answers them the same way. Only
        # per-link problems become `skipped` entries.
        s = settings.get()
        if body.raw_args is not None and not s["raw_args_enabled"]:
            raise HTTPException(
                status_code=400,
                detail="raw yt-dlp arguments are disabled in Settings → Advanced")
        if body.preset and presets.get(body.preset) is None:
            raise HTTPException(
                status_code=400, detail=f"unknown preset: {body.preset!r}")
        created: list[dict] = []
        skipped: list[dict] = []
        for url in urls:
            if not _looks_like_url(url):
                skipped.append({"url": url[:200],
                                "error": "not a link — expecting something "
                                         "like https://…"})
                continue
            try:
                created.append(_queue_one(
                    JobRequest(url=url, fmt=body.fmt, headers=body.headers,
                               preset=body.preset,
                               playlist_items=body.playlist_items,
                               raw_args=body.raw_args, overrides=body.overrides),
                    mgr))
            except (ValueError, HTTPException) as e:
                detail = e.detail if isinstance(e, HTTPException) else str(e)
                skipped.append({"url": url[:200], "error": str(detail)})
        return {"jobs": created, "skipped": skipped}

    @app.get("/presets")
    def list_presets(_mgr: JobManager = Depends(require_auth)):
        # defaults + the per-job key list ride along so the UI can offer
        # "save the settings that differ from the defaults as a preset"
        from .download_opts import QUALITY_PRESETS
        from .settings import DEFAULTS, PER_JOB_KEYS

        return {"presets": presets.list(),
                "per_job_keys": list(PER_JOB_KEYS),
                "qualities": list(QUALITY_PRESETS),
                "defaults": {k: DEFAULTS[k] for k in PER_JOB_KEYS}}

    @app.post("/presets")
    def save_preset(body: dict, _mgr: JobManager = Depends(require_auth)):
        try:
            return presets.save(body.get("name", ""), body.get("patch") or {})
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.delete("/presets/{name}")
    def delete_preset(name: str, _mgr: JobManager = Depends(require_auth)):
        try:
            if not presets.delete(name):
                raise HTTPException(status_code=404,
                                    detail=f"no such preset: {name!r}")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"ok": True}

    def _dir_files(root: Path) -> list[Path]:
        try:
            return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []
        except OSError:
            return []

    def _dir_stats(root: Path) -> tuple[int, int]:
        """(files, bytes) under a root; a file that vanished mid-walk is just
        not counted."""
        files = _dir_files(root)
        total = 0
        for p in files:
            try:
                total += p.stat().st_size
            except OSError:
                pass
        return len(files), total

    def _wipe_dir(root: Path) -> tuple[int, int]:
        """Delete every file under `root` (deepest first) and the directories
        they leave empty. Returns (files, bytes); the root itself stays."""
        deleted = freed = 0
        if not root.exists():
            return deleted, freed
        try:
            entries = sorted(root.rglob("*"), key=lambda q: len(q.parts),
                             reverse=True)
        except OSError:
            return deleted, freed
        for p in entries:
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
        return deleted, freed

    def _cache_owns_downloads() -> bool:
        """True when the cache root contains (or equals) the download folder.

        The dangerous direction of overlap: wiping such a root would sweep
        the user's downloads as if they were cache. That is a config mistake,
        so the cache sweep stands down — the folder sweep owns those files."""
        try:
            c = Path(cache_dir).resolve()
            d = Path(manager.download_dir).resolve()
        except OSError:
            return True          # cannot tell: do not touch the cache
        return d == c or d.is_relative_to(c)

    @app.get("/files/summary")
    def files_summary(_mgr: JobManager = Depends(require_auth)):
        """How much lives in the download folder and in the app cache (the UI
        shows both before a wipe)."""
        files, total = _dir_stats(Path(manager.download_dir))
        cache_files, cache_total = _dir_stats(Path(cache_dir))
        return {"dir": str(manager.download_dir), "files": files, "bytes": total,
                "cache_dir": str(cache_dir), "cache_files": cache_files,
                "cache_bytes": cache_total}

    def _archive_lines() -> list[str]:
        if not archive_path or not Path(archive_path).exists():
            return []
        try:
            text = Path(archive_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        return [ln.strip() for ln in text.splitlines() if ln.strip()]

    @app.get("/archive")
    def get_archive(_mgr: JobManager = Depends(require_auth)):
        """What the download archive remembers (the v0.22 review's #7).

        It used to be a black box: once a video was in it, that video could
        never be downloaded again — not even after deleting the file. The
        list is bounded because an archive can hold tens of thousands of
        lines while the UI shows a page of them.
        """
        lines = _archive_lines()
        return {"path": str(archive_path) if archive_path else None,
                "count": len(lines), "entries": lines[-200:]}

    @app.post("/archive/forget")
    def forget_archive(body: ArchiveForgetRequest,
                       _mgr: JobManager = Depends(require_auth)):
        """Forget one archived entry so that video can be downloaded again."""
        entry = (body.entry or "").strip()
        if not entry:
            raise HTTPException(status_code=400, detail="nothing to forget")
        if not archive_path or not Path(archive_path).exists():
            raise HTTPException(status_code=404, detail="no archive yet")
        lines = _archive_lines()
        kept = [ln for ln in lines if ln != entry]
        removed = len(lines) - len(kept)
        if not removed:
            raise HTTPException(status_code=404,
                                detail="that entry is not in the archive")
        path = Path(archive_path)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text("\n".join(kept) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        return {"removed": removed}

    @app.post("/files/clear")
    def files_clear(body: FilesClearRequest | None = None,
                    mgr: JobManager = Depends(require_auth)):
        """Delete every downloaded file (sidecars included).

        This exists because on Android the download folder is app-private —
        a file manager cannot open Android/data, so the app has to offer the
        cleanup itself. Completed job rows go with their files; errored jobs
        stay so they can be retried.

        Destructive enough to need the word, not just a button: the UI already
        asks, and this makes the engine refuse a stray call too (the v0.21.1
        audit found a bare POST wiped the folder).

        Since v0.29.0 this does exactly what it says and no more: the app
        cache has its own endpoint (/cache/clear) and its own button — the
        v0.24.9 bundling made "delete" quietly do two things.
        """
        if (body.confirm if body else "") != "delete":
            raise HTTPException(
                status_code=400,
                detail='this deletes every downloaded file — send '
                       '{"confirm": "delete"} to proceed')
        active = [j for j in mgr.list()
                  if j["status"] in ("queued", "downloading", "merging")]
        if active:
            # unlinking a `.part` under a live worker makes yt-dlp die on the
            # final rename, and the download is lost for nothing (v0.21.2)
            raise HTTPException(
                status_code=409,
                detail=f"{len(active)} download(s) still running — "
                       "cancel them before clearing the folder")
        d = Path(manager.download_dir)
        deleted, freed = _wipe_dir(d)
        pruned = mgr.clear_completed()
        return {"deleted": deleted, "freed_bytes": freed,
                "cleared_jobs": pruned, "dir": str(d)}

    @app.post("/cache/clear")
    def cache_clear(body: FilesClearRequest | None = None,
                    _mgr: JobManager = Depends(require_auth)):
        """Free only the app cache — yt-dlp's player/signature data (v0.29.0).

        Nothing here is a download: yt-dlp re-fetches what it needs, so this
        is safe to run any time (and unlike /files/clear it never refuses for
        a running job — nothing it deletes can be a `.part` or a finished
        file). The one thing it will not do is run on a config mistake: a
        cache root that contains the download folder stands down, because
        wiping it would sweep the user's downloads as if they were cache.
        """
        if (body.confirm if body else "") != "delete":
            raise HTTPException(
                status_code=400,
                detail='this clears the app cache — send '
                       '{"confirm": "delete"} to proceed')
        if _cache_owns_downloads():
            return {"deleted": 0, "freed_bytes": 0, "dir": str(cache_dir),
                    "stood_down": True}
        deleted, freed = _wipe_dir(Path(cache_dir))
        return {"deleted": deleted, "freed_bytes": freed, "dir": str(cache_dir),
                "stood_down": False}

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

    @app.post("/jobs/{job_id}/pause")
    def pause_job(job_id: str, mgr: JobManager = Depends(require_auth)):
        """Stop a job and keep its partial file (v0.22.0 review #6)."""
        try:
            return redact_job(mgr.pause(job_id))
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from None

    @app.post("/jobs/{job_id}/resume")
    def resume_job(job_id: str, mgr: JobManager = Depends(require_auth)):
        try:
            return redact_job(mgr.resume(job_id))
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e)) from None

    @app.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str, body: RetryRequest | None = None,
                  mgr: JobManager = Depends(require_auth)):
        """Retry a failed job — optionally with edits (v0.22.0 review #11).

        A 403 or a missing format will fail the same way every time, so the
        body may carry {fmt, preset, overrides, raw_args} for the new attempt;
        anything it leaves out is reused from the original job.
        """
        patch = None
        if body is not None:
            raw = body.raw_args
            if raw is not None and not settings.get()["raw_args_enabled"]:
                raise HTTPException(
                    status_code=400,
                    detail="raw yt-dlp arguments are disabled in Settings → Advanced")
            if body.fmt and body.preset:
                raise HTTPException(
                    status_code=400,
                    detail="pass either 'preset' or 'fmt', not both")
            patch = {"fmt": body.fmt, "preset": body.preset,
                     "overrides": body.overrides, "raw_args": raw}
            patch = {k: v for k, v in patch.items() if v is not None}
            if "preset" in patch:
                # expand exactly like /jobs does: a preset is a named patch,
                # not a name to hand `create` raw. Before this, a bundle or
                # saved preset died as "unknown preset" and a preset->format
                # edit tripped create's "not both" refusal (v0.32.1 audit).
                try:
                    entry = presets.get(patch["preset"])
                except ValueError as e:
                    raise HTTPException(status_code=400, detail=str(e)) from None
                if entry is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"unknown preset: {patch['preset']!r}")
                intent, extra = split_patch(entry["patch"])
                patch["preset"] = intent
                merged = {**(body.overrides or {}), **extra}
                patch["overrides"] = merged or None
        try:
            return redact_job(mgr.retry(job_id, patch))
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

    def require_auth_media(
        token: str | None = None,
        creds: HTTPAuthorizationCredentials | None = Security(
            HTTPBearer(auto_error=False)),
    ):
        """Auth for the endpoint an HTML media element has to reach.

        `<video src=…>` cannot send an Authorization header, so the stream
        route also accepts the token as a query parameter: the same token the
        page already holds, over loopback, for the user's own file. Everything
        else keeps the header-only rule.
        """
        supplied = token or (creds.credentials if creds else "")
        if auth_token and (not supplied
                           or not secrets.compare_digest(supplied, auth_token)):
            raise HTTPException(status_code=401, detail="unauthorized")
        return manager

    @app.get("/files/list")
    def files_list(_mgr: JobManager = Depends(require_auth)):
        """What "open folder" shows: the folder's own files, newest first.

        A file manager can open Downloads on desktop; nothing can open
        Android/data on Android 11+, so the app lists the folder itself
        (2026-09-27 report: "Add the open folder button too").
        """
        root = Path(manager.download_dir)
        return {"dir": str(root), **_file_entries(root)}

    @app.get("/files/stream")
    def files_stream(request: Request, path: str = "",
                     mgr: JobManager = Depends(require_auth_media)):
        """Play one file from the download folder (the folder sheet's Play).

        The path is relative to the folder and must resolve inside it — the
        same guard the delete path uses, so neither the sheet nor a crafted
        URL becomes a way to read host files.
        """
        rel = (path or "").strip()
        if not rel or rel.startswith("/") or ".." in Path(rel).parts:
            raise HTTPException(status_code=404, detail="no such file")
        target = Path(manager.download_dir) / rel
        try:
            mgr._require_inside(target, None)       # noqa: SLF001
        except PermissionError:
            raise HTTPException(
                status_code=403,
                detail="that file is outside the download folder") from None
        if not target.is_file():
            raise HTTPException(status_code=404, detail="no such file")
        return _stream_file(target, request)

    @app.get("/jobs/{job_id}/stream")
    def stream_job(request: Request, job_id: str, name: str | None = None,
                   mgr: JobManager = Depends(require_auth_media)):
        """Play a finished download in the page (the v0.22 review's #10).

        `name` plays one entry of a playlist row by basename — the list the
        job recorded is the whitelist, so the parameter can never reach any
        other file (2026-09-27 report: playlist rows had no Play at all).
        """
        try:
            job = mgr.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="job not found") from None
        if job["status"] != "completed":
            raise HTTPException(status_code=409,
                                detail="this download is not finished")
        raw = job.get("filepath")
        path = Path(str(raw)) if raw else None
        if name:
            if "/" in name or "\\" in name or name.strip() in ("", ".", ".."):
                raise HTTPException(status_code=404, detail="no such file")
            match = next((str(f) for f in (job.get("files") or [])
                          if Path(str(f)).name == name), None)
            if not match:
                raise HTTPException(
                    status_code=404,
                    detail="no such file in this download") from None
            path = Path(match)
        if not path or path.is_dir() or not path.is_file():
            raise HTTPException(status_code=404,
                                detail="no playable file for this job")
        try:
            # the same guard the delete path uses: a job row is not a licence
            # to read arbitrary host files
            mgr._require_inside(path, job)          # noqa: SLF001
        except PermissionError:
            raise HTTPException(
                status_code=403,
                detail="that file is outside the download folder") from None
        return _stream_file(path, request)

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
