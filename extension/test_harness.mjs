// The extension's background logic, run for real in Node with a stubbed chrome
// API. The emulator can host the Android shell but not a Chrome extension, and
// a browser test would drag xvfb into CI — so the listeners are fired here with
// realistic requests and everything they do is asserted: what gets remembered,
// what gets captured, and what the engine is asked.
//
// Run: node extension/test_harness.mjs   (exit 1 with a list of failures)
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "background.js"), "utf8");
const i18nSrc = readFileSync(join(here, "i18n.js"), "utf8");
const popupSrc = readFileSync(join(here, "popup.js"), "utf8");
const popupFull = i18nSrc + "\n" + popupSrc;   // the extension's own t() rides along

const failures = [];
const ok = (cond, what) => {
  if (!cond) failures.push(what);
};

// -- a chrome stub with just enough surface ---------------------------------
const listeners = { beforeRequest: [], beforeSendHeaders: [], headersReceived: [],
                    beforeRedirect: [], beforeSendHeadersSpec: null, menuClicks: [] };
const menusMade = [];
const store = {};
const badge = {};
const fetchCalls = [];
const headCalls = [];
let onRemoved = [];
let onUpdated = [];
let onMessage = null;

globalThis.chrome = {
  action: { setBadgeText: ({ tabId, text }) => (badge[tabId] = text) },
  contextMenus: {
    create: (props, cb) => { menusMade.push(props); if (cb) cb(); },
    removeAll: (cb) => { if (cb) cb(); },
    onClicked: { addListener: (fn) => listeners.menuClicks.push(fn) },
  },
  storage: {
    local: {
      get(defaults, cb) {
        const read = () => {
          const out = { ...defaults };
          for (const k of Object.keys(defaults)) if (k in store) out[k] = store[k];
          return out;
        };
        // the real API takes a callback *or* returns a promise — both forms are
        // used in background.js, so both must work here
        if (typeof cb === "function") {
          Promise.resolve().then(() => cb(read()));
          return undefined;
        }
        return Promise.resolve().then(read);
      },
      set(obj, cb) {
        Object.assign(store, JSON.parse(JSON.stringify(obj)));
        if (cb) Promise.resolve().then(cb);
      },
    },
  },
  webRequest: {
    // Chrome exposes the extraHeaders constant; Firefox's object does not —
    // that difference is what the guard in background.js reads (see the
    // Firefox section below)
    OnBeforeSendHeadersOptions: { EXTRA_HEADERS: "extraHeaders" },
    onBeforeRequest: { addListener: (fn) => listeners.beforeRequest.push(fn) },
    onBeforeSendHeaders: {
      addListener: (fn, _filter, spec) => {
        listeners.beforeSendHeadersSpec = spec;
        listeners.beforeSendHeaders.push(fn);
      },
    },
    onHeadersReceived: { addListener: (fn) => listeners.headersReceived.push(fn) },
    onBeforeRedirect: { addListener: (fn) => listeners.beforeRedirect.push(fn) },
  },
  tabs: {
    onRemoved: { addListener: (fn) => onRemoved.push(fn) },
    onUpdated: { addListener: (fn) => onUpdated.push(fn) },
    query() {},
  },
  runtime: { onMessage: { addListener: (fn) => (onMessage = fn) } },
};

globalThis.fetch = async (url, opts = {}) => {
  fetchCalls.push({ url, opts });
  // the true-size probe (v0.5.21): this one address answers a HEAD with the
  // real length, so a sliced find can learn it without downloading a byte
  if (/^HEAD$/i.test(opts.method || "") && url === "https://cdn.fb/probe.mp4?oh=1") {
    headCalls.push(url);
    return { ok: true, status: 200, headers: {
      get: (n) => (/^content-length$/i.test(n) ? "5242880" : null),
    } };
  }
  // a CDN that refuses HEAD still answers a one-byte range with the total in
  // Content-Range (v0.5.21)
  if (url === "https://cdn.fb/ranged.mp4?oh=9") {
    if (/^HEAD$/i.test(opts.method || "")) {
      return { ok: false, status: 403, text: async () => "no" };
    }
    if (/bytes=0-0/.test(String((opts.headers || {}).Range || ""))) {
      return { ok: false, status: 206, headers: {
        get: (n) => (/^content-range$/i.test(n) ? "bytes 0-0/7340032" : null),
      } };
    }
  }
  if (/reddit\.com\/.*\/s\//i.test(url)) {
    // the follow-redirect resolve: Chrome exempts extension fetches that
    // hold host permissions, so the canonical address comes back
    return { ok: true, status: 200,
             url: "https://www.reddit.com/r/y/comments/zzz9/followed/",
             json: async () => ({}) };
  }
  if (url.endsWith("/jobs")) {
    if ((opts.method || "GET") === "GET") {
      return { ok: true, status: 200, json: async () => ({ jobs: [
        { id: "m2", title: "reddit video", status: "completed",
          created_at: "2026-10-10T02:00:00Z",
          note: "the thumbnail could not be embedded" },
        { id: "m1", title: "clip", status: "downloading",
          created_at: "2026-10-10T01:00:00Z" },
      ] }) };
    }
    return { ok: true, status: 200, json: async () => ({ id: "J9" }) };
  }
  if (url.endsWith("/sniff/patterns")) {
    // an extension the baked-in fallback does not know: proof the engine's list
    // is what is in use
    return { ok: true, json: async () => ({ ext: ["mp4", "m3u8", "ts", "xyz"] }) };
  }
  if (url.endsWith("/sniff/rank")) {
    return {
      ok: true,
      json: async () => ({
        items: [{ url: "https://cdn/x.m3u8", kind: "manifest", hidden: false, reason: "" }],
        hidden: 0,
      }),
    };
  }
  if (url.endsWith("/health")) {
    return { ok: true, status: 200, json: async () => ({ ok: true, version: "0.39.2" }) };
  }
  if (url.endsWith("/handoff")) {
    return { ok: true, status: 200,
             json: async () => ({ ok: true, id: "hm1", status: "probing" }) };
  }
  if (url.endsWith("/jobs/batch")) {
    const list = (JSON.parse(opts.body || "{}").urls) || [];
    return { ok: true, status: 200,
             json: async () => ({ jobs: list.map((_, i) => ({ id: "B" + i })), skipped: [] }) };
  }
  return { ok: false, status: 404, text: async () => "nope" };
};

// -- load the extension source as a plain script -----------------------------
// Loading twice is also how a worker restart is simulated: MV3 workers are
// ephemeral, so `new Function(src)()` against the same storage is exactly what
// Chrome does when it wakes the worker up again.
function load() {
  new Function(src)();
}
load();

const settle = () => new Promise((r) => setTimeout(r, 25));
const req = (type, url, extra = {}) => ({ tabId: 7, type, url, ...extra });
const sent = [
  { name: "Cookie", value: "sid=1" },
  { name: "User-Agent", value: "UA/1" },
  { name: "Referer", value: "https://site/watch" },
  { name: "Accept-Language", value: "en" },
  { name: "Authorization", value: "Bearer nope" },
];
const found = () => ((store.tabMedia || {})[7] || []).map((m) => m.url);

// 1. what counts as a find — and, just as important, what does not
listeners.beforeRequest[0](req("media", "https://cdn/show"));
listeners.beforeRequest[0](req("image", "https://cdn/logo.png"));
listeners.beforeSendHeaders[0](req("media", "https://cdn/show", { requestHeaders: sent }));
listeners.beforeSendHeaders[0](req("image", "https://cdn/logo.png", { requestHeaders: sent }));
listeners.headersReceived[0](req("media", "https://cdn/lying", {
  responseHeaders: [{ name: "Content-Type", value: "video/mp4" }],
}));
listeners.headersReceived[0](req("media", "https://cdn/page", {
  responseHeaders: [{ name: "Content-Type", value: "text/html" }],
}));
await settle();

ok(found().includes("https://cdn/show"), "a media element request is remembered");
ok(!found().includes("https://cdn/logo.png"), "an image is not a find");
ok(found().includes("https://cdn/lying"),
   "a video/* response whose URL says nothing is a find");
ok(!found().includes("https://cdn/page"), "an HTML response is not a find");
ok(Number(badge[7]) === found().length && Number(badge[7]) >= 2,
   "the badge counts the finds");

const cap = (store.reqHeaders || {})["https://cdn/show"];
ok(cap && cap.headers.cookie === "sid=1" && cap.headers["user-agent"] === "UA/1" &&
   cap.headers.referer === "https://site/watch",
   "the handoff headers are captured: cookie, UA, referer");
ok(cap && !("accept-language" in cap.headers) && !("authorization" in cap.headers),
   "and nothing beyond what the engine forwards");
ok(!(store.reqHeaders || {})["https://cdn/logo.png"],
   "ordinary browsing's headers never reach storage");
ok(Array.isArray(listeners.beforeSendHeadersSpec) &&
   listeners.beforeSendHeadersSpec.includes("extraHeaders"),
   "chrome: the header listener asks for extraHeaders (Cookie/Referer)");

// three finds in the same tick — a player asking for its manifest and its first
// fragments together. None may be lost to a read-modify-write race.
listeners.beforeRequest[0](req("media", "https://cdn/one.ts"));
listeners.beforeRequest[0](req("media", "https://cdn/two.ts"));
listeners.beforeRequest[0](req("media", "https://cdn/three.ts"));
await settle();
ok(["one.ts", "two.ts", "three.ts"].every((n) => found().includes("https://cdn/" + n)),
   "three finds in the same tick all survive");
ok(Number(badge[7]) === found().length && Number(badge[7]) >= 5,
   "the badge follows every find");

// 1b. the response teaches a find its size (v0.5.20): the range's total when
// the player asked for a slice — never the slice's own length.
listeners.headersReceived[0](req("media", "https://cdn/sized.mp4", {
  responseHeaders: [
    { name: "Content-Type", value: "video/mp4; charset=binary" },
    { name: "Content-Length", value: "65536" },
    { name: "Content-Range", value: "bytes 0-65535/9437184" },
  ],
}));
await settle();
let sized = ((store.tabMedia || {})[7] || []).find((m) => m.url === "https://cdn/sized.mp4");
ok(sized && sized.bytes === 9437184 && sized.mime === "video/mp4",
   "a 206's range total becomes the find's size and type");
listeners.headersReceived[0](req("media", "https://cdn/sized.mp4", {
  responseHeaders: [{ name: "Content-Range", value: "bytes 0-1023/65536" }],
}));
await settle();
sized = ((store.tabMedia || {})[7] || []).find((m) => m.url === "https://cdn/sized.mp4");
ok(sized && sized.bytes === 9437184,
   "a later, smaller range does not shrink a known size");
const gotSized = await new Promise((resolve) => {
  onMessage({ type: "getMedia", tabId: 7 }, {}, resolve);
});
ok(gotSized && gotSized.items.some((i) => i.url === "https://cdn/sized.mp4" &&
   i.bytes === 9437184 && i.mime === "video/mp4"),
   "the popup is told the size and the type");
listeners.headersReceived[0](req("media", "https://cdn/sized.mp4", {
  responseHeaders: [{ name: "Content-Length", value: "12" }],
}));
await settle();

// 1c. the same file fetched in byte slices (Facebook's reel player): one
// signed address with bytestart/byteend per range is ONE find, never twenty,
// and a slice's own length is never mistaken for the file's size (v0.5.21).
const fbBase = "https://cdn.fb/collapse.mp4?oh=11&oe=22&__gda__=33";
const fbSlice = (from, to) => fbBase + "&bytestart=" + from + "&byteend=" + to;
const fbHeaders = [
  { name: "Content-Type", value: "video/mp4" },
  { name: "Content-Length", value: "18431" },
];
const fbFinds = () => ((store.tabMedia || {})[7] || []).filter((m) => m.url === fbBase);
listeners.headersReceived[0](req("media", fbSlice(0, 18431), { responseHeaders: fbHeaders }));
await settle();
listeners.headersReceived[0](req("media", fbSlice(18432, 36863), { responseHeaders: fbHeaders }));
await settle();
ok(fbFinds().length === 1, "the slices of one file collapse to one find");
ok(fbFinds()[0] && fbFinds()[0].url.indexOf("bytestart") === -1 &&
   fbFinds()[0].url.indexOf("byteend") === -1,
   "…keyed by the signed address without the slice params");
ok(fbFinds()[0] && fbFinds()[0].bytes === 0,
   "…and 18431 is not taken for the file's size");
ok(fbFinds()[0] && fbFinds()[0].alt === fbSlice(0, 18431),
   "…with the first slice kept as the engine's fallback");
listeners.beforeRequest[0](req("media", fbSlice(36864, 55295)));
await settle();
ok(fbFinds().length === 1, "a third slice does not add a second find");

// the signature is over the query as the page sent it: cutting the two range
// params must not re-encode anything else (a value's "=" would become %3D and
// the CDN would answer 403 to its own address) (v0.5.21)
const signed = "https://cdn.fb/signed.mp4?efg=eyJhIjoiYiJ9==&_nc_oc=Adm:ab,cd" +
               "&bytestart=0&byteend=99";
listeners.headersReceived[0](req("media", signed, {
  responseHeaders: [{ name: "Content-Type", value: "video/mp4" },
                    { name: "Content-Length", value: "100" }],
}));
await settle();
const signedFind = ((store.tabMedia || {})[7] || [])
  .find((m) => m.url.indexOf("signed.mp4") !== -1);
ok(signedFind && signedFind.url ===
   "https://cdn.fb/signed.mp4?efg=eyJhIjoiYiJ9==&_nc_oc=Adm:ab,cd",
   "…and every other byte of the signed query is left alone");

// 1d. the true size is asked for once per address: a HEAD when the CDN
// answers one, and never again on the next slice (v0.5.21).
const probeUrl = "https://cdn.fb/probe.mp4?oh=1";
listeners.beforeRequest[0](req("media", probeUrl + "&bytestart=0&byteend=1023"));
listeners.headersReceived[0](req("media", probeUrl + "&bytestart=0&byteend=1023", {
  responseHeaders: [{ name: "Content-Type", value: "video/mp4" },
                    { name: "Content-Length", value: "1024" }],
}));
await settle();
await settle();
const probed = () => ((store.tabMedia || {})[7] || []).find((m) => m.url === probeUrl);
ok(probed() && probed().bytes === 5242880,
   "the probe learns the file's true size from the CDN");
ok(headCalls.length === 1, "…and the address is probed once, not per slice");
listeners.beforeRequest[0](req("media", probeUrl + "&bytestart=2048&byteend=4095"));
listeners.headersReceived[0](req("media", probeUrl + "&bytestart=2048&byteend=4095", {
  responseHeaders: [{ name: "Content-Type", value: "video/mp4" },
                    { name: "Content-Length", value: "2048" }],
}));
await settle();
await settle();
ok(headCalls.length === 1, "a later slice of the same file does not re-probe");
ok(probed() && probed().bytes === 5242880,
   "…and the known size never shrinks back to a slice");

// a CDN that will not answer HEAD is asked for one byte instead: the total in
// Content-Range is the same answer (v0.5.21)
const rangedUrl = "https://cdn.fb/ranged.mp4?oh=9";
listeners.beforeRequest[0](req("media", rangedUrl + "&bytestart=0&byteend=1023"));
await settle();
await settle();
const ranged = ((store.tabMedia || {})[7] || []).find((m) => m.url === rangedUrl);
ok(ranged && ranged.bytes === 7340032,
   "a refused HEAD falls back to the range total");

// 1e. an audio-only track is served as video/mp4 and says so only in `efg`:
// the find must be labelled audio, or the row offers silence as the video
// (v0.5.21).
const efgTag = Buffer.from(JSON.stringify({ vencode_tag: "dash_ln_heaac_vbr3_audio" }))
  .toString("base64url");
const efgUrl = "https://cdn.fb/track.m4a?efg=" + efgTag;
listeners.headersReceived[0](req("media", efgUrl + "&bytestart=0&byteend=9999", {
  responseHeaders: [{ name: "Content-Type", value: "video/mp4" },
                    { name: "Content-Length", value: "10000" }],
}));
await settle();
const track = ((store.tabMedia || {})[7] || []).find((m) => m.url === efgUrl);
ok(track && track.mime === "audio/mp4",
   "an efg audio tag labels the find audio/mp4, not video/mp4");
const gotAlt = await new Promise((resolve) => {
  onMessage({ type: "getMedia", tabId: 7 }, {}, resolve);
});
const fbItem = gotAlt && gotAlt.items.find((i) => i.url === fbBase);
ok(fbItem && fbItem.alt === fbSlice(0, 18431),
   "getMedia hands the popup the slice fallback with the find");
ok(gotAlt && gotAlt.items.every((i) => typeof i.alt === "string"),
   "…and every item says alt, empty when it has none");

// 1f. a scroll leaves old videos behind: a find past the window is dropped
// when the next one arrives, so the list is the last few minutes, not the
// session (v0.5.23)
store.tabMedia = { 19: [
  { url: "https://cdn/stale.mp4", foundAt: Date.now() - 25 * 60 * 1000,
    via: "network", mime: "video/mp4", bytes: 1024 },
] };
listeners.beforeRequest[0]({ tabId: 19, type: "media", url: "https://cdn/fresh.mp4" });
await settle();
const nineteen = ((store.tabMedia || {})[19] || []).map((m) => m.url);
ok(!nineteen.includes("https://cdn/stale.mp4") && nineteen.includes("https://cdn/fresh.mp4"),
   "a find older than the window does not survive the next one");
delete store.tabMedia[19];

// 2. the pattern list is the engine's
ok(fetchCalls.some((c) => c.url.endsWith("/sniff/patterns")),
   "the engine's pattern list is fetched at start");
await settle();
listeners.beforeRequest[0](req("xmlhttprequest", "https://cdn/thing.xyz?t=1"));
await settle();
ok(found().includes("https://cdn/thing.xyz?t=1"),
   "after the fetch, an extension the fallback does not know (.xyz) is a find");

// 3. ranking: the popup asks the engine and gets its answer back
const ranked = await new Promise((resolve) => {
  const keep = onMessage({ type: "rank", items: [{ url: "https://cdn/x.m3u8" }] }, {}, resolve);
  ok(keep === true, "the message handler answers asynchronously");
});
const rankCall = fetchCalls.find((c) => c.url.endsWith("/sniff/rank"));
ok(rankCall && rankCall.opts.method === "POST", "rank is a POST to /sniff/rank");
ok(rankCall && JSON.parse(rankCall.opts.body).urls[0] === "https://cdn/x.m3u8",
   "with the finds' URLs");
ok(rankCall && String(rankCall.opts.headers.Authorization).startsWith("Bearer"),
   "and the engine token");
ok(ranked && ranked.items && ranked.items[0].kind === "manifest",
   "the engine's answer reaches the popup");

// 4. a restart must not lose the engine's list: the day-long cache timer must
// not outlive the regex it cached (MV3 workers die constantly)
store.patterns = ["mp4", "m3u8", "ts", "xyz"];
store.patternsAt = Date.now();          // fresh — so no re-fetch is due
fetchCalls.length = 0;
listeners.beforeRequest.length = 0;
listeners.beforeSendHeaders.length = 0;
listeners.headersReceived.length = 0;
onRemoved = [];
onUpdated = [];
load();                                  // a fresh service-worker generation
await settle();
ok(!fetchCalls.some((c) => c.url.endsWith("/sniff/patterns")),
   "a restarted worker does not re-fetch a fresh pattern list");
listeners.beforeRequest[0](req("xmlhttprequest", "https://cdn/after-restart.xyz"));
await settle();
ok(found().includes("https://cdn/after-restart.xyz"),
   "…and still knows the engine's extensions after the restart");

// 5. headers for a URL only its *response* proves is media: held in memory,
// committed on proof — a guarded stream 403s without them
listeners.beforeSendHeaders[0](req("xmlhttprequest", "https://cdn/liar",
  { requestHeaders: sent }));
ok(!(store.reqHeaders || {})["https://cdn/liar"],
   "nothing is stored before the response proves it is media");
listeners.headersReceived[0](req("xmlhttprequest", "https://cdn/liar", {
  responseHeaders: [{ name: "Content-Type", value: "video/mp4" }],
}));
await settle();
const liar = (store.reqHeaders || {})["https://cdn/liar"];
ok(liar && liar.headers.cookie === "sid=1",
   "the held headers are committed once the response is media");
listeners.beforeSendHeaders[0](req("xmlhttprequest", "https://cdn/json",
  { requestHeaders: sent }));
listeners.headersReceived[0](req("xmlhttprequest", "https://cdn/json", {
  responseHeaders: [{ name: "Content-Type", value: "application/json" }],
}));
await settle();
ok(!(store.reqHeaders || {})["https://cdn/json"],
   "and a non-media response leaves nothing behind");

// 6. closing a tab must not resurrect its finds, nor wipe another tab's
const tab8 = { tabId: 8, type: "media", url: "https://cdn/tab8" };
listeners.beforeRequest[0](tab8);
await settle();
onRemoved[0](7);
await settle();
ok(found().length === 0, "a closed tab's finds are gone");
ok(((store.tabMedia || {})[8] || []).some((m) => m.url === "https://cdn/tab8"),
   "another tab's finds survive it");

// 7. walking the same tab to a new page empties the old list: finds belong to
// the page that asked for them. Reported live (2026-10-02): a tab moved from
// one video to the next, and the chooser still offered the old streams.
listeners.beforeRequest[0]({ tabId: 9, type: "media", url: "https://cdn/old-page" });
await settle();
ok(((store.tabMedia || {})[9] || []).length === 1, "a page's find is kept");
onUpdated[0](9, { status: "loading" });            // same page reloading
await settle();
ok(((store.tabMedia || {})[9] || []).length === 1,
   "a status-only update (the same page reloading) keeps the list");
onUpdated[0](9, { url: "https://newsite/watch?v=next" });
await settle();
ok(((store.tabMedia || {})[9] || []).length === 0, "navigating a tab empties its finds");
ok((badge[9] || "") === "", "…and clears the tab badge with it");
listeners.beforeRequest[0]({ tabId: 9, type: "media", url: "https://cdn/new-page" });
await settle();
ok(((store.tabMedia || {})[9] || []).map((m) => m.url).join() === "https://cdn/new-page",
   "…and the new page collects its own");
ok(badge[9] === "1", "…with a fresh count on the badge");

// 5. right-click → Download with suravidl (v0.40.7): the menu exists after a
// worker restart, and the deepest thing under the cursor is what gets handed
// over — a video element beats its wrapping link beats the page
ok(menusMade.some((m) => m.id === "suravidl-download"
   && (m.contexts || []).includes("video") && (m.contexts || []).includes("link")
   && (m.contexts || []).includes("audio") && (m.contexts || []).includes("page")),
   "the context menu is installed for links, video, audio, and pages");
ok(listeners.menuClicks.length >= 1, "…with its click listened for");
const clickMenu = (info, tab) =>
  listeners.menuClicks[listeners.menuClicks.length - 1](info, tab);
fetchCalls.length = 0;
await clickMenu({ srcUrl: "https://cdn/vid.mp4", linkUrl: "https://site/wrap",
                  pageUrl: "https://site/p" }, { url: "https://site/p" });
let mCall = fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
ok(mCall && JSON.parse(mCall.opts.body).url === "https://cdn/vid.mp4",
   "a video right-click hands over the video itself");
ok(mCall && JSON.parse(mCall.opts.body).tab_url === "https://site/p",
   "…with the page as its tab");
fetchCalls.length = 0;
await clickMenu({ linkUrl: "https://cdn/linked.m3u8", pageUrl: "https://site/p" },
                { url: "https://site/p" });
mCall = fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
ok(mCall && JSON.parse(mCall.opts.body).url === "https://cdn/linked.m3u8",
   "a link right-click hands over the link");
fetchCalls.length = 0;
await clickMenu({ pageUrl: "https://site/watch" }, { url: "https://site/watch" });
mCall = fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
ok(mCall && JSON.parse(mCall.opts.body).url === "https://site/watch",
   "a page right-click hands over the page's own address");

// — v0.5.12: a reddit-style share link resolves before it is sent. The
// browser itself saw the redirect when the user opened the link; the next
// send of that same link uses the canonical address, never the /s/ trap —
listeners.beforeRedirect[0]({
  url: "https://www.reddit.com/r/x/s/AbC123",
  redirectUrl: "https://www.reddit.com/r/x/comments/abc123/the_thread/",
});
await settle();
fetchCalls.length = 0;
await clickMenu({ linkUrl: "https://www.reddit.com/r/x/s/AbC123", pageUrl: "https://site/p" },
                { url: "https://site/p" });
mCall = fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
ok(mCall && JSON.parse(mCall.opts.body).url ===
   "https://www.reddit.com/r/x/comments/abc123/the_thread/",
   "a share link is handed over resolved, not as the /s/ trap");

// …and a share link the browser never visited resolves through the fetch
// (Chrome exempts extension fetches holding host permissions)
const fresh = await new Promise((resolve) => {
  const keep = onMessage({ type: "sendToEngine",
                           url: "https://www.reddit.com/r/y/s/Zz9" }, {}, resolve);
  ok(keep === true, "sendToEngine answers asynchronously");
});
ok(!!fresh, "sendToEngine completes for a share link");
const sCall = fetchCalls.filter((c) => c.url.endsWith("/jobs")).pop();
ok(sCall && JSON.parse(sCall.opts.body).url ===
   "https://www.reddit.com/r/y/comments/zzz9/followed/",
   "…and a fresh share link rides the fetch's canonical address");

// 6. the popup's quick door for several finds (v0.40.7): one batch call to
// the engine's own batch endpoint — /jobs/batch, never N single jobs
// v0.43.2: the batch rides each find's captured headers like the single
// quick door does — seed one and watch it come through keyed by URL
store.reqHeaders = { "https://cdn/a.mp4": { headers: { Referer: "https://site/" } } };
const batched = await new Promise((resolve) => {
  const keep = onMessage({ type: "sendBatch",
                           urls: ["https://cdn/a.mp4", "https://cdn/b.mp4"] }, {}, resolve);
  ok(keep === true, "sendBatch answers asynchronously");
});
const batchCall = fetchCalls.filter((c) => c.url.endsWith("/jobs/batch")).pop();
ok(batchCall && batchCall.opts.method === "POST", "the batch is a POST to /jobs/batch");
ok(batchCall && JSON.parse(batchCall.opts.body).urls.length === 2,
   "carrying every ticked find");
ok(batchCall && String(batchCall.opts.headers.Authorization).startsWith("Bearer"),
   "…with the engine token");
const batchBody = batchCall && JSON.parse(batchCall.opts.body);
ok(batchBody && batchBody.headers_by_url &&
   batchBody.headers_by_url["https://cdn/a.mp4"].Referer === "https://site/",
   "the captured headers ride the batch, keyed by URL");
ok(batchBody && !batchBody.headers_by_url["https://cdn/b.mp4"],
   "links with nothing captured stay out of the map");
ok(batched && batched.ok && batched.queued === 2,
   "the engine's own count comes back to the popup");

// — the Firefox flavor -------------------------------------------------------
// Measured on Firefox 157 while the AMO-listed 0.5.2 build was broken:
// `chrome.*` is a callback-only shim (tabs.query / sendMessage /
// storage.local.get return undefined there without a callback — not
// promises), `browser.*` returns promises, and an `extraInfoSpec` value
// Firefox does not know is a thrown TypeError, not a no-op. That throw killed
// the shipped background script mid-load (line 146) and took the popup's
// message port with it — nothing ever worked. This section runs the same
// source against a stub shaped like the real thing, so the class cannot come
// back silently.
{
  const ff = {
    listeners: { beforeRequest: [], beforeSendHeaders: [], headersReceived: [],
                 beforeRedirect: [] },
    spec: null, store: {}, badge: {}, fetchCalls: [], onRemoved: [], onUpdated: [], onMessage: null,
    jobsStatus: 200, handoffStatus: 200, healthOk: true, enginePort: 0,
    batchStatus: 200, batchSkipped: false, jobsList: null, jobsListStatus: 200,
  };
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const readStore = (defaults) => {
    const out = { ...defaults };
    for (const k of Object.keys(defaults)) if (k in ff.store) out[k] = ff.store[k];
    return out;
  };
  const sendToBg = (msg) => new Promise((resolve) => {
    if (!ff.onMessage) return resolve(undefined);
    const keep = ff.onMessage(msg, {}, resolve);
    if (!keep) resolve(undefined);
  });

  // the callback-only namespace
  const chromeStub = {
    action: { setBadgeText: ({ tabId, text }) => (ff.badge[tabId] = text) },
    storage: { local: {
      get(defaults, cb) {
        if (typeof cb !== "function") return undefined;   // measured: no promise
        Promise.resolve().then(() => cb(readStore(defaults)));
      },
      set(obj, cb) {
        Object.assign(ff.store, clone(obj));              // measured: the write happens
        if (typeof cb === "function") Promise.resolve().then(cb);
      },
    } },
    webRequest: {
      OnBeforeSendHeadersOptions: { REQUESTHEADERS: "requestHeaders", BLOCKING: "blocking" },
      onBeforeRequest: { addListener: (fn) => ff.listeners.beforeRequest.push(fn) },
      onBeforeSendHeaders: {
        addListener: (fn, _filter, spec) => {
          for (const s of spec || []) {
            if (s !== "requestHeaders" && s !== "blocking") {
              throw new Error('Type error for parameter extraInfoSpec (Invalid enumeration value "' + s + '")');
            }
          }
          ff.spec = spec;
          ff.listeners.beforeSendHeaders.push(fn);
        },
      },
      onHeadersReceived: { addListener: (fn) => ff.listeners.headersReceived.push(fn) },
      onBeforeRedirect: { addListener: (fn) => ff.listeners.beforeRedirect.push(fn) },
    },
    tabs: {
      onRemoved: { addListener: (fn) => ff.onRemoved.push(fn) },
      onUpdated: { addListener: (fn) => ff.onUpdated.push(fn) },
      query(_q, cb) {
        if (typeof cb === "function") Promise.resolve().then(() => cb([{ id: 7 }]));
        return undefined;                                  // measured: no promise
      },
    },
    runtime: {
      onMessage: { addListener: (fn) => (ff.onMessage = fn) },
      sendMessage(_m, cb) {
        if (typeof cb === "function") Promise.resolve().then(() => cb({}));
        return undefined;                                  // measured: no promise
      },
      openOptionsPage() {},
    },
  };
  // the promise namespace — Firefox's canonical menus live here, NOT on
  // chrome.* (measured: chrome.contextMenus is not a Firefox alias)
  const ffMenus = { made: [], clicks: [] };
  const browserStub = {
    storage: { local: {
      get: (defaults) => Promise.resolve(readStore(defaults)),
      set: (obj) => { Object.assign(ff.store, clone(obj)); return Promise.resolve(); },
    } },
    tabs: { query: () => Promise.resolve([{ id: 7 }]) },
    runtime: { sendMessage: sendToBg, openOptionsPage() {} },
    menus: {
      create: (props, cb) => { ffMenus.made.push(props); if (cb) cb(); return Promise.resolve(); },
      removeAll: (cb) => { if (cb) cb(); return Promise.resolve(); },
      onClicked: { addListener: (fn) => ffMenus.clicks.push(fn) },
    },
  };

  const saved = { chrome: globalThis.chrome, browser: globalThis.browser,
                  fetch: globalThis.fetch, document: globalThis.document };
  globalThis.chrome = chromeStub;
  globalThis.browser = browserStub;
  globalThis.fetch = async (url, opts = {}) => {
    ff.fetchCalls.push({ url, opts });
    if (/reddit\.com\/.*\/s\//i.test(url)) {
      // measured: Firefox background fetches are CORS-bound — a redirect
      // fetch to another origin cannot read the answer there
      throw new Error("TypeError: NetworkError when attempting to fetch resource.");
    }
    if (url.endsWith("/sniff/patterns")) {
      return { ok: true, json: async () => ({ ext: ["mp4", "m3u8", "ts"] }) };
    }
    if (url.endsWith("/sniff/rank")) {
      return { ok: true, json: async () => ({ items: [], hidden: 0 }) };
    }
    if (url.endsWith("/health")) {
      // the engine's port ladder: ff.enginePort narrows which rung answers
      const port = (/127\.0\.0\.1:(\d+)\//.exec(url) || [])[1] || "8787";
      if (ff.healthOk && (!ff.enginePort || String(ff.enginePort) === port)) {
        return { ok: true, status: 200, json: async () => ({ ok: true, version: "0.39.2" }) };
      }
      throw new Error("connect ECONNREFUSED " + url);
    }
    if (url.endsWith("/handoff")) {
      if (ff.handoffStatus === 200) {
        return { ok: true, status: 200,
                 json: async () => ({ ok: true, id: "h1", status: "probing" }) };
      }
      return { ok: false, status: ff.handoffStatus, text: async () => '{"detail":"gone"}' };
    }
    if (url.endsWith("/jobs/batch")) {
      if (ff.batchStatus === 401) {
        return { ok: false, status: 401, text: async () => '{"detail":"unauthorized"}' };
      }
      if (ff.batchSkipped) {
        return { ok: true, status: 200,
                 json: async () => ({ jobs: [], skipped: [{ url: "u0", error: "not a link" }] }) };
      }
      const list = (JSON.parse(opts.body || "{}").urls) || [];
      return { ok: true, status: 200,
               json: async () => ({ jobs: list.map((_, i) => ({ id: "B" + i })), skipped: [] }) };
    }
    if (url.endsWith("/jobs")) {
      if ((opts.method || "GET") === "GET") {
        if (ff.jobsListStatus === 401) {
          return { ok: false, status: 401, text: async () => '{"detail":"unauthorized"}' };
        }
        return { ok: true, status: 200, json: async () => ({ jobs: ff.jobsList || [] }) };
      }
      if (ff.jobsStatus === 200) {
        return { ok: true, status: 200, json: async () => ({ id: "J7" }) };
      }
      return { ok: false, status: ff.jobsStatus, text: async () => '{"detail":"unauthorized"}' };
    }
    return { ok: false, status: 404, text: async () => "nope" };
  };

  let ffLoaded = true;
  try { new Function(src)(); }
  catch (e) {
    ffLoaded = false;
    failures.push("firefox: the background script must load without throwing (" + e + ")");
  }
  if (ffLoaded) {
    ok(ff.listeners.beforeSendHeaders.length === 1,
       "firefox: the header listener registers instead of throwing");
    ok(Array.isArray(ff.spec) && !ff.spec.includes("extraHeaders"),
       "firefox: the spec never asks for a value Firefox refuses");
    ok(ff.onMessage !== null, "firefox: the popup's message port exists");

    ff.listeners.beforeRequest[0]({ tabId: 7, type: "media", url: "https://cdn/ff.mp4" });
    await settle();
    const got = await sendToBg({ type: "getMedia", tabId: 7 });
    ok(got && got.items && got.items.length === 1, "firefox: getMedia answers with the find");

    // — v0.5.13: a content-script report lands in the tab's find list with
    //   its via; a report without a real sender tab is refused —
    const pf = await new Promise((resolve) =>
      ff.onMessage({ type: "pageFind", url: "https://cdn/from-player/noext", via: "player" },
                   { tab: { id: 12 } }, resolve));
    await settle();
    ok(pf && pf.ok, "firefox: a page-side find is accepted");
    ok(((ff.store.tabMedia || {})[12] || []).some(
      (m) => m.url === "https://cdn/from-player/noext" && m.via === "player"),
      "firefox: …stored, with how it was found");
    const forged = await new Promise((resolve) =>
      ff.onMessage({ type: "pageFind", url: "https://cdn/forged" }, {}, resolve));
    await settle();
    ok(forged && forged.ok === false &&
       !Object.values(ff.store.tabMedia || {}).some(
         (l) => (l || []).some((m) => m.url === "https://cdn/forged")),
       "firefox: a report without a sender tab is refused");

    await sendToBg({ type: "rank", items: [{ url: "https://cdn/ff.mp4" }] });
    ok(ff.fetchCalls.some((c) => c.url.endsWith("/sniff/rank")),
       "firefox: rank reaches the engine through the promise namespace");

    // the popup's handoff (v0.39.0): the find plus its captured headers go to
    // /handoff, the engine probes them itself and the app opens on the format
    // list — the quality choice lives there, not in this popup
    const st = await sendToBg({ type: "engineState" });
    ok(st && st.ok && st.version === "0.39.2", "firefox: engineState reads /health");
    ff.store.reqHeaders = { "https://cdn/ff.mp4": { headers: { cookie: "sid=1" } } };
    const hand = await sendToBg({ type: "sendHandoff", url: "https://cdn/ff.mp4",
                                  urls: ["https://cdn/ff.mp4"], tabUrl: "https://site/watch" });
    ok(hand && hand.ok && hand.mode === "handoff" && hand.handoff.id === "h1",
       "firefox: sendHandoff returns the engine's handoff");
    const hCall = ff.fetchCalls.find((c) => c.url.endsWith("/handoff"));
    ok(hCall && hCall.opts.method === "POST", "firefox: …as a POST to /handoff");
    const hBody = hCall && JSON.parse(hCall.opts.body);
    ok(hBody && hBody.url === "https://cdn/ff.mp4" && hBody.tab_url === "https://site/watch",
       "firefox: the handoff carries the stream and its tab");
    ok(hBody && hBody.headers && hBody.headers.cookie === "sid=1",
       "firefox: …and the captured request headers");
    ok(String(hCall.opts.headers.Authorization).startsWith("Bearer"),
       "firefox: …with the token");

    // right-click → Download with suravidl (v0.40.7), through the promise
    // namespace — this must not depend on chrome.contextMenus existing
    ok(ffMenus.made.some((m) => m.id === "suravidl-download"),
       "firefox: the context menu installs through browser.menus");
    ff.fetchCalls.length = 0;
    await ffMenus.clicks[ffMenus.clicks.length - 1]({ srcUrl: "https://cdn/ffmenu.mp4" },
                                                    { url: "https://ffsite/p" });
    const fmCall = ff.fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
    ok(fmCall && JSON.parse(fmCall.opts.body).url === "https://cdn/ffmenu.mp4",
       "firefox: a video right-click hands over the video");

    // the popup's quick door for several finds (v0.40.7): one batch call,
    // answered per-link; all-skipped and 401 both stay speakable
    const fB = await sendToBg({ type: "sendBatch", urls: ["u1", "u2", "u3"] });
    ok(fB && fB.ok && fB.queued === 3, "firefox: sendBatch queues every find");
    ff.batchSkipped = true;
    const fSkip = await sendToBg({ type: "sendBatch", urls: ["u1"] });
    ok(fSkip && !fSkip.ok && /skipped/.test(fSkip.error || ""),
       "firefox: a batch where every link was skipped is a failure to report");
    ff.batchSkipped = false;
    ff.batchStatus = 401;
    const fDenied = await sendToBg({ type: "sendBatch", urls: ["u1"] });
    ok(fDenied && !fDenied.ok && /token/i.test(fDenied.error || ""),
       "firefox: a 401 on the batch says the token is the problem");
    ff.batchStatus = 200;

    ff.handoffStatus = 404;
    const older = await sendToBg({ type: "sendHandoff", url: "https://cdn/ff.mp4" });
    ok(older && older.ok && older.mode === "job" && older.job.id === "J7",
       "firefox: an engine without /handoff falls back to the old one-shot job");
    ff.handoffStatus = 200;
    // the app can move down the port ladder when its preferred port was
    // busy at launch: the extension walks the same ladder instead of
    // declaring a running app dead (the reported bug)
    ff.enginePort = 8789;
    ff.fetchCalls.length = 0;
    const stPort = await sendToBg({ type: "engineState" });
    ok(stPort && stPort.ok && /:8789/.test(stPort.url || ""),
       "firefox: engineState finds the engine on a neighbouring port");
    ok(ff.store.discoveredUrl === "http://127.0.0.1:8789",
       "firefox: …and remembers where it found it");
    const hPort = await sendToBg({ type: "sendHandoff", url: "https://cdn/ff.mp4",
                                   urls: [], tabUrl: "https://site/x" });
    const hPortCall = ff.fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
    ok(hPort && hPort.ok && hPortCall && /:8789/.test(hPortCall.url),
       "firefox: the handoff follows the discovered port");
    ff.enginePort = 0;

    ff.healthOk = false;
    ff.fetchCalls.length = 0;
    const stDown = await sendToBg({ type: "engineState" });
    ok(stDown && !stDown.ok, "firefox: a dead engine reads as not running");
    ok(ff.fetchCalls.filter((c) => c.url.endsWith("/health")).length >= 5,
       "firefox: …after actually walking the ladder, not assuming");
    ff.healthOk = true;

    ff.store.engineUrl = "http://127.0.0.1:8787";
    ff.store.engineToken = "t";
    const sent = await sendToBg({ type: "sendToEngine", url: "https://cdn/ff.mp4" });
    ok(sent && sent.ok && sent.job.id === "J7", "firefox: the handoff returns the engine's job");
    const jobCall = ff.fetchCalls.find((c) => c.url.endsWith("/jobs"));
    ok(jobCall && jobCall.opts.method === "POST", "firefox: …as a POST to /jobs");
    ok(jobCall && String(jobCall.opts.headers.Authorization).startsWith("Bearer"),
       "firefox: with the token");

    ff.jobsStatus = 401;
    const denied = await sendToBg({ type: "sendToEngine", url: "https://cdn/ff.mp4" });
    ok(denied && !denied.ok && /token/i.test(denied.error || ""),
       "firefox: a 401 says the token is the problem");

    // — v0.5.12: the share-link map resolves here too; an unmapped link
    //   passes through unchanged (Firefox's background fetches are CORS-
    //   bound, so the map — filled by the browser's own redirects — is the
    //   path, and a miss must never mangle the link) —
    ff.listeners.beforeRedirect[0]({
      url: "https://www.reddit.com/r/x/s/AbC123",
      redirectUrl: "https://www.reddit.com/r/x/comments/abc123/the_thread/",
    });
    await settle();
    const fShare = await sendToBg({ type: "sendHandoff",
      url: "https://www.reddit.com/r/x/s/AbC123", urls: [],
      tabUrl: "https://www.reddit.com/r/x/s/AbC123" });
    const fShareCall = ff.fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
    const fShareBody = fShareCall && JSON.parse(fShareCall.opts.body);
    ok(fShare && fShare.ok && fShareBody &&
       fShareBody.url === "https://www.reddit.com/r/x/comments/abc123/the_thread/" &&
       fShareBody.tab_url === "https://www.reddit.com/r/x/comments/abc123/the_thread/",
       "firefox: a seen share redirect resolves the link and its tab");
    const fFresh = await sendToBg({ type: "sendHandoff",
      url: "https://www.reddit.com/r/never/s/Ww1", urls: [], tabUrl: "" });
    const fFreshCall = ff.fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
    ok(fFresh && fFresh.ok &&
       JSON.parse(fFreshCall.opts.body).url === "https://www.reddit.com/r/never/s/Ww1",
       "firefox: an unmapped share link passes through unchanged, never mangled");

    // — the mirror: recentJobs answers in the lean shape, newest first, the
    //   caveat note included —
    ff.jobsList = [
      { id: "m1", title: "clip", url: "https://cdn/a.mp4", status: "downloading",
        created_at: "2026-10-10T01:00:00Z", note: "" },
      { id: "m2", title: "reddit video", url: "https://cdn/b.mp4", status: "completed",
        created_at: "2026-10-10T02:00:00Z",
        note: "the thumbnail could not be embedded" },
    ];
    const rec = await sendToBg({ type: "recentJobs" });
    ok(rec && rec.ok && rec.jobs.length === 2 && rec.jobs[0].id === "m2",
       "firefox: recentJobs sorts newest-first");
    ok(rec && rec.jobs[0].note.indexOf("thumbnail") !== -1 && !("filepath" in rec.jobs[0]),
       "firefox: …with the note, in the lean shape");

    // and the popup script itself, against that same environment (v0.39.0:
    // a doorman — plain words, a chooser only when the page offered several
    // streams, and ONE handoff; the quality pick happens in the app)
    const el = (tag = "div") => ({
      tagName: tag, hidden: false, className: "", value: "", src: "",
      checked: false, disabled: false, name: "", type: "", onclick: null, children: [],
      classList: {
        _s: new Set(),
        add(...c) { for (const x of c) this._s.add(x); },
        remove(...c) { for (const x of c) this._s.delete(x); },
        contains(c) { return this._s.has(c); },
        toggle(c, on) { on ? this._s.add(c) : this._s.delete(c); },
      },
      setAttribute(n, v) { (this._attrs = this._attrs || {})[n] = String(v); },
      getAttribute(n) { return (this._attrs || {})[n] ?? null; },
      append(...kids) { this.children.push(...kids); },
      appendChild(k) { this.children.push(k); },
      querySelector(sel) {
        const find = (el) => {
          for (const c of el.children || []) {
            if (c.tagName === "input") return c;
            const deep = find(c);
            if (deep) return deep;
          }
          return null;
        };
        return sel.includes("input") ? find(this) : null;
      },
      _text: "",
      set textContent(v) { this._text = v; if (v === "") this.children = []; },
      get textContent() { return this._text; },
    });
    const ids = ["engine", "engineText", "found", "site", "favicon", "hostline",
                 "headline", "subline", "pickgroup", "streams", "foldline", "cards",
                 "cardhint", "send",
                 "empty", "down", "retry", "rescan", "quick", "status",
                 "optsLink", "ver", "allbtn", "recent", "recentList"];
    const mkNodes = () => {
      const nodes = {};
      for (const id of ids) nodes[id] = el();
      // mirrors popup.html: these start hidden and the script unhides them
      for (const id of ["found", "empty", "down", "pickgroup", "site", "favicon", "recent",
                        "cards", "cardhint"]) {
        nodes[id].hidden = true;
      }
      return nodes;
    };
    const installDom = (nodes) => {
      globalThis.document = {
        getElementById: (id) => {
          if (!ids.includes(id)) {
            failures.push("firefox: the popup asked for an id popup.html lacks (" + id + ")");
          }
          return nodes[id] || null;
        },
        createElement: (t) => el(t),
        querySelector: (sel) => {
          const m = /#([\w-]+)\s+input/.exec(sel);
          const inputs = [];
          const collect = (el) => {
            for (const c of el.children || []) {
              if (c.tagName === "input") inputs.push(c);
              collect(c);
            }
          };
          if (m && nodes[m[1]]) collect(nodes[m[1]]);
          return sel.includes(":checked")
            ? (inputs.find((i) => i.checked) || null)
            : (inputs[0] || null);
        },
      };
      return nodes;
    };
    let optsOpened = false;
    browserStub.runtime.openOptionsPage = () => (optsOpened = true);
    ff.jobsStatus = 200;

    // — one find: the plain flow —
    let nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("firefox: the popup script must load without throwing (" + e + ")");
    }
    await settle();
    await settle();
    ok(nodes.found.hidden === false && nodes.down.hidden === true,
       "firefox: with the engine up, the popup shows the found card");
    ok(nodes.engine.className.includes("ok") &&
       nodes.engineText.textContent === "engine ready",
       "firefox: the engine chip says ready");
    ok(nodes.headline.textContent === "Video found on this page",
       "firefox: one find reads as one video, in plain words");
    ok(nodes.pickgroup.hidden === true, "firefox: no chooser is forced for a single stream");
    await nodes.send.onclick();
    const pCall = ff.fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
    ok(pCall && JSON.parse(pCall.opts.body).url === "https://cdn/ff.mp4",
       "firefox: the button hands the find to the engine");
    ok(/✓ Sent — choose the quality in suravidl\./.test(nodes.status.textContent),
       "firefox: and says where the quality gets chosen");
    ok(nodes.send.disabled === true, "firefox: the handoff cannot be sent twice");

    // — the other door: quick download takes the best quality right away —
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("firefox: the popup reload must load without throwing (" + e + ")");
    }
    await settle();
    await settle();
    await nodes.quick.onclick();
    const qCall = ff.fetchCalls.filter((c) => c.url.endsWith("/jobs")).pop();
    const qBody = qCall && JSON.parse(qCall.opts.body);
    ok(qBody && qBody.url === "https://cdn/ff.mp4" && qBody.headers.cookie === "sid=1",
       "firefox: quick download queues the best quality with the captured headers");
    ok(!!qBody && !("fmt" in qBody),
       "firefox: …without a format, which is what \"best\" means to the engine");
    ok(/✓ Sent — suravidl is downloading it in best quality\./.test(nodes.status.textContent),
       "firefox: …and says the download has started");
    ok(nodes.send.disabled === true && nodes.quick.disabled === true,
       "firefox: neither door can be pressed twice");

    // — several finds: rows named, ordinals only when names collide, and
    //   the URL door on every row (v0.5.7) —
    ff.listeners.beforeRequest[0]({ tabId: 7, type: "media", url: "https://cdn/ff2.mp4" });
    await settle();
    ff.listeners.beforeRequest[0]({ tabId: 7, type: "media",
      url: "https://cdn/big-buck-bunny/1080p/master.m3u8?tok=x" });
    await settle();
    ff.listeners.beforeRequest[0]({ tabId: 7, type: "media",
      url: "https://cdn/other/Big.Buck.Bunny.2019.720p.mp4" });
    await settle();
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("firefox: the popup reload must load without throwing (" + e + ")");
    }
    await settle();
    await settle();
    ok(nodes.headline.textContent === "4 streams found on this page",
       "firefox: four finds read as four streams");
    ok(nodes.pickgroup.hidden === false && nodes.streams.children.length === 4,
       "firefox: …and offer a chooser");
    const rows = nodes.streams.children;
    const labelOf = (r) => r.children[0].children[1].textContent;
    // v0.5.20: newest first, and the tick is a recommendation — a manifest
    // outranks everything, because it is the whole stream.
    ok(rows[0].children[0].children[0].checked === true,
       "firefox: the recommended stream is pre-asked for");
    ok(labelOf(rows[0]) === "All qualities",
       "firefox: a master names the whole stream");
    ok(labelOf(rows[1]) === "Big Buck Bunny 2019 · 720p",
       "firefox: a real filename names the row, resolution kept");
    ok(labelOf(rows[2]) === "Stream 1" && labelOf(rows[3]) === "Stream 2",
       "firefox: identical rows still get ordinals");
    ok(rows[0].children[0].children[2] &&
       rows[0].children[0].children[2].textContent === "best",
       "firefox: …and the recommended row says why it is ticked");
    // the URL door: folded by default, unfolds the raw link, folds back
    ok(rows[0].children[2].hidden === true, "firefox: raw links start folded");
    rows[0].children[1].onclick();
    ok(rows[0].children[2].hidden === false &&
       rows[0].children[2].textContent === "https://cdn/big-buck-bunny/1080p/master.m3u8?tok=x",
       "firefox: the URL button unfolds the raw link");
    ok(rows[0].children[1].getAttribute("aria-expanded") === "true",
       "firefox: …and says it is open");
    rows[0].children[1].onclick();
    ok(rows[0].children[2].hidden === true, "firefox: and folds it back");
    rows[0].children[0].children[0].checked = false;
    rows[1].children[0].children[0].checked = true;
    await nodes.send.onclick();
    const p2 = ff.fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
    ok(JSON.parse(p2.opts.body).url === "https://cdn/other/Big.Buck.Bunny.2019.720p.mp4",
       "firefox: the chosen stream is the one handed over");

    // — v0.40.7: tick several, and the quick door takes them all in one
    //   call — the quality door keeps its single first-ticked pick —
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("firefox: the popup reload must load without throwing (" + e + ")");
    }
    await settle();
    await settle();
    const brows = nodes.streams.children;
    brows[1].children[0].children[0].checked = true;
    brows[2].children[0].children[0].checked = true;
    if (typeof brows[2].children[0].children[0].onchange === "function") {
      brows[2].children[0].children[0].onchange();
    }
    ok(String(nodes.quick.textContent).startsWith("Queue all 3"),
       "firefox: the quick door says how many it will take");
    ff.fetchCalls.length = 0;
    await nodes.quick.onclick();
    const bCallFF = ff.fetchCalls.filter((c) => c.url.endsWith("/jobs/batch")).pop();
    const bBodyFF = bCallFF && JSON.parse(bCallFF.opts.body);
    ok(bBodyFF && bBodyFF.urls.length === 3,
       "firefox: quick download queues every ticked find in one call");
    ok(bCallFF && String(bCallFF.opts.headers.Authorization).startsWith("Bearer"),
       "firefox: …with the token");
    ok(/✓ Sent — 3 downloading at best quality/.test(nodes.status.textContent),
       "firefox: …and says how many are downloading");

    // — select all: one press ticks every row, the door flips its label —
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("firefox: the popup reload must load without throwing (" + e + ")");
    }
    await settle();
    await settle();
    nodes.allbtn.onclick();
    ok(nodes.streams.children.every((r) => r.children[0].children[0].checked),
       "firefox: Select all ticks every row");
    ok(String(nodes.allbtn.textContent) === "Select none"
       || String(nodes.allbtn.getAttribute("aria-pressed")) === "true",
       "firefox: …and the door says what a second press will do");

    // — v0.5.20: one video's streams carry their sizes, the biggest is the
    //   tick, and an audio track is named as audio — (a second video on the
    //   page is the v0.5.22 card case below) —
    const now = Date.now();
    const MB = (n) => Math.round(n * 1048576);
    ff.store.tabMedia = { 7: [
      { url: "https://cdn/reel/a.m4a?x=1", foundAt: now - 1100,
        via: "network", mime: "audio/mp4", bytes: 950000 },
      { url: "https://cdn/reel/video.mp4?x=720", foundAt: now - 950,
        via: "network", mime: "video/mp4", bytes: MB(3) },
      { url: "https://cdn/reel/video.mp4?x=1080", foundAt: now - 700,
        via: "network", mime: "video/mp4", bytes: MB(9) },
    ] };
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("v0.5.20: the popup must load with sized finds (" + e + ")");
    }
    await settle();
    await settle();
    const srows = nodes.streams.children;
    ok(srows.length === 3,
       "v0.5.20: only the newest video's own streams are rows");
    ok(nodes.headline.textContent === "3 streams found on this page",
       "v0.5.20: …and one video's streams read as one video");
    ok(/· 9 MB$/.test(labelOf(srows[0])) && srows[0].children[0].children[0].checked,
       "v0.5.20: the biggest video carries its size, and is the tick");
    ok(srows[0].children[0].children[2] &&
       srows[0].children[0].children[2].textContent === "best",
       "v0.5.20: …and says why it is ticked");
    ok(/· 3 MB$/.test(labelOf(srows[1])),
       "v0.5.20: the smaller rendition says its size too");
    ok(labelOf(srows[2]) === "Audio · 928 KB",
       "v0.5.20: an audio track is named as audio, not as a video");
    ff.store.tabMedia = {};

    // — v0.5.21: a reel's audio track is named Audio even though the CDN
    //   typed it video/mp4, the whole file is the pick rather than an 18 KB
    //   leftover slice, and the slice address rides the handoff as a fallback —
    const fbNow = Date.now();
    ff.store.tabMedia = { 7: [
      { url: "https://cdn.fb/q/1?efg=x", foundAt: fbNow - 500,
        via: "network", mime: "audio/mp4", bytes: 980000, alt: "" },
      { url: "https://cdn.fb/s/2?oh=2", foundAt: fbNow - 600,
        via: "network", mime: "video/mp4", bytes: 18431,
        alt: "https://cdn.fb/s/2?oh=2&bytestart=0" },
      { url: "https://cdn.fb/clip.mp4?oh=1", foundAt: fbNow - 800,
        via: "network", mime: "video/mp4", bytes: 5242880,
        alt: "https://cdn.fb/clip.mp4?oh=1&bytestart=0" },
    ] };
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("v0.5.21: the popup must load with a reel's finds (" + e + ")");
    }
    await settle();
    await settle();
    const fbRows = nodes.streams.children;
    ok(fbRows.length === 3, "v0.5.21: the reel's file and its track are separate rows");
    ok(labelOf(fbRows[2]) === "Audio · 957 KB",
       "v0.5.21: an audio-only track reads Audio, not Video");
    ok(fbRows[2].children[0].children[0].checked === false,
       "v0.5.21: …and is never the tick");
    ok(fbRows[0].children[0].children[0].checked === true &&
       fbRows[0].children[0].children[2] &&
       fbRows[0].children[0].children[2].textContent === "best",
       "v0.5.21: the whole file is the pick, not the 18 KB slice");
    await nodes.send.onclick();
    const fbCall = ff.fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
    const fbBody = fbCall && JSON.parse(fbCall.opts.body);
    ok(fbBody && fbBody.urls.includes("https://cdn.fb/clip.mp4?oh=1"),
       "v0.5.21: the handoff carries the canonical address");
    ok(fbBody && fbBody.urls.includes("https://cdn.fb/clip.mp4?oh=1&bytestart=0"),
       "v0.5.21: …and the slice the player used, as a fallback");
    ff.store.tabMedia = {};

    // — v0.5.22: a feed holds several videos and nothing on the wire says
    //   which one is on screen, so the popup stops ticking one: a card per
    //   video, nothing chosen, and a click downloads THAT card's video —
    const cardNow = Date.now();
    ff.store.tabMedia = { 7: [
      { url: "https://cdn.fb/old.mp4?oh=7", foundAt: cardNow - 120000,
        via: "network", mime: "video/mp4", bytes: 3 * 1048576, alt: "" },
      { url: "https://cdn.fb/old.m4a?oh=6", foundAt: cardNow - 119000,
        via: "network", mime: "audio/mp4", bytes: 900000, alt: "" },
      { url: "https://cdn.fb/mid.mp4?oh=8", foundAt: cardNow - 60000,
        via: "network", mime: "video/mp4", bytes: 5 * 1048576, alt: "" },
      { url: "https://cdn.fb/new.mp4?oh=9", foundAt: cardNow - 500,
        via: "network", mime: "video/mp4", bytes: 8 * 1048576, alt: "" },
    ] };
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("v0.5.22: the popup must load with several videos (" + e + ")");
    }
    await settle();
    await settle();
    ok(nodes.cards.hidden === false && nodes.cards.children.length === 3,
       "v0.5.22: a feed shows one card per video, not a list of streams");
    ok(nodes.pickgroup.hidden === true && nodes.send.hidden === true &&
       nodes.quick.hidden === true,
       "v0.5.22: no checkbox chooser and no pre-chosen door");
    ok(nodes.headline.textContent === "3 videos found on this page" &&
       /newest find is often the next reel/.test(nodes.subline.textContent),
       "v0.5.22: …and the card says which one the newest find tends to be");
    const cards = nodes.cards.children;
    ok(/8 MB$/.test(cards[0].children[1].children[0].textContent),
       "v0.5.22: the newest card is first and carries its size");
    const acts0 = cards[0].children[1].children[1];
    ok(acts0.children[0].textContent === "Download",
       "v0.5.22: each card names its own action");
    ok(acts0.children[1].textContent === "Quality",
       "v0.5.25: …and keeps the app's quality door beside it");
    ok(nodes.streams.children.length === 0,
       "v0.5.22: nothing is ticked on the user's behalf — there is no list to tick");
    ok(nodes.cardhint.hidden === false,
       "v0.5.23: …and the list says what to do when this video is not in it");
    ff.fetchCalls.length = 0;
    await cards[2].children[1].children[1].children[0].onclick();
    const cardCall = ff.fetchCalls.filter((c) => c.url.endsWith("/jobs")).pop();
    const cardBody = cardCall && JSON.parse(cardCall.opts.body);
    ok(cardBody && cardBody.url === "https://cdn.fb/old.mp4?oh=7",
       "v0.5.22: clicking a card downloads that video, the one the person chose");
    ok(cardBody && cardBody.audio_url === "https://cdn.fb/old.m4a?oh=6",
       "v0.5.24: …with its own soundtrack, so the file is not silent");

    // the other door, on the same card: the card's video goes to the app's
    // chooser, not somebody else's (v0.5.25)
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("v0.5.25: the popup must load for the quality door (" + e + ")");
    }
    await settle();
    await settle();
    ff.fetchCalls.length = 0;
    await nodes.cards.children[1].children[1].children[1].children[1].onclick();
    const qualCall = ff.fetchCalls.filter((c) => c.url.endsWith("/handoff")).pop();
    ok(qualCall && JSON.parse(qualCall.opts.body).url === "https://cdn.fb/mid.mp4?oh=8",
       "v0.5.25: Choose quality hands over the card's own video");
    ff.store.tabMedia = {};

    // — the popup mirrors the engine's jobs, notes and all (v0.5.12) —
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("firefox: the popup reload must load without throwing (" + e + ")");
    }
    await settle();
    await settle();
    ok(nodes.recent.hidden === false && nodes.recentList.children.length === 3,
       "firefox: the mirror lists the recent jobs");
    ok(nodes.recentList.children[0].children[2].textContent === "Done" &&
       nodes.recentList.children[2].children[2].textContent === "Downloading",
       "firefox: …newest first, in the app's words");
    ok(String(nodes.recentList.children[1].textContent).indexOf("thumbnail") !== -1,
       "firefox: …and a caveat note rides under its job");

    // — a tab walking to a new page resets its list (same bug, this flavor) —
    ff.listeners.beforeRequest[0]({ tabId: 8, type: "media", url: "https://cdn/ff-old-page" });
    await settle();
    let ffGot = await sendToBg({ type: "getMedia", tabId: 8 });
    ok(ffGot.items.length === 1, "firefox: a find is kept while its page is open");
    ff.onUpdated[0](8, { url: "https://newsite/watch?v=2" });
    await settle();
    ffGot = await sendToBg({ type: "getMedia", tabId: 8 });
    ok(ffGot.items.length === 0, "firefox: navigating the tab empties its finds");

    // — engine down: one thing to fix, not a list you cannot send —
    ff.healthOk = false;
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("firefox: the popup reload must load without throwing (" + e + ")");
    }
    await settle();
    await settle();
    ok(nodes.down.hidden === false && nodes.found.hidden === true,
       "firefox: a dead engine shows exactly one thing to fix");
    ff.healthOk = true;

    // — nothing playing: the plate offers its own way out —
    ff.store.tabMedia = {};
    nodes = installDom(mkNodes());
    try { new Function(popupFull)(); }
    catch (e) {
      failures.push("firefox: the popup reload must load without throwing (" + e + ")");
    }
    await settle();
    await settle();
    ok(nodes.empty.hidden === false && nodes.found.hidden === true,
       "firefox: an empty page shows the nothing-playing plate");
    ok(nodes.rescan !== null, "firefox: …with its Check again button");

    nodes.optsLink.onclick({ preventDefault() {} });
    ok(optsOpened, "firefox: the options link opens the options page");
  }

  globalThis.chrome = saved.chrome;
  globalThis.browser = saved.browser;
  globalThis.fetch = saved.fetch;
  globalThis.document = saved.document;
}


// — v0.5.13: the page side. The content script reads the PLAYER itself — a
//   source the player pointed at is evidence whatever it looks like, even
//   when the element never requested anything; blob/MSE sources are proof of
//   streaming, not finds; and the scan recovers what ran before it loaded —
{
  const pageSrc = readFileSync(join(here, "pagefind.js"), "utf8");
  const realSetTimeout = setTimeout;
  const runPage = ({ els = [], entries = [], patterns = ["mp4", "m3u8"] } = {}) => {
    const sent = [];
    const observers = [];
    const doc = {
      querySelectorAll: (sel) =>
        els.filter((e) => sel.toLowerCase().includes(e.tagName.toLowerCase())),
      documentElement: { node: true },
    };
    class FakeMO { constructor(cb) { observers.push(cb); } observe() {} }
    const api = {
      runtime: { sendMessage: (m) => sent.push(m) },
      storage: { local: { get: () => Promise.resolve({ patterns }) } },
    };
    new Function("chrome", "browser", "document", "location", "performance",
      "MutationObserver", "URL", "setTimeout", "addEventListener", pageSrc)(
      api, undefined, doc, { href: "https://site/watch" },
      { getEntriesByType: () => entries }, FakeMO, URL,
      (fn) => realSetTimeout(fn, 0), () => {});
    return { sent, observers };
  };

  const els = [
    { tagName: "VIDEO", currentSrc: "https://cdn/from-player-noext", src: "" },
    { tagName: "VIDEO", currentSrc: "blob:https://site/abcd", src: "" },
    { tagName: "SOURCE", currentSrc: "", src: "/relative/stream.mp4" },
  ];
  const r = runPage({
    els,
    entries: [
      { name: "https://cdn/timeline.m3u8?tok=1", initiatorType: "fetch" },
      { name: "https://cdn/logo.png", initiatorType: "img" },
      { name: "https://cdn/timeline-noext", initiatorType: "video" },
    ],
  });
  await settle();
  ok(r.sent.length && r.sent.every((m) => m.type === "pageFind"),
     "page side: reports are pageFind messages");
  ok(r.sent.some((m) => m.url === "https://cdn/from-player-noext" && m.via === "player"),
     "page side: a player source is reported whatever it looks like");
  ok(!r.sent.some((m) => /^blob:/.test(m.url)),
     "page side: a blob source is not a find");
  ok(r.sent.some((m) => m.url === "https://site/relative/stream.mp4"),
     "page side: a relative source resolves against the page");
  ok(r.sent.some((m) => m.url === "https://cdn/timeline.m3u8?tok=1" && m.via === "scan"),
     "page side: the timeline scan reports a pattern match");
  ok(r.sent.some((m) => m.url === "https://cdn/timeline-noext" && m.via === "player"),
     "page side: a video-initiated timeline request is evidence");
  ok(!r.sent.some((m) => m.url === "https://cdn/logo.png"),
     "page side: the scan keeps network noise out");

  const late = [];
  const r2 = runPage({ els: late });
  late.push({ tagName: "VIDEO", currentSrc: "https://cdn/late-player", src: "" });
  r2.observers[0]();
  await settle();
  ok(r2.sent.some((m) => m.url === "https://cdn/late-player"),
     "page side: the observer catches a player added later");
}

// — v0.5.12: the chooser's boxes are drawn as checkboxes (squares with a
//   tick) — this list is multi-select, and circles promise one choice —
const cssSrc = readFileSync(join(here, "popup.css"), "utf8");
const pickBlock = (/\.pickline input \{([^}]*)\}/.exec(cssSrc) || [])[1] || "";
ok(pickBlock && !/border-radius:\s*50%/.test(pickBlock),
   "the pick rows' boxes are not drawn as radio circles");
ok(/\.pickline input:checked::after \{[\s\S]{0,220}?border-left: 2px solid[\s\S]{0,220}?rotate\(-45deg\)/.test(cssSrc),
   "…they are squares with a tick");

if (failures.length) {
  console.error("extension runtime: FAILED");
  for (const f of failures) console.error(" - " + f);
  process.exit(1);
}
console.log("extension runtime: all checks passed");
