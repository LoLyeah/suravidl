"""Named download presets: the built-in audio intents plus the user's own.

A preset is a named, validated patch (see settings.validate_preset_patch):
either an audio intent (`"preset": "audio-mp3"`), or any per-job options
(subtitles, SponsorBlock, embeds, template, raw args…), or both. Applying one
to a job is the same code path as a per-job override — one thing to get right.

User presets are data: `presets.json` next to settings.json, mode 0600.
Built-ins are code, so they cannot be deleted, only listed.
"""
import json
import os
from pathlib import Path

from .settings import validate_preset_patch

# name → patch. The audio intents existed before presets were a feature; they
# are expressed in the new shape so the UI has exactly one list to render.
BUILTIN_PRESETS: dict[str, dict] = {
    "audio-native": {"preset": "audio-native"},
    "audio-m4a": {"preset": "audio-m4a"},
    "audio-mp3": {"preset": "audio-mp3"},
    # v0.22.0 (feature review #9): 192k MP3 was the only "convert" path, and
    # the native Opus / lossless FLAC these sites actually serve had none.
    "audio-mp3-320": {"preset": "audio-mp3-320"},
    "audio-mp3-128": {"preset": "audio-mp3-128"},
    "audio-flac": {"preset": "audio-flac"},
    "audio-opus": {"preset": "audio-opus"},
    # v0.29.0: the video side — an MP4 compatibility intent, plus everyday
    # bundles that are pure patches (they may be edited into user presets).
    "video-mp4-1080": {"preset": "video-mp4-1080"},
    "video-mp4-720": {"preset": "video-mp4-720"},
    "subs-en-sidecar": {"subtitles_mode": "sidecar", "subtitles_langs": "en",
                        "subtitles_to_srt": True},
    "subs-en-embed": {"subtitles_mode": "embed", "subtitles_langs": "en"},
    "metadata-cover": {"embed_metadata": True, "embed_thumbnail": True},
}

BUILTIN_DESCRIPTIONS = {
    "audio-native": "keep the audio stream as the site serves it (no ffmpeg)",
    "audio-m4a": "extract the audio to m4a",
    "audio-mp3": "extract the audio to mp3 192k",
    "audio-mp3-320": "extract the audio to mp3 320k",
    "audio-mp3-128": "extract the audio to mp3 128k (small files)",
    "audio-flac": "extract the audio to flac (lossless)",
    "audio-opus": "extract the audio to opus (native, no generation loss)",
    "video-mp4-1080": "up to 1080p, MP4 (H.264 + AAC when the site has it) — opens anywhere",
    "video-mp4-720": "up to 720p, MP4 (H.264 + AAC when the site has it) — smaller files",
    "subs-en-sidecar": "English subtitles as .srt files next to the video",
    "subs-en-embed": "English subtitles embedded in the video",
    "metadata-cover": "embed title/artist metadata and the cover art",
}

MAX_NAME = 40


def normalize_name(name: str) -> str:
    """Preset names end up in URLs and in the UI: keep them boring."""
    name = str(name or "").strip()
    if not name:
        raise ValueError("a preset needs a name")
    if len(name) > MAX_NAME:
        raise ValueError(f"preset names are limited to {MAX_NAME} characters")
    if not all(c.isalnum() or c in " -_." for c in name):
        raise ValueError("preset names may use letters, digits, space, - _ .")
    return name


def split_patch(patch: dict) -> tuple[str | None, dict]:
    """(audio intent, per-job overrides) — what a job create needs."""
    patch = dict(patch or {})
    audio = patch.pop("preset", None)
    return audio, patch


class PresetStore:
    """User presets, persisted as one small JSON file."""

    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else None
        self._data: dict[str, dict] = {}
        if self.path and self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                loaded = {}
            if isinstance(loaded, dict):
                for name, patch in loaded.items():
                    try:  # a hand-edited file must not brick the engine
                        self._data[normalize_name(name)] = \
                            validate_preset_patch(patch)
                    except ValueError:
                        continue

    def list(self) -> list[dict]:
        out = [{"name": n, "patch": p, "builtin": True,
                "description": BUILTIN_DESCRIPTIONS.get(n, "")}
               for n, p in BUILTIN_PRESETS.items()]
        out += [{"name": n, "patch": p, "builtin": False, "description": ""}
                for n, p in sorted(self._data.items())]
        return out

    def get(self, name: str) -> dict | None:
        name = normalize_name(name)
        for entry in self.list():
            if entry["name"] == name:
                return entry
        return None

    def save(self, name: str, patch: dict) -> dict:
        name = normalize_name(name)
        if name in BUILTIN_PRESETS:
            raise ValueError(f"{name!r} is a built-in preset")
        self._data[name] = validate_preset_patch(patch)
        self._save()
        return {"name": name, "patch": self._data[name], "builtin": False,
                "description": ""}

    def delete(self, name: str) -> bool:
        name = normalize_name(name)
        if name in BUILTIN_PRESETS:
            raise ValueError(f"{name!r} is a built-in preset")
        if name not in self._data:
            return False
        del self._data[name]
        self._save()
        return True

    def _save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
