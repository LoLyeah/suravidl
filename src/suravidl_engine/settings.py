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
    "fragments": 1,              # concurrent fragment downloads (1-16)
    "proxy": "",                 # http(s)/socks URL
    "archive": False,            # skip URLs already in the download archive
    "sponsorblock_mode": "off",  # off | mark | remove
    "sponsorblock_categories": "sponsor, selfpromo",
}

THEMES = ("light", "dark", "amoled")
GLASS_STYLES = ("frosted", "liquid")


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
            self._data["max_concurrent"] = max(1, min(4, int(default_max_concurrent)))
        if self.path and self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                loaded = {}
            for k in DEFAULTS:
                if k in loaded and loaded[k] is not None:
                    self._data[k] = loaded[k]

    def get(self) -> dict:
        return dict(self._data)

    def update(self, patch: dict) -> dict:
        unknown = set(patch) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"unknown settings: {sorted(unknown)}")
        for key, value in patch.items():
            self._data[key] = self._validate(key, value)
        self._save()
        return self.get()

    @staticmethod
    def _validate(key: str, value):
        if key == "download_dir":
            path = Path(str(value)).expanduser()
            if not path.is_absolute():
                raise ValueError("download_dir must be an absolute path")
            return str(path)
        if key == "max_concurrent":
            return max(1, min(4, int(value)))
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
        if key in ("subtitles_auto", "embed_metadata", "embed_thumbnail", "archive"):
            return bool(value)
        if key == "rate_limit":
            from .download_opts import parse_rate_limit

            parse_rate_limit(str(value or ""))  # raises on junk
            return str(value or "").strip()
        if key == "fragments":
            return max(1, min(16, int(value)))
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
