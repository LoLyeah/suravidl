"""User-tunable settings, persisted as JSON next to the jobs db."""
import json
import os
from pathlib import Path

DEFAULTS = {
    "download_dir": None,
    "max_concurrent": 2,
    "open_dir_on_complete": False,
    "auto_resume": True,   # re-queue jobs cut off by an engine restart
    "theme": "dark",       # light | dark | amoled
    "glass": "frosted",    # frosted | liquid
    "cookies_file": "",          # Netscape cookies.txt for age-gated videos
    "cookies_from_browser": "",  # e.g. chrome / firefox / edge
    # --- tier-1 download options (see download_opts.py) -------------------
    "filename_template": "%(title).100B.%(ext)s",
    "subtitles_mode": "off",     # off | sidecar | embed
    "subtitles_langs": "en",     # comma list, e.g. "en, id" or "all"
    "subtitles_auto": False,     # include auto-generated captions
    "embed_metadata": False,
    "embed_thumbnail": False,
    "rate_limit": "",            # e.g. "2M" (bytes/s)
    "subfolders": "off",         # off | playlist | site — keep big batches tidy
    "video_container": "auto",   # auto | mp4 | mkv — remux for compatibility
    "live_from_start": False,    # live streams: record from the start when the
                                 # site still has it (yt-dlp --live-from-start)
    "download_sections": "",     # "" or a clip like "00:01:30-00:02:45"
    "subtitles_to_srt": False,   # TVs want .srt, not YouTube's .vtt
    "archive_ignore": False,     # this job only: download even if archived
    "fragments": 1,              # concurrent fragment downloads (1-16)
    "retries": 10,               # yt-dlp retries per download (0-30)
    "max_downloads": 0,          # stop after N downloads in a playlist (0 = all)
    "proxy": "",                 # http(s)/socks URL
    "archive": False,            # skip URLs already in the download archive
    "sponsorblock_mode": "off",  # off | mark | remove
    "sponsorblock_categories": "sponsor, selfpromo",
    # --- per-site memory (M20) -------------------------------------------
    "site_quality": {},          # {"youtube.com": "720"} — an offer, never a rule
    # advanced tier (raw yt-dlp arguments; default-OFF by design)
    "raw_args_enabled": False,
    "raw_args": "",              # e.g. "--no-mtime --extractor-args ..."
    # --- curated groups (the yt-dlp tab; see CURATED_KEYS) ----------------
    "verbose": False,            # keep yt-dlp's chatty log (debugging aid)
    "ip_version": "auto",        # auto | ipv4 | ipv6 (broken-IPv6 workaround)
    "no_check_certificates": False,
    "sleep_requests": 0,         # seconds between requests (0-30), be polite
    "geo_bypass": False,         # "not available in your country" bypass
    "geo_bypass_country": "",    # two-letter code, e.g. ID
    "extractor_args": "",        # e.g. youtube:player_client=web_safari
}

THEMES = ("light", "dark", "amoled")
GLASS_STYLES = ("frosted", "liquid")


def int_in(value, name: str, lo: int, hi: int) -> int:
    """An integer clamped to [lo, hi], with junk refused — never a crash.

    `int(float("inf"))` raises OverflowError and `int(float("nan"))` raises
    ValueError deep inside the endpoint, which the client sees as a 500. A
    number a user can type (or a JSON file can carry) deserves a clear refusal
    instead.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number") from None
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be a finite number") from None
    return max(lo, min(hi, int(number)))

# Keys a single download may override ("this download only"), and the ones that
# belong to the app itself: a job must not be able to move the download folder,
# change how many jobs run at once, or repaint the UI.
PER_JOB_DENIED = {
    "download_dir",      # the manager's folder, not a job's business
    "raw_args_enabled",  # the raw-args SWITCH is app-level: a job may not
                         # switch the escape hatch on for itself (v0.21.2
                         # audit). `raw_args` itself stays allowed — that is
                         # how the per-download arguments field works when the
                         # switch IS on — and it is inert while it is off.
    "max_concurrent",    # queue policy
    "open_dir_on_complete",
    "auto_resume",
    "theme",
    "glass",
    "site_quality",      # memory about you, not an option for this download
}
PER_JOB_KEYS = tuple(k for k in DEFAULTS if k not in PER_JOB_DENIED)

# A preset patch may additionally name the audio intent (built-in presets only).
PRESET_PATCH_KEYS = PER_JOB_KEYS + ("preset",)


def validate_overrides(patch: dict | None) -> dict:
    """Validate a per-job settings patch; ValueError on anything not allowed.

    Same validators as the settings screen, so a value that would be refused
    there is refused here too — and the whitelist stops the API from smuggling
    engine-owned keys (cookiefile, outtmpl, paths) into yt-dlp.
    """
    if not patch:
        return {}
    if not isinstance(patch, dict):
        raise ValueError("overrides must be an object")
    unknown = sorted(set(patch) - set(PER_JOB_KEYS))
    if unknown:
        raise ValueError(f"these options cannot be set per download: {unknown}")
    return {k: Settings._validate(k, v) for k, v in patch.items()}


def validate_preset_patch(patch: dict | None) -> dict:
    """A preset is a named patch: per-job keys plus an optional audio intent."""
    if not isinstance(patch, dict) or not patch:
        raise ValueError("a preset needs a patch with at least one option")
    unknown = sorted(set(patch) - set(PRESET_PATCH_KEYS))
    if unknown:
        raise ValueError(f"unknown preset options: {unknown}")
    out: dict = {}
    for k, v in patch.items():
        if k == "preset":
            from .jobs import preset_opts

            preset_opts(v)   # raises ValueError for anything but the built-ins
            out[k] = str(v)
        else:
            out[k] = Settings._validate(k, v)
    return out


class Settings:
    """Tiny validated key/value store. Unknown keys are rejected loudly."""

    def __init__(self, path: Path | str | None = None,
                 default_download_dir: str | Path | None = None,
                 default_max_concurrent: int | None = None):
        self.path = Path(path) if path else None
        self._data = dict(DEFAULTS)
        if default_download_dir is not None:
            self._data["download_dir"] = str(Path(default_download_dir))
        if default_max_concurrent is not None:
            self._data["max_concurrent"] = int_in(default_max_concurrent,
                                                  "max_concurrent", 1, 4)
        if self.path and self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                loaded = {}
            for k in DEFAULTS:
                if k not in loaded or loaded[k] is None:
                    continue
                # Validate what we load: a hand-edited or half-written file
                # used to reach the engine unchecked, and one bad value
                # (an uncreatable download_dir, `"nan"` for max_concurrent)
                # then killed every start (v0.21.2 audit). A key that does
                # not validate keeps its default instead of taking the app
                # down.
                try:
                    self._data[k] = self._validate(k, loaded[k])
                except (ValueError, OSError, TypeError):
                    continue

    def get(self) -> dict:
        return dict(self._data)

    def update(self, patch: dict) -> dict:
        unknown = set(patch) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"unknown settings: {sorted(unknown)}")
        # validate EVERYTHING before touching memory: a patch with one good and
        # one bad key used to leave the good half applied in RAM while the file
        # on disk kept the old value (v0.21.2 audit)
        clean = {key: self._validate(key, value) for key, value in patch.items()}
        previous = dict(self._data)
        self._data.update(clean)
        try:
            self._save()
        except OSError:
            self._data = previous       # never leave a half-applied change
            raise
        return self.get()

    @staticmethod
    def _validate(key: str, value):
        if key == "download_dir":
            path = Path(str(value)).expanduser()
            if not path.is_absolute():
                raise ValueError("download_dir must be an absolute path")
            # Prove we can actually write there BEFORE saving it: a folder
            # that cannot be created used to be persisted anyway, and the
            # next start died in mkdir — every start, forever (v0.21.2 audit)
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                raise ValueError(
                    f"download folder cannot be used: {path} ({e.strerror or e})")
            if not path.is_dir():
                raise ValueError(f"download folder is not a folder: {path}")
            return str(path)
        if key == "max_concurrent":
            return int_in(value, "max_concurrent", 1, 4)
        if key == "open_dir_on_complete":
            return bool(value)
        if key == "auto_resume":
            return bool(value)
        if key == "cookies_file":
            value = str(value or "").strip()
            if value:
                p = Path(value).expanduser()
                if not p.is_file():
                    raise ValueError(f"cookies file not found: {p}")
                value = str(p)
            return value
        if key == "cookies_from_browser":
            value = str(value or "").strip()
            if value:
                from .auth import parse_browser

                parse_browser(value)  # raises ValueError with the known list
            return value
        if key == "theme":
            value = str(value)
            if value not in THEMES:
                raise ValueError(f"theme must be one of {THEMES}")
            return value
        if key == "glass":
            value = str(value)
            if value not in GLASS_STYLES:
                raise ValueError(f"glass must be one of {GLASS_STYLES}")
            return value
        # -- tier-1 download options -----------------------------------------
        if key == "filename_template":
            from .download_opts import validate_template

            return validate_template(str(value or ""))
        if key == "subfolders":
            from .download_opts import SUBFOLDER_MODES

            v = str(value or "off").strip().lower() or "off"
            if v not in SUBFOLDER_MODES:
                raise ValueError(f"subfolders must be one of {list(SUBFOLDER_MODES)}")
            return v
        if key == "video_container":
            from .download_opts import CONTAINERS

            v = str(value or "auto").strip().lower() or "auto"
            if v not in CONTAINERS:
                raise ValueError(f"video_container must be one of {list(CONTAINERS)}")
            return v
        if key == "download_sections":
            from .download_opts import parse_sections

            text = str(value or "").strip()
            if not text:
                return ""
            start, end = parse_sections(text)
            return f"*{start}-{end}"
        if key == "subtitles_mode":
            from .download_opts import SUBTITLE_MODES

            value = str(value)
            if value not in SUBTITLE_MODES:
                raise ValueError(f"subtitles_mode must be one of {SUBTITLE_MODES}")
            return value
        if key == "subtitles_langs":
            value = str(value or "").strip()
            if any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789,._-* " for c in value):
                raise ValueError("subtitles_langs must be a comma list of language codes")
            return value
        if key in ("subtitles_auto", "embed_metadata", "embed_thumbnail", "archive",
                   "subtitles_to_srt", "archive_ignore", "live_from_start"):
            return bool(value)
        if key == "rate_limit":
            from .download_opts import parse_rate_limit

            parse_rate_limit(str(value or ""))  # raises on junk
            return str(value or "").strip()
        if key == "fragments":
            return int_in(value, "fragments", 1, 16)
        if key == "retries":
            return int_in(value, "retries", 0, 30)
        if key == "max_downloads":
            return int_in(value, "max_downloads", 0, 1000)
        if key == "proxy":
            from .download_opts import validate_proxy

            return validate_proxy(str(value or ""))
        if key == "sponsorblock_mode":
            from .download_opts import SPONSORBLOCK_MODES

            value = str(value)
            if value not in SPONSORBLOCK_MODES:
                raise ValueError(f"sponsorblock_mode must be one of {SPONSORBLOCK_MODES}")
            return value
        if key == "sponsorblock_categories":
            from .download_opts import validate_sponsorblock_categories

            return validate_sponsorblock_categories(str(value or ""))
        if key == "raw_args_enabled":
            return bool(value)
        if key == "raw_args":
            from .download_opts import parse_raw_args

            value = str(value or "").strip()
            if len(value) > 1000:
                raise ValueError("raw_args is too long (max 1000 characters)")
            parse_raw_args(value)  # raises ValueError on flags yt-dlp rejects
            return value
        # -- curated groups (the yt-dlp tab) ---------------------------------
        if key in ("verbose", "no_check_certificates", "geo_bypass"):
            return bool(value)
        if key == "ip_version":
            from .download_opts import IP_VERSIONS

            value = str(value)
            if value not in IP_VERSIONS:
                raise ValueError(f"ip_version must be one of {IP_VERSIONS}")
            return value
        if key == "sleep_requests":
            from .download_opts import SLEEP_REQUESTS_MAX

            try:
                seconds = float(value)
            except (TypeError, ValueError):
                raise ValueError("sleep_requests must be a number of seconds") from None
            if seconds != seconds or seconds in (float("inf"), float("-inf")):
                raise ValueError("sleep_requests must be a finite number") from None
            if not 0 <= seconds <= SLEEP_REQUESTS_MAX:
                raise ValueError(
                    f"sleep_requests must be between 0 and {SLEEP_REQUESTS_MAX:g} seconds")
            return seconds
        if key == "geo_bypass_country":
            value = str(value or "").strip().upper()
            if value and (len(value) != 2 or not value.isalpha()):
                raise ValueError("geo_bypass_country must be a two-letter code (e.g. ID)")
            return value
        if key == "extractor_args":
            from .download_opts import parse_extractor_args

            value = str(value or "").strip()
            if len(value) > 300:
                raise ValueError("extractor_args is too long (max 300 characters)")
            parse_extractor_args(value)
            return value
        if key == "site_quality":
            from .site_memory import clean

            return clean(value)
        raise ValueError(f"unknown setting: {key}")

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2),
                             encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)  # holds cookie paths & prefs, not public
        except OSError:
            pass
