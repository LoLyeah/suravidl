// suravidl extension background (MV3 service worker / Firefox background page).
// Detects media per tab, captures the request headers yt-dlp needs
// (Cookie / User-Agent / Referer), badges the count, hands off to the engine.
const MEDIA_RE = /\.(mp4|webm|m3u8|mpd|mov|mkv|avi|flv|ts|m4s|mp3|m4a|aac|ogg|opus|wav)(\?|$)/i;
const KEEP_PER_TAB = 20;
const HEADER_KEEP = 100;
const action = chrome.action || chrome.browserAction; // MV3 vs Firefox MV2

function prune(reqHeaders) {
  const entries = Object.entries(reqHeaders).slice(-HEADER_KEEP);
  return Object.fromEntries(entries);
}

function remember(tabId, url) {
  chrome.storage.local.get({ tabMedia: {}, reqHeaders: {} }, ({ tabMedia, reqHeaders }) => {
    const list = tabMedia[tabId] || [];
    let added = false;
    if (!list.some((m) => m.url === url)) {
      list.push({ url, foundAt: Date.now() });
      tabMedia[tabId] = list.slice(-KEEP_PER_TAB);
      added = true;
    }
    const write = { tabMedia };
    if (added) write.reqHeaders = prune(reqHeaders);
    chrome.storage.local.set(write, () => {
      if (added && action && action.setBadgeText) {
        action.setBadgeText({ tabId, text: String(tabMedia[tabId].length) });
      }
    });
  });
}

// capture the headers yt-dlp needs for auth'd sites (Cookie/UA/Referer/Origin)
function captureHeaders(url, reqHeaders) {
  const pick = {};
  for (const h of reqHeaders || []) {
    const k = (h.name || "").toLowerCase();
    if (["cookie", "user-agent", "referer", "origin"].includes(k) && h.value) {
      pick[k] = h.value;
    }
  }
  if (!Object.keys(pick).length) return;
  chrome.storage.local.get({ reqHeaders: {} }, ({ reqHeaders: store }) => {
    store[url] = { headers: pick, at: Date.now() };
    chrome.storage.local.set({ reqHeaders: prune(store) });
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
    // Capture only media-ish requests. Listening to every request in the tab
    // put cookies for ordinary browsing into extension storage, and only
    // media headers are ever handed to the engine (v0.21.2 audit).
    const isMedia =
      details.type === "media" ||
      (["xmlhttprequest", "other", "media"].includes(details.type) &&
        MEDIA_RE.test(details.url));
    if (!isMedia) return;
    captureHeaders(details.url, details.requestHeaders);
  },
  { urls: ["<all_urls>"] },
  ["requestHeaders", "extraHeaders"]
);

chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.get({ tabMedia: {} }, ({ tabMedia }) => {
    delete tabMedia[tabId];
    chrome.storage.local.set({ tabMedia });
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
  if (msg && msg.type === "sendToEngine") {
    sendToEngine(msg.url).then(sendResponse);
    return true;
  }
});

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
