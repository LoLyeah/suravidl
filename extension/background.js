// suravidl extension background (MV3 service worker / Firefox background page).
// Detects media per tab, captures the request headers yt-dlp needs
// (Cookie / User-Agent / Referer), badges the count, hands off to the engine.
//
// The media-pattern list is the engine's (`GET /sniff/patterns`), fetched once a
// day; the fallback below stands when it is not answering. A test keeps that
// fallback a subset of the engine's list, so a shell can only ever look at
// *fewer* URLs than the engine can name — never at shapes it cannot.
//
// A response that *says* video/* is remembered even when its URL matched
// nothing: a stream whose name lies is exactly the one yt-dlp would never hear
// about. Type-only, so this still never touches ordinary browsing (v0.21.2).
const FALLBACK_EXT = ["mp4", "m4v", "webm", "mov", "mkv", "avi", "flv", "wmv",
  "ogv", "m3u8", "mpd", "ts", "m4s", "mp3", "m4a", "aac", "ogg", "opus", "wav",
  "flac"];
const MEDIA_TYPES =
  /^(video\/|audio\/|application\/vnd\.apple\.mpegurl|application\/x-mpegurl|application\/mpegurl|application\/dash\+xml)/i;
// A feed preloads several videos at once, so one screen can put twenty URLs on
// the wire; a cap that tight dropped the video being watched while keeping the
// ones queued after it. Keep a scroll's worth, and let age be the real limit.
const KEEP_PER_TAB = 60;
const KEEP_MS = 20 * 60 * 1000;
const HEADER_KEEP = 100;
const PENDING_KEEP = 200;
const action = chrome.action || chrome.browserAction; // MV3 vs Firefox MV2

// Firefox's `chrome` namespace is a callback-only shim: called without a
// callback, `chrome.storage.local.get(...)` returns undefined there, not a
// promise, so every `await` on it would read nothing (measured on Firefox
// 157 — the `browser` namespace returns promises, and Chrome's `chrome.*`
// does too; ask whichever answers, v0.5.3).
const api = globalThis.browser || chrome;

function buildRe(ext) {
  return new RegExp("\\.(" + ext.join("|") + ")(\\?|$)", "i");
}
let MEDIA_RE = buildRe(FALLBACK_EXT);

function prune(reqHeaders) {
  const entries = Object.entries(reqHeaders).slice(-HEADER_KEEP);
  return Object.fromEntries(entries);
}

// The page's decode key for scrambled playlists (v0.5.16): like the header
// store, it is session material — a key older than half an hour belongs to a
// stream that already expired with it.
const PK_TTL_MS = 30 * 60 * 1000;

function prunePk(tabPk) {
  const now = Date.now();
  const entries = Object.entries(tabPk || {})
    .filter(([, v]) => v && now - (v.at || 0) < PK_TTL_MS)
    .slice(-30);
  return Object.fromEntries(entries);
}

// Storage is read-modify-write, and three media requests can land in the same
// tick — a player asks for its manifest and its first fragments together. So
// every write is chained: without it the last writer wins and finds disappear
// (found the hard way, by the Node harness in extension/test_harness.mjs).
let storageChain = Promise.resolve();
function update(mutate) {
  storageChain = storageChain
    .then(() => new Promise((resolve) => {
      chrome.storage.local.get({ tabMedia: {}, reqHeaders: {}, shareMap: {}, tabPk: {}, tabPoster: {} }, (data) => {
        chrome.storage.local.set(mutate(data) || {}, resolve);
      });
    }))
    .catch(() => {});
  return storageChain;
}

// What a response says about itself: its type, and the size a person can
// compare. On a 206 the Content-Length is the chunk the player asked for —
// the real file size is the range's total, so read that first (v0.5.20).
function responseMeta(responseHeaders) {
  let mime = "", len = 0, total = 0;
  for (const h of responseHeaders || []) {
    const name = (h && h.name ? h.name : "").toLowerCase();
    const value = String((h && h.value) == null ? "" : h.value);
    if (name === "content-type") mime = value.split(";")[0].trim().toLowerCase();
    else if (name === "content-length") len = parseInt(value, 10) || 0;
    else if (name === "content-range") {
      const m = /\/(\d+)\s*$/.exec(value);
      if (m) total = parseInt(m[1], 10) || 0;
    }
  }
  return { mime, bytes: total || len };
}

// A fragmented MP4 served in slices — Facebook's reel player does this — is
// one file asked for many times: the player appends `bytestart` and `byteend`
// to a signed address, and the CDN answers each slice with 200 and the
// slice's own length, never a Content-Range. The signature covers the address
// without those two params, so they come off exactly and every slice lands on
// the same find instead of twenty (v0.5.21).
function canonicalMediaUrl(raw) {
  const text = String(raw || "");
  const q = text.indexOf("?");
  if (q < 0) return { url: raw, sliced: false };
  const hash = text.indexOf("#", q);
  const head = text.slice(0, q);
  const query = text.slice(q + 1, hash < 0 ? undefined : hash);
  const tail = hash < 0 ? "" : text.slice(hash);
  const parts = query.split("&");
  const kept = parts.filter((p) => !/^(?:bytestart|byteend)=/.test(p));
  if (kept.length === parts.length) return { url: raw, sliced: false };
  // Every other byte of the query stays as the page sent it: the signature
  // is over this string, and re-serialising (which would turn a value's
  // "=" into %3D) is exactly how a signed URL starts answering 403.
  const rest = kept.filter((p) => p !== "").join("&");
  return { url: head + (rest ? "?" + rest : "") + tail, sliced: true };
}

// The `efg` parameter is base64url of the player's own description of the
// track it is about to fetch. Its tag is the one place an audio-only file
// admits it: the CDN types it video/mp4 exactly like the picture, and a row
// called "Video" for a soundtrack had a person download silence (v0.5.21).
function efgBlob(raw) {
  try {
    const efg = new URL(raw).searchParams.get("efg");
    if (!efg) return null;
    const b64 = efg.replace(/-/g, "+").replace(/_/g, "/");
    const text = atob(b64 + "===".slice((b64.length + 3) % 4));
    return JSON.parse(text) || null;
  } catch (_) {
    return null;   // a payload we cannot read claims nothing
  }
}

// The parent asset id: equal on a reel's picture and its soundtrack, which
// is the only key that survives them being served from different edge hosts
// (Gemini 4 Carbon, 2026-11-12: the CDN shards per representation object).
function efgAsset(raw) {
  const blob = efgBlob(raw);
  if (!blob) return "";
  const id = blob.xpv_asset_id || blob.video_id || blob.asset_id;
  return id == null ? "" : String(id);
}

function efgKind(raw) {
  try {
    const blob = efgBlob(raw);
    if (!blob) return "";
    // the tag is the player's own answer; the other strings are a fallback
    // for a payload shaped differently, never a second opinion on a real tag
    const tag = typeof blob.vencode_tag === "string" ? blob.vencode_tag.toLowerCase() : "";
    const words = tag || Object.keys(blob).map((k) => blob[k])
      .filter((v) => typeof v === "string")
      .join(" ")
      .toLowerCase();
    if (/audio|heaac/.test(words)) return "audio";
    if (/dash_|progressive|video/.test(words)) return "video";
  } catch (_) { /* a payload we cannot read claims nothing */ }
  return "";
}

// What a response can honestly say about an audio track the CDN typed as
// video: the efg tag corrects the name, and nothing else about it changes.
function efgMime(raw, mime) {
  return efgKind(raw) === "audio" && (!mime || /^video\//.test(mime))
    ? "audio/mp4" : mime;
}

// The same fragment reports its headers over and over during one playback,
// and every remember() is a storage read-modify-write. Only a changed answer
// is worth a write (v0.5.20).
const META_SEEN = new Map();

function learnMeta(tabId, rawUrl, meta) {
  // A slice's Content-Length is the chunk the player asked for, never the
  // file: zero means unknown, which the row says, and the probe below fills
  // the real size in once (v0.5.21). The efg tag can still correct the type,
  // because a soundtrack is served as video/mp4 like the picture.
  const sliced = canonicalMediaUrl(rawUrl).sliced;
  const learned = { mime: efgMime(rawUrl, meta.mime), bytes: sliced ? 0 : meta.bytes };
  if (!learned.mime && !learned.bytes) return;
  const key = learned.mime + "|" + learned.bytes;
  if (META_SEEN.get(rawUrl) === key) return;
  if (META_SEEN.size > 400) META_SEEN.clear();
  META_SEEN.set(rawUrl, key);
  remember(tabId, rawUrl, "network", learned);
}

// One question per address, asked once: how big is the file? A HEAD is the
// cheap answer; a CDN that refuses HEAD still answers a one-byte range with
// the total in Content-Range. Failure is silence — a probe that cannot read
// the size leaves it unknown, which the row already says (v0.5.21).
const PROBED = new Set();
const PROBE_LIVE_MAX = 8;
let probeLive = 0;

function headerValue(res, name) {
  try {
    const h = res && res.headers;
    return h && typeof h.get === "function" ? String(h.get(name) || "") : "";
  } catch (_) {
    return "";
  }
}

function probeSignal() {
  // A browser without AbortSignal.timeout probes without a deadline rather
  // than not at all; the call never throws either way.
  try { return AbortSignal.timeout(6000); } catch (_) { return undefined; }
}

function learnProbe(url, bytes, mime) {
  const audio = efgKind(url) === "audio";
  update(({ tabMedia }) => {
    let changed = false;
    for (const list of Object.values(tabMedia || {})) {
      for (const m of list || []) {
        if (m.url !== url) continue;
        const size = Math.max(bytes, m.bytes || 0);
        // the efg tag outranks the CDN's type: an audio track is served as
        // video/mp4, and the probe must not name it back to a video. A type
        // that is not media at all (octet-stream on a HEAD) is no answer, so
        // the type the response already taught the find stands.
        const type = audio && /^video\//.test(mime || "")
          ? "audio/mp4"
          : (MEDIA_TYPES.test(mime || "") ? mime : (m.mime || ""));
        if (size !== m.bytes || type !== m.mime) {
          m.bytes = size;
          m.mime = type;
          changed = true;
        }
      }
    }
    return changed ? { tabMedia } : {};
  });
}

async function probeSize(url, sliceUrl) {
  if (!url || PROBED.has(url) || probeLive >= PROBE_LIVE_MAX) return;
  if (PROBED.size > 500) PROBED.clear();
  PROBED.add(url);
  probeLive += 1;
  try {
    const stored = await api.storage.local.get({ reqHeaders: {} });
    // the alias commitHeaders keeps is the usual home; the slice's own entry
    // answers when the request came from a frame that stored nothing else
    const cap = stored.reqHeaders[url] || stored.reqHeaders[sliceUrl] || {};
    const referer = cap.headers && cap.headers.referer;
    const init = () => {
      const opts = { credentials: "include", cache: "no-store", signal: probeSignal() };
      if (referer) opts.referrer = referer;
      return opts;
    };
    let bytes = 0, mime = "";
    try {
      const res = await fetch(url, Object.assign(init(), { method: "HEAD" }));
      if (res && res.ok) {
        bytes = parseInt(headerValue(res, "content-length"), 10) || 0;
        mime = headerValue(res, "content-type").split(";")[0].trim().toLowerCase();
      }
    } catch (_) { /* a refused HEAD is not an answer */ }
    if (!bytes) {
      try {
        const res = await fetch(url, Object.assign(init(), {
          headers: { Range: "bytes=0-0" },
        }));
        if (res && (res.ok || res.status === 206)) {
          const total = /\/(\d+)\s*$/.exec(headerValue(res, "content-range"));
          if (total) bytes = parseInt(total[1], 10) || 0;
        }
      } catch (_) { /* no range answer either: the size stays unknown */ }
    }
    if (bytes > 0) learnProbe(url, bytes, mime);
  } finally {
    probeLive -= 1;
  }
}

function remember(tabId, rawUrl, via, meta) {
  const canon = canonicalMediaUrl(rawUrl);
  const url = canon.url;
  const done = update(({ tabMedia, reqHeaders }) => {
    const list = tabMedia[tabId] || [];
    const at = list.findIndex((m) => m.url === url);
    let added = false;
    if (at >= 0) {
      // seen again, this time with its response: the find learns what it is
      // and how big it is, and keeps its place (and its foundAt) in the list.
      // A later 206 must not shrink a known size back to one chunk.
      const cur = list[at];
      // the first slice is the address the player itself used: the engine
      // gets it as a fallback if the canonical one is refused (v0.5.21)
      const alt = cur.alt || (canon.sliced ? rawUrl : "");
      if (!meta) {
        if (alt === (cur.alt || "")) return { tabMedia };
        list[at] = Object.assign({}, cur, { alt });
        return { tabMedia };
      }
      const mime = meta.mime || cur.mime || "";
      const bytes = Math.max(meta.bytes || 0, cur.bytes || 0);
      const asset = cur.asset || efgAsset(rawUrl) || "";
      if (mime === cur.mime && bytes === cur.bytes && alt === (cur.alt || "") &&
          asset === (cur.asset || "")) {
        return { tabMedia };
      }
      list[at] = Object.assign({}, cur, { mime, bytes, alt, asset });
    } else {
      list.push({
        url, foundAt: Date.now(), via: via || "network",
        mime: (meta && meta.mime) || "", bytes: (meta && meta.bytes) || 0,
        alt: canon.sliced ? rawUrl : "",
        asset: efgAsset(rawUrl) || "",
      });
      const now = Date.now();
      tabMedia[tabId] = list
        .filter((m) => now - (m.foundAt || 0) < KEEP_MS)
        .slice(-KEEP_PER_TAB);
      added = true;
    }
    if (added && action && action.setBadgeText) {
      action.setBadgeText({ tabId, text: String(tabMedia[tabId].length) });
    }
    return added ? { tabMedia, reqHeaders: prune(reqHeaders) } : { tabMedia };
  });
  // After the write, so the answer finds the find it belongs to; the probe's
  // own guard keeps every later slice of the same address from asking again.
  // A probe that rejects (a worker being torn down) must not become an
  // unhandled rejection in the service worker.
  if (canon.sliced) done.then(() => probeSize(url, rawUrl).catch(() => {}));
  return done;
}

function loadPatterns() {
  chrome.storage.local.get(
    { engineUrl: "http://127.0.0.1:8787", engineToken: "", patternsAt: 0, patterns: null },
    async (stored) => {
      // MV3 workers are ephemeral: the in-memory regex dies with every restart,
      // so the cached list has to come back out of storage *before* the day-long
      // timer is trusted. Without this, every wake-up silently fell back to the
      // baked-in list for 24 h (found by the Antigravity audit).
      if (Array.isArray(stored.patterns) && stored.patterns.length) {
        MEDIA_RE = buildRe(stored.patterns);
      }
      if (Date.now() - stored.patternsAt < 24 * 3600 * 1000) return;
      try {
        const eng = await resolveEngine();
        if (!eng.ok) return;
        const res = await fetch(eng.base + "/sniff/patterns", {
          headers: { Authorization: "Bearer " + stored.engineToken },
        });
        if (!res.ok) return;
        const body = await res.json();
        if (Array.isArray(body.ext) && body.ext.length) {
          MEDIA_RE = buildRe(body.ext);
          chrome.storage.local.set({ patternsAt: Date.now(), patterns: body.ext });
        }
      } catch (e) {
        /* the engine is not up yet — the fallback list stands */
      }
    }
  );
}

// The headers yt-dlp needs for auth'd sites (Cookie/UA/Referer/Origin), picked
// from a request and nothing else.
function pickHeaders(reqHeaders) {
  const pick = {};
  for (const h of reqHeaders || []) {
    const k = (h.name || "").toLowerCase();
    if (["cookie", "user-agent", "referer", "origin"].includes(k) && h.value) {
      pick[k] = h.value;
    }
  }
  return Object.keys(pick).length ? pick : null;
}

// Headers for requests that have not proved themselves yet. A stream whose URL
// says nothing is only recognised from its *response*, which arrives after its
// request headers went out — so those are held here, in memory only, and
// committed only if the response turns out to be media. Nothing but media
// headers ever reaches storage or the engine (the v0.21.2 rule, still), and
// nothing is held for more than a couple of hundred requests.
const pending = new Map();

// MV3 service workers die after ~30 s idle: a header held only here is gone
// if the worker goes away between the request and its response, and the
// guarded stream then downloads without its cookie — silently (v0.46.10
// audit B/F3). Mirror the map into chrome.storage.session — in-memory,
// browser-managed, never written to disk — so a fresh worker still finds it.
// Firefox MV2 has no session area (its background page lives for the whole
// session); the feature check keeps this a no-op there.
const pendingSession = (chrome.storage && chrome.storage.session) || null;
const PENDING_KEY = "svPending";

function _mirrorPending() {
  if (!pendingSession) return;
  try {
    pendingSession.set({ [PENDING_KEY]: Object.fromEntries(pending) });
  } catch (_) { /* a session area that refuses must never break sniffing */ }
}

function holdHeaders(url, pick) {
  pending.set(url, pick);
  while (pending.size > PENDING_KEEP) {
    pending.delete(pending.keys().next().value);
  }
  _mirrorPending();
}

function dropHeaders(url) {
  pending.delete(url);
  _mirrorPending();
}

/** The held headers for a URL: memory first, then the session mirror — the
 *  worker may have restarted since the request went out. */
async function heldHeaders(url) {
  const held = pending.get(url);
  if (held) return held;
  if (!pendingSession) return null;
  try {
    const got = await pendingSession.get(PENDING_KEY);
    return ((got && got[PENDING_KEY]) || {})[url] || null;
  } catch (_) {
    return null;
  }
}

/** The tab's captured decode key (v0.5.16), or "" — a fresh one only.
 *  The engine validates it against the stream, so a stale or foreign key
 *  fails the decode honestly instead of doing anything. */
async function pkFor(tabId) {
  if (typeof tabId !== "number" || tabId < 0) return "";
  try {
    const stored = await api.storage.local.get({ tabPk: {} });
    const hit = (stored.tabPk || {})[tabId];
    if (hit && Date.now() - (hit.at || 0) < PK_TTL_MS) return hit.pk || "";
  } catch (_) { /* no key is a normal state, not an error */ }
  return "";
}

function commitHeaders(url, pick) {
  const canon = canonicalMediaUrl(url).url;
  update(({ reqHeaders: store }) => {
    store[url] = { headers: pick, at: Date.now() };
    // the engine fetches the canonical address, so the captured referer has
    // to be findable there too; one alias per file is enough (v0.5.21)
    if (canon !== url && !store[canon]) store[canon] = { headers: pick, at: Date.now() };
    return { reqHeaders: prune(store) };
  });
}

chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    if (details.tabId < 0) return; // not a tab (worker/extension itself)
    const isMedia = details.type === "media" ||
      (details.type === "xmlhttprequest" && MEDIA_RE.test(details.url));
    if (isMedia) remember(details.tabId, details.url);
  },
  { urls: ["<all_urls>"] }
);

// Chrome hides Cookie/Referer/Origin from listeners unless the spec asks for
// `extraHeaders`; Firefox refuses that exact value — it throws "Invalid
// enumeration value" while the script is still wiring listeners, and every
// listener declared after it (the popup's message port included) would never
// exist. Ask only where the constant says the value is real (v0.5.3).
const EXTRA_HEADERS = (chrome.webRequest.OnBeforeSendHeadersOptions || {})
  .EXTRA_HEADERS ? ["extraHeaders"] : [];

chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    if (details.tabId < 0) return;
    // Only media-ish requests are ever inspected: listening to every request in
    // the tab put cookies for ordinary browsing into extension storage, and only
    // media headers are ever handed to the engine (v0.21.2 audit). A request
    // that merely *might* be media is held in memory (see holdHeaders) and
    // dropped unless its response proves it — storage stays media-only.
    if (!["media", "xmlhttprequest", "other"].includes(details.type)) return;
    const pick = pickHeaders(details.requestHeaders);
    if (!pick) return;
    if (details.type === "media" || MEDIA_RE.test(details.url)) {
      commitHeaders(details.url, pick);
    } else {
      holdHeaders(details.url, pick);
    }
  },
  { urls: ["<all_urls>"] },
  ["requestHeaders"].concat(EXTRA_HEADERS)
);

// The response decides when the name said nothing: a stream served as video/*
// from a URL no pattern recognises still ends up in the list, which is the
// whole point of sniffing rather than guessing. And every media response —
// recognised or not — hands over the two facts a person can sort by: what it
// is, and how big it is (v0.5.20).
chrome.webRequest.onHeadersReceived.addListener(
  (details) => {
    if (details.tabId < 0) return;
    if (details.type === "main_frame" || details.type === "sub_frame") return;
    const meta = responseMeta(details.responseHeaders);
    if (MEDIA_RE.test(details.url)) {
      learnMeta(details.tabId, details.url, meta);
      return;
    }
    if (!MEDIA_TYPES.test(meta.mime)) {
      dropHeaders(details.url); // the name did not lie after all
      return;
    }
    learnMeta(details.tabId, details.url, meta);
    // The request headers for this URL were held because its name said
    // nothing; now that the response proved it is media, they are worth
    // keeping — a guarded stream needs them to download.
    heldHeaders(details.url).then((held) => {
      if (held) commitHeaders(details.url, held);
      dropHeaders(details.url);
    });
  },
  { urls: ["<all_urls>"] },
  ["responseHeaders"]
);

chrome.tabs.onRemoved.addListener((tabId) => {
  // Through the same chain as every other write: a tab closing mid-stream is
  // exactly when an un-chained read-modify-write would resurrect its finds, or
  // drop another tab's.
  update(({ tabMedia, tabPoster }) => {
    delete tabMedia[tabId];
    delete tabPoster[tabId];
    return { tabMedia, tabPoster };
  });
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  // New page, new list: the previous page's finds belong to the URL that
  // asked for them. Reported live (2026-10-02): a tab walked from one video
  // to the next and the chooser still offered the old streams. changeInfo.url
  // is present only when the URL truly changed — a same-page reload keeps its
  // list — and the extension holds host permissions for every URL it watches,
  // so the URL is always there when it matters (no new permission: this needs
  // the one it already has).
  if (!changeInfo || !changeInfo.url) return;
  update(({ tabMedia, tabPoster }) => {
    if (tabMedia[tabId]) {
      delete tabMedia[tabId];
      delete tabPoster[tabId];
      if (action && action.setBadgeText) action.setBadgeText({ tabId, text: "" });
    }
    return { tabMedia, tabPoster };
  });
});

// The only messages a CONTENT SCRIPT may send: sightings. Everything else
// here drives the engine or reads stored state, and belongs to the
// extension's own pages, which carry no tab (v0.46.10 audit B/F2; v0.5.27
// added the player's poster to the sightings, nothing else).
const REPORT_ONLY = new Set(["pageFind", "pkFind", "pagePoster"]);

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  // v0.46.10 audit B/F2: pagefind.js runs in every frame of every page, so a
  // message arriving with `_sender.tab` set comes from a content script — and
  // a content script may only ever report a sighting (pageFind) or the page's
  // decode key (pkFind, v0.5.16). Every other action here drives the engine
  // or reads stored state and belongs to the extension's own pages
  // (popup/options), which carry no tab.
  if (_sender && _sender.tab && !(msg && REPORT_ONLY.has(msg.type))) {
    sendResponse({ ok: false, error: "refused" });
    return false;
  }
  if (msg && msg.type === "getMedia") {
    chrome.storage.local.get({ tabMedia: {}, reqHeaders: {}, tabPoster: {} },
      ({ tabMedia, reqHeaders, tabPoster }) => {
      const items = (tabMedia[msg.tabId] || []).map((m) => ({
        url: m.url,
        alt: m.alt || "",
        foundAt: m.foundAt,
        via: m.via || "network",
        mime: m.mime || "",
        bytes: m.bytes || 0,
        asset: m.asset || "",
        hasHeaders: !!reqHeaders[m.url],
      }));
      sendResponse({ items,
        poster: ((tabPoster || {})[msg.tabId] || {}).url || "" });
    });
    return true; // async response
  }
  if (msg && msg.type === "rank") {
    rankWithEngine(msg.items || []).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "shape") {
    shapeWithEngine(msg.items || [], msg.tabId).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "engineState") {
    engineState().then(sendResponse);
    return true;
  }
  if (msg && msg.type === "sendHandoff") {
    sendHandoff(msg.url, msg.urls, msg.tabUrl, msg.tabId).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "sendToEngine") {
    sendToEngine(msg.url, msg.tabId, msg.audioUrl).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "sendBatch") {
    sendBatchToEngine(msg.urls, msg.tabId).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "recentJobs") {
    recentJobs().then(sendResponse);
    return true;
  }
  if (msg && msg.type === "pagePoster") {
    // the player's own poster is the one picture available for a stream the
    // extension cannot decode (HLS), so a row can still wear a face (v0.5.27)
    const tabId = _sender && _sender.tab ? _sender.tab.id : undefined;
    if (typeof tabId === "number" && tabId >= 0 && msg.url) {
      update(({ tabPoster }) => {
        tabPoster[tabId] = { url: String(msg.url), at: Date.now() };
        return { tabPoster };
      });
      sendResponse({ ok: true });
      return false;
    }
    sendResponse({ ok: false });
    return false;
  }
  if (msg && msg.type === "pageFind") {
    // the page-side layer (v0.5.13): only a content script can send this —
    // the message always carries the sender's tab, and nothing else does.
    // The page itself cannot reach this (isolated world), so a "find" is
    // never forgeable by the page being visited.
    const tabId = _sender && _sender.tab ? _sender.tab.id : undefined;
    if (typeof tabId === "number" && tabId >= 0 && msg.url) {
      remember(tabId, String(msg.url), msg.via === "player" ? "player" : "page");
      sendResponse({ ok: true });
      return false;
    }
    sendResponse({ ok: false });
    return false;
  }
  if (msg && msg.type === "pkFind") {
    // the decode key of a scrambled-playlist player (v0.5.16): Chrome reads
    // it in the MAIN world (pk.js) and posts it through the content script;
    // Firefox reads it via wrappedJSObject in pagefind.js. Stored per tab
    // like the captured headers — and, like them, only ever handed to the
    // engine, which validates the key against the stream itself (a forged
    // key fails the decode, it never grants anything).
    const tabId = _sender && _sender.tab ? _sender.tab.id : undefined;
    if (typeof tabId === "number" && tabId >= 0
        && typeof msg.pk === "string" && msg.pk.length >= 16 && msg.pk.length <= 512) {
      update(({ tabPk }) => {
        tabPk[tabId] = { pk: msg.pk, at: Date.now() };
        return { tabPk: prunePk(tabPk) };
      });
      sendResponse({ ok: true });
      return false;
    }
    sendResponse({ ok: false });
    return false;
  }
});

// Which of these is worth showing? The engine's answer, so the popup and the
// phone hide the same fragments for the same reason. No answer (engine down) →
// show everything: never hide something on a guess.
async function rankWithEngine(items) {
  const stored = await api.storage.local.get({ engineToken: "" });
  const eng = await resolveEngine();
  if (!eng.ok) return null;
  try {
    const res = await fetch(eng.base + "/sniff/rank", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + stored.engineToken,
      },
      body: JSON.stringify({ urls: items.map((m) => m.url) }),
    });
    if (res.ok) return await res.json();
  } catch (e) {
    /* fall through: show everything */
  }
  return null;
}

// The stream's own shape: a master manifest says each variant's resolution
// and each audio rendition's name. The popup labels rows with this — a row
// called "video" by its URL becomes "Video · 1080p" (v0.47.3).
async function shapeWithEngine(items, tabId) {
  const eng = await resolveEngine();
  if (!eng.ok) return null;
  const stored = await api.storage.local.get({ engineToken: "", reqHeaders: {} });
  let headers = {};
  for (const m of items) {
    const hit = stored.reqHeaders[m.url];
    if (hit && hit.headers) { headers = hit.headers; break; }
  }
  try {
    const res = await fetch(eng.base + "/sniff/shape", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + stored.engineToken,
      },
      body: JSON.stringify({
        urls: items.map((m) => m.url),
        headers,
        xor_key: (await pkFor(tabId)) || undefined,
      }),
    });
    if (res.ok) return await res.json();
  } catch (e) {
    /* fall through: labels fall back to the URL */
  }
  return null;
}

async function sendToEngine(url, tabId, audioUrl) {
  url = await resolveShareUrl(url);
  const stored = await api.storage.local.get({ engineToken: "", reqHeaders: {} });
  const captured = (stored.reqHeaders[url] && stored.reqHeaders[url].headers) || {};
  const eng = await resolveEngine();
  if (!eng.ok) {
    return { ok: false, error: "cannot reach the engine at " + eng.base +
             " — is the suravidl app open?" };
  }
  let res;
  try {
    res = await fetch(eng.base + "/jobs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + stored.engineToken,
      },
      body: JSON.stringify({ url, headers: captured,
                             // a feed's soundtrack, paired by the popup
                             audio_url: audioUrl || undefined,
                             xor_key: (await pkFor(tabId)) || undefined }),
    });
  } catch (e) {
    RESOLVED = "";
    return { ok: false, error: "cannot reach the engine at " + eng.base +
             " — is the suravidl app open? (" + e + ")" };
  }
  if (res.status === 401 || res.status === 403) {
    return { ok: false, error: "the engine refused the token (" + res.status +
             ") — copy it in suravidl → Settings → Authentication → API token, paste it " +
             "into the extension's Options (the link below)" };
  }
  if (!res.ok) return { ok: false, error: "engine " + res.status + ": " + (await res.text()) };
  return { ok: true, job: await res.json() };
}

// Queue several finds at once (v0.40.7): the engine's own batch door, which
// answers per link (`skipped`) instead of failing the lot — one bad row in
// a handful must not cost the rest. The engine has had /jobs/batch since
// long before /handoff; an even older one falls back to sending one by one.
async function sendBatchToEngine(urls, tabId) {
  const list = (urls || []).filter(Boolean).slice(0, 20);
  if (!list.length) return { ok: false, error: "nothing to send" };
  const stored = await api.storage.local.get({ engineToken: "", reqHeaders: {} });
  // v0.43.2: the single quick door rides the captured request headers (an
  // auth-walled stream refuses without them) — the batch door must too.
  // One map keyed by URL; links with nothing captured fall back engine-side.
  // v0.5.12: a share link resolves first; captured headers key on the URL
  // the page actually used, so each send keeps its own lookup
  const pairs = [];
  for (const u of list) pairs.push({ from: u, url: await resolveShareUrl(u) });
  const resolvedList = pairs.map((p) => p.url);
  const headersByUrl = {};
  for (const p of pairs) {
    const h = stored.reqHeaders[p.from] && stored.reqHeaders[p.from].headers;
    if (h && Object.keys(h).length) headersByUrl[p.url] = h;
  }
  const eng = await resolveEngine();
  if (!eng.ok) {
    return { ok: false, error: "cannot reach the engine at " + eng.base +
             " — is the suravidl app open?" };
  }
  let res;
  try {
    res = await fetch(eng.base + "/jobs/batch", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + stored.engineToken,
      },
      body: JSON.stringify(Object.keys(headersByUrl).length
        ? { urls: resolvedList, headers_by_url: headersByUrl,
            xor_key: (await pkFor(tabId)) || undefined }
        : { urls: resolvedList,
            xor_key: (await pkFor(tabId)) || undefined }),
    });
  } catch (e) {
    RESOLVED = "";   // it moved: look again next time
    return { ok: false, error: "cannot reach the engine at " + eng.base +
             " — is the suravidl app open? (" + e + ")" };
  }
  if (res.status === 401 || res.status === 403) {
    return { ok: false, error: "the engine refused the token (" + res.status +
             ") — copy it in suravidl → Settings → Authentication → API token, paste it " +
             "into the extension's Options (the link below)" };
  }
  if (res.status === 404 || res.status === 405) {
    let queued = 0;
    for (const u of resolvedList) {
      const one = await sendToEngine(u);
      if (one.ok) queued += 1;
    }
    return queued ? { ok: true, queued, skipped: list.length - queued }
                  : { ok: false, error: "engine " + res.status };
  }
  if (!res.ok) return { ok: false, error: "engine " + res.status + ": " + (await res.text()) };
  const body = await res.json();
  const queued = (body.jobs || []).length;
  const skipped = (body.skipped || []).length;
  if (!queued) {
    const why = ((body.skipped || [])[0] || {}).error || "nothing queued";
    return { ok: false, error: "the engine skipped every link: " + why };
  }
  return { ok: true, queued, skipped };
}

// ── share links (v0.5.12) ────────────────────────────────────────────────
// Reddit-style "/…/s/…" share links only resolve inside a browser session:
// a downloader fetching one gets "this link does not exist" (the app has
// said so honestly since v0.45.28). The extension IS a session, so it
// resolves them before anything is sent. Two sources, in order:
//   1. the redirect the browser itself made when the user opened the link
//      — observed live and remembered, no fetch needed (and the only path
//      on Firefox: its background fetches are CORS-bound, measured, so an
//      unmapped link there passes through unchanged);
//   2. a follow-redirect fetch. Chrome exempts extension fetches that hold
//      host permissions, so it resolves there even for a bare link.
const SHARE_LINK = /^https?:\/\/(?:[a-z0-9-]+\.)*reddit\.com\/[^?#]*\/s\/[A-Za-z0-9]+/i;
let SHARE_MAP = null;   // lazily read from storage; { shareUrl: canonical }

async function shareMap() {
  if (SHARE_MAP) return SHARE_MAP;
  try {
    const got = await api.storage.local.get({ shareMap: {} });
    SHARE_MAP = got.shareMap || {};
  } catch (_) { SHARE_MAP = {}; }
  return SHARE_MAP;
}

function rememberShare(from, to) {
  if (!from || !to || from === to) return;
  update(({ shareMap }) => {
    const map = Object.assign({}, shareMap || {});
    map[from] = to;
    const keys = Object.keys(map);
    while (keys.length > 40) delete map[keys.shift()];
    SHARE_MAP = map;
    return { shareMap: map };
  });
}

async function resolveShareUrl(url) {
  if (!url || !SHARE_LINK.test(url)) return url;
  try {
    const map = await shareMap();
    if (map[url]) return map[url];
  } catch (_) { /* fall through to the fetch */ }
  try {
    const res = await fetch(url, { redirect: "follow", credentials: "include",
                                   cache: "no-store" });
    const final = (res && res.url) || "";
    if (final && final !== url && !SHARE_LINK.test(final)) {
      rememberShare(url, final);   // the next send needs no fetch at all
      return final;
    }
  } catch (_) { /* CORS (Firefox) or offline: the link passes through */ }
  return url;
}

// the browser's own redirects are the cheapest source — fired for the tab's
// real navigations, so a link the user opened is resolved the moment it lands
if (chrome.webRequest.onBeforeRedirect) {
  chrome.webRequest.onBeforeRedirect.addListener(
    (details) => {
      try {
        if (SHARE_LINK.test(details.url || "") && details.redirectUrl) {
          rememberShare(details.url, details.redirectUrl);
        }
      } catch (_) { /* never fatal */ }
    },
    { urls: ["*://*.reddit.com/*"] }
  );
}

// ── the popup's mirror (v0.5.12) ─────────────────────────────────────────
// What the engine is doing with what was sent — the same states and the
// same honest notes the app shows, where the hand-off was made. Read-only;
// a failure is just "nothing to mirror", never an error on the popup.
const RECENT_KEEP = 4;

async function recentJobs() {
  const stored = await api.storage.local.get({ engineToken: "" });
  const eng = await resolveEngine();
  if (!eng.ok) return { ok: false, jobs: [] };
  try {
    const res = await fetch(eng.base + "/jobs", {
      headers: { Authorization: "Bearer " + stored.engineToken },
      cache: "no-store",
    });
    if (!res.ok) return { ok: false, jobs: [] };
    const body = await res.json();
    const jobs = (body.jobs || [])
      .slice()
      .sort((a, b) => String(b.created_at || "").localeCompare(String(a.created_at || "")))
      .slice(0, RECENT_KEEP)
      .map((j) => ({
        id: j.id,
        url: j.url || "",
        title: j.title || "",
        status: j.status || "",
        note: j.note || "",
      }));
    return { ok: true, jobs };
  } catch (_) {
    return { ok: false, jobs: [] };
  }
}

// The engine's port ladder. Keep in sync with _port_candidates() in
// suravidl_engine/__main__.py (a test pins both): the app sits on 8787
// unless that was busy at launch, when it walks one rung at a time — never
// a random port, so the extension can always find it. This is the fix for
// "suravidl isn't running" while the app visibly ran: its engine had moved
// and the extension never looked.
const PORT_LADDER = [8787, 8788, 8789, 8790, 8791, 8792];
let RESOLVED = "";   // where this session already found the engine

async function probeBase(base, ms = 700) {
  // one quick /health — the only engine call that needs no token
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), ms);
    const res = await fetch(base + "/health", { cache: "no-store", signal: ctrl.signal });
    clearTimeout(timer);
    if (!res.ok) return null;
    const body = await res.json();
    return body && body.ok ? { base, version: body.version || "" } : null;
  } catch (_) {
    return null;
  }
}

// Where is the engine? The configured address first; when that address is
// this machine, walk the port ladder too. The answer is remembered for the
// session and — when it is not the configured address — for the next one.
async function resolveEngine() {
  const stored = await api.storage.local.get({
    engineUrl: "http://127.0.0.1:8787",
    discoveredUrl: "",
  });
  const configured = String(stored.engineUrl || "").replace(/\/$/, "");
  const candidates = [RESOLVED, stored.discoveredUrl, configured];
  let loopback = false;
  try {
    loopback = ["127.0.0.1", "localhost", "::1", "[::1]"]
      .includes(new URL(configured).hostname);
  } catch (_) { /* unparseable address: nothing local to scan */ }
  if (loopback) {
    for (const p of PORT_LADDER) candidates.push("http://127.0.0.1:" + p);
  }
  const tried = [];
  for (const c of candidates) {
    if (!c || tried.includes(c)) continue;
    tried.push(c);
    const hit = await probeBase(c);
    if (hit) {
      RESOLVED = hit.base;
      if (hit.base !== configured && stored.discoveredUrl !== hit.base) {
        api.storage.local.set({ discoveredUrl: hit.base });
      }
      return { ok: true, base: hit.base, version: hit.version };
    }
  }
  return { ok: false, base: configured };
}

// Is the engine up? /health needs no token, so this answers even when the
// token is not configured yet — the popup's "not running" state is about
// the app, not about credentials.
async function engineState() {
  const eng = await resolveEngine();
  if (!eng.ok) return { ok: false, error: "cannot reach the engine at " + eng.base };
  return { ok: true, version: eng.version, url: eng.base };
}

// Hand the find over (v0.39.0): the engine probes the stream itself — with
// the captured headers — and the app's window opens on the format list, so
// the quality choice happens where the formats are real. An older engine
// (no /handoff) falls back to the one-shot job this extension used to send.
async function sendHandoff(url, urls, tabUrl, tabId) {
  url = await resolveShareUrl(url);
  tabUrl = await resolveShareUrl(tabUrl);
  urls = await Promise.all((urls || []).map(resolveShareUrl));
  const stored = await api.storage.local.get({ engineToken: "", reqHeaders: {} });
  const captured = (stored.reqHeaders[url] && stored.reqHeaders[url].headers) || {};
  const eng = await resolveEngine();
  if (!eng.ok) {
    return { ok: false, error: "cannot reach the engine at " + eng.base +
             " — is the suravidl app open?" };
  }
  let res;
  try {
    res = await fetch(eng.base + "/handoff", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + stored.engineToken,
      },
      body: JSON.stringify({ url, urls: urls || [], headers: captured,
                             tab_url: tabUrl || "",
                             xor_key: (await pkFor(tabId)) || undefined }),
    });
  } catch (e) {
    RESOLVED = "";   // it moved: look again next time
    return { ok: false, error: "cannot reach the engine at " + eng.base +
             " — is the suravidl app open? (" + e + ")" };
  }
  if (res.status === 404 || res.status === 405) {
    // an older engine has no /handoff: the old one-shot job is still honest
    const old = await sendToEngine(url, tabId);
    return old.ok ? { ok: true, mode: "job", job: old.job } : old;
  }
  if (res.status === 401 || res.status === 403) {
    return { ok: false, error: "the engine refused the token (" + res.status +
             ") — copy it in suravidl → Settings → Authentication → API token, paste it " +
             "into the extension's Options (the link below)" };
  }
  if (!res.ok) return { ok: false, error: "engine " + res.status + ": " + (await res.text()) };
  return { ok: true, mode: "handoff", handoff: await res.json() };
}

// Right-click → Download with suravidl (v0.40.7): the quality door, for any
// link, video, or page — no trip through the toolbar. The menu is rebuilt on
// every load (MV3 workers restart; removeAll-then-create is the one pattern
// that never trips the duplicate-id error). Firefox's canonical namespace is
// `browser.menus` — chrome.contextMenus is not an alias there — so both are
// tried, and a browser without either simply keeps the popup flow.
function menuUrl(info) {
  return (info && (info.srcUrl || info.linkUrl || info.pageUrl)) || "";
}

function installMenus() {
  const menus = (globalThis.browser && globalThis.browser.menus) ||
                (typeof chrome !== "undefined" && chrome.contextMenus);
  if (!menus || !menus.create || !menus.onClicked) return;
  try {
    menus.removeAll(() => {
      try {
        menus.create({
          id: "suravidl-download",
          title: "Download with suravidl",
          contexts: ["link", "video", "audio", "page"],
        }, () => {
          try { void (chrome.runtime && chrome.runtime.lastError); } catch (_) { /* none */ }
        });
      } catch (_) { /* nothing to install into */ }
    });
  } catch (_) { /* nothing to install into */ }
  menus.onClicked.addListener(async (info, tab) => {
    const url = menuUrl(info);
    if (!url) return;
    const res = await sendHandoff(url, [], (tab && tab.url) || (info && info.pageUrl) || "",
                                  tab && tab.id);
    // no popup to say it in: a quiet "!" on the toolbar until the next send
    try {
      if (chrome.action && chrome.action.setBadgeText) {
        chrome.action.setBadgeText(
          res && res.ok ? { text: "" } : { text: "!" });
      }
    } catch (_) { /* nothing to say it on */ }
  });
}

loadPatterns();
installMenus();
