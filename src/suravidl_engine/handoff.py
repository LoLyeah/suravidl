"""Browser handoffs: the extension's find becomes a probe the user finishes.

The popup hands over what a page was playing; the engine probes it *here*,
with the captured request headers, and holds the result until a suravidl
window picks it up. So the quality choice happens in the app (where the
formats are real), the extension stays a doorman, and captured cookies never
leave the engine: reads never include headers, and a job started from a
handoff reuses them server-side (`handoff_id` on POST /jobs).
"""
from __future__ import annotations

import threading
import time
import uuid

from .probe import scrub_secrets

TTL_S = 30 * 60        # one nobody opened in half an hour is stale
MAX_KEPT = 5           # the newest handoffs; older ones roll off
DEDUPE_S = 30          # the same stream clicked twice is one handoff
CANDIDATES_TRIED = 3   # a probe that fails falls through to its siblings
MAX_PROBING = 3        # handoffs arrive in bursts; probes are heavy (v0.40.10)


class HandoffStore:
    """In-memory by design: a handoff only exists while an engine is up."""

    def __init__(self, probe_fn, now=time.time):
        self._probe_fn = probe_fn
        self._now = now
        self._lock = threading.Lock()
        self._items: dict[str, dict] = {}
        self._probes = threading.BoundedSemaphore(MAX_PROBING)

    # -- writes ----------------------------------------------------------
    def add(self, url, urls=None, headers=None, tab_url=None) -> dict:
        now = self._now()
        with self._lock:
            self._expire(now)
            for it in self._items.values():
                if it["url"] == url and now - it["at"] < DEDUPE_S:
                    return self._public(it)
            item = {
                "id": uuid.uuid4().hex[:12],
                "url": url,
                "urls": [u for u in (urls or []) if u][:20],
                "headers": dict(headers or {}),
                "tab_url": tab_url or "",
                "at": now,
                "status": "probing",
                "probe": None,
                "resolved_url": url,
                "error": None,
            }
            self._items[item["id"]] = item
            while len(self._items) > MAX_KEPT:
                oldest = min(self._items.values(), key=lambda i: i["at"])
                del self._items[oldest["id"]]
        threading.Thread(target=self._run, args=(item["id"],),
                         daemon=True).start()
        return self._public(item)

    def ack(self, hid: str) -> bool:
        with self._lock:
            return self._items.pop(hid, None) is not None

    def headers_for(self, hid: str) -> dict | None:
        with self._lock:
            it = self._items.get(hid)
            return dict(it["headers"]) if it else None

    # -- reads -----------------------------------------------------------
    def list(self) -> list:
        now = self._now()
        with self._lock:
            self._expire(now)
            return [self._public(i) for i in
                    sorted(self._items.values(), key=lambda i: -i["at"])]

    @staticmethod
    def _public(item: dict) -> dict:
        """Everything but the headers — cookies never travel to a reader."""
        out = {k: v for k, v in item.items() if k != "headers"}
        out["has_headers"] = bool(item["headers"])
        return out

    # -- internals -------------------------------------------------------
    def _expire(self, now) -> None:
        for hid in [k for k, v in self._items.items() if now - v["at"] > TTL_S]:
            del self._items[hid]

    def _run(self, hid: str) -> None:
        # burst control: a multi-select handoff must not start a dozen heavy
        # probes at once (v0.40.10 audit)
        with self._probes:
            self._probe(hid)

    def _probe(self, hid: str) -> None:
        with self._lock:
            item = self._items.get(hid)
            if not item:
                return
            headers = dict(item["headers"])
            candidates = list(dict.fromkeys([item["url"]] + item["urls"]))[:CANDIDATES_TRIED]
        probe, resolved, error = None, candidates[0], None
        for cand in candidates:
            try:
                probe = self._probe_fn(cand, headers)
                resolved, error = cand, None
                break
            except Exception as e:  # noqa: BLE001 - becomes the handoff's state
                error = str(e)
        with self._lock:
            item = self._items.get(hid)
            if not item:
                return
            if probe is not None:
                # whatever the probe path was, a readable handoff carries no
                # request secrets (yt-dlp embeds them; see probe.scrub_secrets)
                item.update(status="ready", probe=scrub_secrets(probe),
                            resolved_url=resolved, error=None)
            else:
                item.update(status="failed", error=error or "probe failed")
