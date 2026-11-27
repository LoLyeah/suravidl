// The page side of the sniffer (v0.5.13) — the layer the phone's in-app
// browser has always had: read the PLAYER itself, not just the network.
//
// Why it exists: the network listeners see what the page requests. A
// <video>/<source> the player has not asked for yet (preload="none", a
// pre-roll gate), and any stream served from a URL with no extension at
// all, are invisible there — and a miss on the second costs the user a
// video (mp4-06.overfetch.video served one with no extension, on another
// host). What the player points at is evidence, the same doctrine
// docs/SNIFFING.md states for the phone.
//
// It runs in the content script's isolated world: the page cannot see it,
// cannot call it, and can therefore never forge a find; unlike the phone's
// MAIN-world hooks (a WebView has no isolated world to stand in), nothing
// here is exposed to the page. Blob/MSE sources are deliberately NOT
// reported — they prove the player is streaming, not what to download.
(() => {
  const api = (typeof browser !== "undefined" && browser) || chrome;
  const MEDIA_TAGS = "video, audio, source";
  const seen = new Set();
  let MEDIA_RE = null;   // the engine's pattern list, read once; scan-only

  function report(raw, via) {
    try {
      if (!raw || typeof raw !== "string") return;
      if (/^(blob|data|mse):/i.test(raw)) return;   // proof of streaming, not a URL to fetch
      let u;
      try { u = new URL(raw, location.href).href; } catch (_) { return; }
      if (!/^https?:/i.test(u)) return;
      if (seen.has(u)) return;
      seen.add(u);
      api.runtime.sendMessage({ type: "pageFind", url: u, via });
    } catch (_) { /* a sniffer must never break the page */ }
  }

  // A blob:/MediaSource source is a marker, not a URL (v0.5.31): it proves the
  // player is fed by JavaScript, which is exactly the case where a network
  // sniffer sees fragments and slices instead of a file. The phone's browser
  // has always reported this; the desktop shell now says it too, so the popup
  // can point at the page door instead of "nothing playing".
  let mseSaid = false;
  function reportMse() {
    if (mseSaid) return;
    mseSaid = true;
    try { api.runtime.sendMessage({ type: "pageMse" }); } catch (_) {}
  }

  let posterLast = "";
  function reportPoster(raw) {
    try {
      if (!raw || typeof raw !== "string") return;
      let u;
      try { u = new URL(raw, location.href).href; } catch (_) { return; }
      if (!/^https?:/i.test(u) || u === posterLast) return;
      posterLast = u;
      api.runtime.sendMessage({ type: "pagePoster", url: u });
    } catch (_) { /* a sniffer must never break the page */ }
  }

  // The decode key of a scrambled-playlist player (v0.5.16): Chrome reads
  // it in the MAIN world (pk.js posts it here); Firefox's MV2 content
  // scripts read page globals directly via wrappedJSObject — one door per
  // engine, the same forwarding. The engine validates the key against the
  // stream itself, so a forged one fails the decode and nothing else.
  let pkLast = null;
  function reportPk(pk) {
    if (typeof pk !== "string" || pk.length < 16 || pk.length > 512
        || pk === pkLast) return;
    pkLast = pk;
    try { api.runtime.sendMessage({ type: "pkFind", pk }); } catch (_) {}
  }
  try {
    addEventListener("message", (e) => {
      if (e.source !== window || !e.data || typeof e.data !== "object") return;
      reportPk(e.data.__svPk);
    });
  } catch (_) {}
  function readWrapped() {
    try {
      const w = window.wrappedJSObject;
      if (w && typeof w.__pk === "string") reportPk(w.__pk);
    } catch (_) {}
  }
  readWrapped();
  try {
    // Firefox's door; a no-op elsewhere. Bounded and unref'd so a Node
    // harness that evaluates this file can still exit (browsers have no
    // unref — the guard keeps it honest there too).
    let pkTicks = 0;
    const pkTimer = setInterval(() => {
      readWrapped();
      if (++pkTicks > 150) clearInterval(pkTimer);   // ~5 minutes of looking
    }, 2000);
    if (pkTimer && pkTimer.unref) pkTimer.unref();
  } catch (_) {}

  // The player's own sources. `currentSrc` first — the source actually
  // chosen — then the attribute. No pattern prefilter: this is evidence.
  function sweep() {
    try {
      let videoCount = 0;
      let singlePoster = "";
      for (const el of document.querySelectorAll(MEDIA_TAGS)) {
        const s = el.currentSrc || el.src;
        if (s && /^(blob|mediasource):/i.test(s)) reportMse();
        else if (s) report(s, "player");
        // the player's poster is a picture of what is playing, and the only
        // one available when the stream is HLS — but only when there is ONE
        // video on the page: on a feed the last swept element is an ad or a
        // hover preview, and that picture is not this list's (v0.5.29)
        if (el.tagName && el.tagName.toLowerCase() === "video") {
          videoCount += 1;
          if (videoCount === 1 && el.poster) singlePoster = el.poster;
        }
      }
      if (videoCount === 1 && singlePoster) reportPoster(singlePoster);
    } catch (_) {}
  }

  // What the page already loaded before this script ran (an extension that
  // was just reloaded, a player that started in a very early inline
  // script): the performance timeline keeps the receipts. Patterns keep
  // the network noise out here — the timeline has everything.
  const scannedKeys = new Set();
  function scan() {
    try {
      const es = performance.getEntriesByType ? performance.getEntriesByType("resource") : [];
      // position cannot be the bookmark: the timeline's buffer drops its
      // oldest entries when it fills, so indexes shift left underneath us
      // and an index past the end would skip the newest finds. A name plus
      // startTime is stable, and startTime only moves forward.
      for (const e of es) {
        const u = (e && e.name) || "";
        if (!u) continue;
        const at = e.startTime || 0;
        const key = u + "\u0000" + at;
        if (scannedKeys.has(key)) continue;
        if (scannedKeys.size > 2000) scannedKeys.clear();
        scannedKeys.add(key);
        if (e.initiatorType === "video" || e.initiatorType === "audio") {
          report(u, "player");           // the player requested it: evidence
        } else if (MEDIA_RE && MEDIA_RE.test(u.split("#")[0])) {
          report(u, "scan");
        }
      }
    } catch (_) {}
  }

  let soon = null;
  function scheduleSweep(records) {
    if (soon) return;
    if (Array.isArray(records)) {
      let hasEl = false;
      for (const r of records) {
        if (!r || !r.addedNodes) continue;
        for (const n of r.addedNodes) {
          if (n && n.nodeType === 1) { hasEl = true; break; }
        }
        if (hasEl) break;
      }
      if (!hasEl) return;
    }
    try {
      soon = setTimeout(() => { soon = null; sweep(); }, 250);
    } catch (_) { sweep(); }
  }

  try {
    api.storage.local.get({ patterns: null }).then((stored) => {
      const ex = (stored && stored.patterns) || [];
      if (ex.length) {
        try { MEDIA_RE = new RegExp("\\.(" + ex.join("|") + ")(\\?|$)", "i"); } catch (_) {}
      }
      scan();
    }).catch(() => {});
  } catch (_) {}

  sweep();
  try {
    new MutationObserver(scheduleSweep)
      .observe(document.documentElement || document, { childList: true, subtree: true });
  } catch (_) {}
  try {
    addEventListener("load", () => { sweep(); scan(); });
  } catch (_) {}
})();
