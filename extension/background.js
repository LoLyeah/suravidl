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
const KEEP_PER_TAB = 20;
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

// Storage is read-modify-write, and three media requests can land in the same
// tick — a player asks for its manifest and its first fragments together. So
// every write is chained: without it the last writer wins and finds disappear
// (found the hard way, by the Node harness in extension/test_harness.mjs).
let storageChain = Promise.resolve();
function update(mutate) {
  storageChain = storageChain
    .then(() => new Promise((resolve) => {
      chrome.storage.local.get({ tabMedia: {}, reqHeaders: {}, shareMap: {} }, (data) => {
        chrome.storage.local.set(mutate(data) || {}, resolve);
      });
    }))
    .catch(() => {});
  return storageChain;
}

function remember(tabId, url) {
  update(({ tabMedia, reqHeaders }) => {
    const list = tabMedia[tabId] || [];
    let added = false;
    if (!list.some((m) => m.url === url)) {
      list.push({ url, foundAt: Date.now() });
      tabMedia[tabId] = list.slice(-KEEP_PER_TAB);
      added = true;
    }
    if (added && action && action.setBadgeText) {
      action.setBadgeText({ tabId, text: String(tabMedia[tabId].length) });
    }
    return added ? { tabMedia, reqHeaders: prune(reqHeaders) } : { tabMedia };
  });
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

function holdHeaders(url, pick) {
  pending.set(url, pick);
  while (pending.size > PENDING_KEEP) {
    pending.delete(pending.keys().next().value);
  }
}

function commitHeaders(url, pick) {
  update(({ reqHeaders: store }) => {
    store[url] = { headers: pick, at: Date.now() };
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
// whole point of sniffing rather than guessing.
chrome.webRequest.onHeadersReceived.addListener(
  (details) => {
    if (details.tabId < 0) return;
    if (details.type === "main_frame" || details.type === "sub_frame") return;
    if (MEDIA_RE.test(details.url)) return; // already known by its name
    for (const h of details.responseHeaders || []) {
      if ((h.name || "").toLowerCase() === "content-type" && MEDIA_TYPES.test(h.value || "")) {
        remember(details.tabId, details.url);
        // The request headers for this URL were held because its name said
        // nothing; now that the response proved it is media, they are worth
        // keeping — a guarded stream needs them to download.
        const held = pending.get(details.url);
        if (held) commitHeaders(details.url, held);
        pending.delete(details.url);
        return;
      }
    }
    pending.delete(details.url); // the name did not lie after all
  },
  { urls: ["<all_urls>"] },
  ["responseHeaders"]
);

chrome.tabs.onRemoved.addListener((tabId) => {
  // Through the same chain as every other write: a tab closing mid-stream is
  // exactly when an un-chained read-modify-write would resurrect its finds, or
  // drop another tab's.
  update(({ tabMedia }) => {
    delete tabMedia[tabId];
    return { tabMedia };
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
  update(({ tabMedia }) => {
    if (tabMedia[tabId]) {
      delete tabMedia[tabId];
      if (action && action.setBadgeText) action.setBadgeText({ tabId, text: "" });
    }
    return { tabMedia };
  });
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "getMedia") {
    chrome.storage.local.get({ tabMedia: {}, reqHeaders: {} }, ({ tabMedia, reqHeaders }) => {
      const items = (tabMedia[msg.tabId] || []).map((m) => ({
        url: m.url,
        foundAt: m.foundAt,
        hasHeaders: !!reqHeaders[m.url],
      }));
      sendResponse({ items });
    });
    return true; // async response
  }
  if (msg && msg.type === "rank") {
    rankWithEngine(msg.items || []).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "engineState") {
    engineState().then(sendResponse);
    return true;
  }
  if (msg && msg.type === "sendHandoff") {
    sendHandoff(msg.url, msg.urls, msg.tabUrl).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "sendToEngine") {
    sendToEngine(msg.url).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "sendBatch") {
    sendBatchToEngine(msg.urls).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "recentJobs") {
    recentJobs().then(sendResponse);
    return true;
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

async function sendToEngine(url) {
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
      body: JSON.stringify({ url, headers: captured }),
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
async function sendBatchToEngine(urls) {
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
        ? { urls: resolvedList, headers_by_url: headersByUrl }
        : { urls: resolvedList }),
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
async function sendHandoff(url, urls, tabUrl) {
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
                             tab_url: tabUrl || "" }),
    });
  } catch (e) {
    RESOLVED = "";   // it moved: look again next time
    return { ok: false, error: "cannot reach the engine at " + eng.base +
             " — is the suravidl app open? (" + e + ")" };
  }
  if (res.status === 404 || res.status === 405) {
    // an older engine has no /handoff: the old one-shot job is still honest
    const old = await sendToEngine(url);
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
    const res = await sendHandoff(url, [], (tab && tab.url) || (info && info.pageUrl) || "");
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
