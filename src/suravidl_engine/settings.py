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
