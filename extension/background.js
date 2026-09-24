// Detect media requests per tab, keep last N in chrome.storage (MV3 workers die fast).
const MEDIA_RE = /\.(mp4|webm|m3u8|mpd|mov|mkv|avi|flv|ts|m4s|mp3|m4a|aac|ogg|opus|wav)(\?|$)/i;
const KEEP = 20;

function remember(tabId, url) {
  chrome.storage.local.get({ tabMedia: {} }, ({ tabMedia }) => {
    const list = tabMedia[tabId] || [];
    if (!list.some((m) => m.url === url)) {
      list.push({ url, foundAt: Date.now() });
      tabMedia[tabId] = list.slice(-KEEP);
      chrome.storage.local.set({ tabMedia });
    }
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

chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.get({ tabMedia: {} }, ({ tabMedia }) => {
    delete tabMedia[tabId];
    chrome.storage.local.set({ tabMedia });
  });
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "getMedia") {
    chrome.storage.local.get({ tabMedia: {} }, ({ tabMedia }) => {
      sendResponse({ items: tabMedia[msg.tabId] || [] });
    });
    return true; // async response
  }
  if (msg?.type === "sendToEngine") {
    sendToEngine(msg.url).then(sendResponse);
    return true;
  }
});

async function sendToEngine(url) {
  const { engineUrl, engineToken } = await chrome.storage.local.get({
    engineUrl: "http://127.0.0.1:8787",
    engineToken: "",
  });
  let res;
  try {
    res = await fetch(`${engineUrl.replace(/\/$/, "")}/jobs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${engineToken}`,
      },
      body: JSON.stringify({ url, headers: {} }),
    });
  } catch (e) {
    return { ok: false, error: `engine unreachable: ${e}` };
  }
  if (!res.ok) return { ok: false, error: `engine ${res.status}: ${await res.text()}` };
  return { ok: true, job: await res.json() };
}
