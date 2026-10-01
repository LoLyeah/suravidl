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
const popupSrc = readFileSync(join(here, "popup.js"), "utf8");

const failures = [];
const ok = (cond, what) => {
  if (!cond) failures.push(what);
};

// -- a chrome stub with just enough surface ---------------------------------
const listeners = { beforeRequest: [], beforeSendHeaders: [], headersReceived: [],
                    beforeSendHeadersSpec: null };
const store = {};
const badge = {};
const fetchCalls = [];
let onRemoved = [];
let onMessage = null;

globalThis.chrome = {
  action: { setBadgeText: ({ tabId, text }) => (badge[tabId] = text) },
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
  },
  tabs: { onRemoved: { addListener: (fn) => onRemoved.push(fn) }, query() {} },
  runtime: { onMessage: { addListener: (fn) => (onMessage = fn) } },
};

globalThis.fetch = async (url, opts = {}) => {
  fetchCalls.push({ url, opts });
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
    listeners: { beforeRequest: [], beforeSendHeaders: [], headersReceived: [] },
    spec: null, store: {}, badge: {}, fetchCalls: [], onRemoved: [], onMessage: null,
    jobsStatus: 200,
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
    },
    tabs: {
      onRemoved: { addListener: (fn) => ff.onRemoved.push(fn) },
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
  // the promise namespace
  const browserStub = {
    storage: { local: {
      get: (defaults) => Promise.resolve(readStore(defaults)),
      set: (obj) => { Object.assign(ff.store, clone(obj)); return Promise.resolve(); },
    } },
    tabs: { query: () => Promise.resolve([{ id: 7 }]) },
    runtime: { sendMessage: sendToBg, openOptionsPage() {} },
  };

  const saved = { chrome: globalThis.chrome, browser: globalThis.browser,
                  fetch: globalThis.fetch, document: globalThis.document };
  globalThis.chrome = chromeStub;
  globalThis.browser = browserStub;
  globalThis.fetch = async (url, opts = {}) => {
    ff.fetchCalls.push({ url, opts });
    if (url.endsWith("/sniff/patterns")) {
      return { ok: true, json: async () => ({ ext: ["mp4", "m3u8", "ts"] }) };
    }
    if (url.endsWith("/sniff/rank")) {
      return { ok: true, json: async () => ({ items: [], hidden: 0 }) };
    }
    if (url.endsWith("/jobs")) {
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

    await sendToBg({ type: "rank", items: [{ url: "https://cdn/ff.mp4" }] });
    ok(ff.fetchCalls.some((c) => c.url.endsWith("/sniff/rank")),
       "firefox: rank reaches the engine through the promise namespace");

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

    // and the popup script itself, against that same environment
    const el = () => ({
      className: "", textContent: "", title: "", onclick: null, children: [],
      append(...kids) { this.children.push(...kids); },
      appendChild(k) { this.children.push(k); },
      _html: "",
      set innerHTML(v) { this._html = v; if (v === "") this.children = []; },
      get innerHTML() { return this._html; },
    });
    const nodes = { list: el(), status: el(), optsLink: el() };
    let optsOpened = false;
    browserStub.runtime.openOptionsPage = () => (optsOpened = true);
    globalThis.document = {
      getElementById: (id) => nodes[id] || null,
      createElement: () => el(),
    };
    ff.jobsStatus = 200;
    try { new Function(popupSrc)(); }
    catch (e) {
      failures.push("firefox: the popup script must load without throwing (" + e + ")");
    }
    await settle();
    await settle();
    ok(nodes.list.children.length === 1, "firefox: the popup renders the found media");
    const rowBtn = nodes.list.children[0] && nodes.list.children[0].children[2];
    ok(rowBtn && rowBtn.textContent === "Download with suravidl",
       "firefox: …with its download button");
    if (rowBtn) {
      await rowBtn.onclick();
      ok(/^✓ sent to engine \(job J7\)$/.test(nodes.status.textContent),
         "firefox: clicking it hands off and reports the job");
    }
    nodes.optsLink.onclick({ preventDefault() {} });
    ok(optsOpened, "firefox: the options link opens the options page");
  }

  globalThis.chrome = saved.chrome;
  globalThis.browser = saved.browser;
  globalThis.fetch = saved.fetch;
  globalThis.document = saved.document;
}


if (failures.length) {
  console.error("extension runtime: FAILED");
  for (const f of failures) console.error(" - " + f);
  process.exit(1);
}
console.log("extension runtime: all checks passed");
