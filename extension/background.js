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
        const res = await fetch(stored.engineUrl.replace(/\/$/, "") + "/sniff/patterns", {
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
  ["requestHeaders", "extraHeaders"]
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
  if (msg && msg.type === "sendToEngine") {
    sendToEngine(msg.url).then(sendResponse);
    return true;
  }
});

// Which of these is worth showing? The engine's answer, so the popup and the
// phone hide the same fragments for the same reason. No answer (engine down) →
// show everything: never hide something on a guess.
async function rankWithEngine(items) {
  const stored = await chrome.storage.local.get({
    engineUrl: "http://127.0.0.1:8787",
    engineToken: "",
  });
  try {
    const res = await fetch(stored.engineUrl.replace(/\/$/, "") + "/sniff/rank", {
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
  const stored = await chrome.storage.local.get({
    engineUrl: "http://127.0.0.1:8787",
    engineToken: "",
    reqHeaders: {},
  });
  const captured = (stored.reqHeaders[url] && stored.reqHeaders[url].headers) || {};
  let res;
  try {
    res = await fetch(stored.engineUrl.replace(/\/$/, "") + "/jobs", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + stored.engineToken,
      },
      body: JSON.stringify({ url, headers: captured }),
    });
  } catch (e) {
    return { ok: false, error: "engine unreachable: " + e };
  }
  if (!res.ok) return { ok: false, error: "engine " + res.status + ": " + (await res.text()) };
  return { ok: true, job: await res.json() };
}

loadPatterns();
