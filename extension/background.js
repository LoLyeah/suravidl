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
      chrome.storage.local.get({ tabMedia: {}, reqHeaders: {} }, (data) => {
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
             ") — copy it in suravidl → Settings → Network → API token, paste it " +
             "into the extension's Options (the link below)" };
  }
  if (!res.ok) return { ok: false, error: "engine " + res.status + ": " + (await res.text()) };
  return { ok: true, job: await res.json() };
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
             ") — copy it in suravidl → Settings → Network → API token, paste it " +
             "into the extension's Options (the link below)" };
  }
  if (!res.ok) return { ok: false, error: "engine " + res.status + ": " + (await res.text()) };
  return { ok: true, mode: "handoff", handoff: await res.json() };
}

loadPatterns();
