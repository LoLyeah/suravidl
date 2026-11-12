// The popup is a doorman, not a download manager (v0.39.0).
//
// It shows what the page is playing, in plain words, and offers two doors:
// the quality route hands the find to the suravidl app (where the real
// formats are, and where the user picks); the quick route queues the best
// quality straight away for people who just want the file. No raw URLs, no
// per-stream rows: the engine does the work, with the captured request
// headers, from either door.
//
// v0.40.7: the chooser is a checkbox list — tick several and the quick door
// queues them all in one batch call; the quality door keeps its one pick
// (the first ticked) because the app's chooser is for one stream.
//
// Firefox's `chrome` namespace is callback-only (measured on Firefox 157):
// every `await` here needs the promise namespace, which Firefox calls
// `browser`; Chrome has no `browser` and its `chrome.*` returns promises.
const api = globalThis.browser || chrome;
const $ = (id) => document.getElementById(id);

// the version chip reads the manifest — a bump can never leave it stale
const MANIFEST = (api.runtime && api.runtime.getManifest)
  ? api.runtime.getManifest() : null;
if (MANIFEST && $("ver")) $("ver").textContent = "v" + MANIFEST.version;
applyI18n();   // the static strings; dynamic ones go through t() at paint

let TAB = null;
let ITEMS = [];      // every find on the tab
let RANK = null;     // the engine's shape for them (hides fragments)
let SHAPE = null;    // the manifests' own shape: variants + audio tracks
let SENT = false;
let INPUTS = [];     // the live row checkboxes, in list order
let SHOW_PARTS = false;  // a stream's variants/audio unfold on demand
let SHOW_OLDER = false;  // the finds from before the newest video, on demand

// Visible finds, playlists first: a manifest is the thing worth choosing —
// its fragments are pieces of it. No rank answer (engine down) shows
// everything; a shell never hides something on a guess. Newest first, within
// each class: on a feed the most recent find is the video on screen, and the
// list used to put the oldest one at the top — under the default tick
// (v0.5.20).
function visibleItems() {
  const shape = {};
  for (const it of (RANK && RANK.items) || []) shape[it.url] = it;
  const visible = ITEMS.filter((m) => !(shape[m.url] && shape[m.url].hidden));
  const ordered = visible.length ? visible : ITEMS.slice();
  // The URL's own shape is the floor: an .m3u8/.mpd master is a manifest
  // whatever the engine says, even when it is down. The engine still decides
  // what to hide.
  const kindOf = (m) => (roleOf(m.url).role === "master"
    ? "manifest"
    : (shape[m.url] && shape[m.url].kind) || "");
  const newest = (a, b) => (b.foundAt || 0) - (a.foundAt || 0);
  const manifests = ordered.filter((m) => kindOf(m) === "manifest").sort(newest);
  return manifests.concat(ordered.filter((m) => kindOf(m) !== "manifest").sort(newest));
}

// Same video, or the one before it? A player asks for its rendition and its
// audio within a second of each other on one origin; a feed's next video
// arrives when the previous one ends. Finds quieter than this belong to
// another video, and fold away (v0.5.20).
const CLUSTER_GAP = 4000;

function hostOf(url) {
  try { return new URL(url).origin; } catch (_) { return ""; }
}

function clusters(items) {
  const out = [];
  for (const m of items) {
    const at = m.foundAt || 0;
    const origin = hostOf(m.url);
    const cur = out[out.length - 1];
    if (cur && cur.origin === origin && cur.last - at <= CLUSTER_GAP) {
      cur.items.push(m);
      cur.last = at;
    } else {
      out.push({ origin, last: at, items: [m] });
    }
  }
  for (const c of out) c.items = orderCluster(c.items);
  return out;
}

// The top row is the answer: a manifest first (it is the whole stream), then
// the biggest video, audio last (it is a track of the video, never a choice of
// its own), and only then newest.
function orderCluster(items) {
  const rank = (m) => (roleOf(m.url).role === "master" ? -1
    : /^audio\//.test(m.mime || "") ? 1 : 0);
  return items.slice().sort((a, b) => {
    if (rank(a) !== rank(b)) return rank(a) - rank(b);
    if ((b.bytes || 0) !== (a.bytes || 0)) return (b.bytes || 0) - (a.bytes || 0);
    return (b.foundAt || 0) - (a.foundAt || 0);
  });
}

// The biggest video in the newest bunch is the file a person means by "this
// video"; audio-only tracks are never it (a player fetches them alongside).
// A slice the player was still feeding is not a video either: 18 KB of a reel
// wore the tick until the real file arrived, and the download it started was
// broken. With another video to pick from, anything under one frame's worth
// of bytes is not a candidate (v0.5.21).
const MIN_VIDEO_BYTES = 64 * 1024;

function recommend(items) {
  // A manifest is the whole stream, whatever its size says: picking it is
  // picking the video, and the app can still choose a quality inside it.
  const master = items.find((m) => roleOf(m.url).role === "master");
  if (master) return master;
  const videos = items.filter((m) => /^video\//.test(m.mime || "") && m.bytes > 0);
  const sized = items.filter((m) => m.bytes > 0);
  const pool = videos.length ? videos : sized;
  if (!pool.length) return items[0] || null;
  const real = pool.filter((m) => m.bytes >= MIN_VIDEO_BYTES);
  return (real.length ? real : pool).reduce((a, b) => (b.bytes > a.bytes ? b : a));
}

function sizeText(bytes) {
  if (!bytes || bytes < 1024) return "";
  const mb = bytes / (1024 * 1024);
  if (mb >= 1024) return (mb / 1024).toFixed(2) + " GB";
  if (mb >= 10) return Math.round(mb) + " MB";
  if (mb >= 1) return mb.toFixed(1).replace(/\.0$/, "") + " MB";
  return Math.max(1, Math.round(bytes / 1024)) + " KB";
}

function kindWord(m) {
  const shape = {};
  for (const it of (RANK && RANK.items) || []) shape[it.url] = it;
  const kind = (shape[m.url] && shape[m.url].kind) || "";
  if (kind === "manifest") return t("Playlist");
  if (kind === "media") return t("Video");
  if (kind === "segment") return t("Fragment");
  return t("Stream");
}

// A row should say what it IS, not just count. When the URL carries a
// resolution token or a human filename, that is the name ("Big Buck Bunny
// 2019 · 1080p"); plumbing — index, master, segment chunks — never reaches
// the user's eyes. "Video 1, Video 2…" told nobody anything (2026-10-01).
const GENERIC_SEG = /^(index|master|playlist|manifest|media|stream|video|out|live|main|hls|dash|chunklist|init|v|m|a)$/i;

function resToken(text) {
  let m = /(?:^|[^\d])(\d{3,4})p(?:[^\d]|$)/i.exec(text);
  if (m) {
    const n = parseInt(m[1], 10);
    if (n >= 144 && n <= 4320) return n + "p";
  }
  m = /(?:^|[^\w])(4k|8k)(?:[^\w]|$)/i.exec(text);
  return m ? m[1].toUpperCase() : "";
}

function streamName(url) {
  let u;
  try { u = new URL(url); } catch (_) { return { name: "", res: "" }; }
  const res = resToken(u.pathname + " " + u.search);
  const last = u.pathname.split("/").filter(Boolean).pop() || "";
  let seg = last;
  try { seg = decodeURIComponent(last); } catch (_) { /* keep it raw */ }
  let name = seg.replace(/\.[a-z0-9]{1,5}$/i, "")        // drop the file extension
               .replace(/[._-]+/g, " ").replace(/\s+/g, " ").trim();
  if (res) {
    const token = /^[48][kK]$/.test(res) ? res.toLowerCase() : res.replace(/p$/, "") + "p?";
    name = name.replace(new RegExp("(^|\\s)" + token + "(\\s|$)", "i"), " ").trim();
  }
  const flat = /^[\d\s]+$/.test(name) || /^[\da-f]{8,}$/i.test(name);
  if (name.length < 4 || name.length > 46 || GENERIC_SEG.test(name) || flat ||
      /(^|\s)(seg|frag|chunk|part|slice|init)([-\s]|$)/i.test(name)) {
    name = "";
  }
  return { name, res };
}

// What a row IS, read from the URL alone — rank is a pure URL answer and
// the popup has to stay instant. A master names the whole stream; an
// audio path is one track; a resolution token is one variant. "Playlist 1,
// Playlist 2…" told nobody which row to pick (2026-10-16).
const AUDIO_SEG = /^(audio|audios|native|jpn|japanese|eng|english|ind|indo|indonesian|commentary)$/i;
const MASTER_SEG = /^(master|index|playlist|manifest|main|hls|stream)$/i;

function roleOf(url) {
  let u;
  try { u = new URL(url); } catch (_) { return { role: "other" }; }
  const path = u.pathname;
  if (!/\.(m3u8|mpd)$/i.test(path) && !/(master|manifest|playlist)/i.test(path)) {
    return { role: "other" };
  }
  const last = (path.split("/").filter(Boolean).pop() || "")
    .replace(/\.[a-z0-9]{1,5}$/i, "").replace(/[._-]+/g, " ");
  if (/\/audio?s?\//i.test(path) || AUDIO_SEG.test(last)) {
    return { role: "audio", name: last };
  }
  if (MASTER_SEG.test(last)) return { role: "master" };
  const res = resToken(last);
  if (res) return { role: "variant", res };
  return { role: "playlist", name: last };
}

// The engine read the manifests themselves: a variant's resolution, an audio
// rendition's name. That beats anything the URL can say (v0.47.3).
function resFromResolution(r) {
  const m = /^\d+x(\d+)$/.exec(String(r || ""));
  return m ? m[1] + "p" : "";
}

function shapeChild(url) {
  const out = { role: "", res: "", name: "" };
  for (const it of (SHAPE && SHAPE.items) || []) {
    for (const v of it.variants || []) {
      if (v.url === url) { out.role = "variant"; out.res = resFromResolution(v.res); }
    }
    for (const a of it.audio || []) {
      if (a.url === url) { out.role = "audio"; out.name = a.name || a.lang || ""; }
    }
    if (out.role) break;
  }
  return out;
}

function shapeMaster(url) {
  return ((SHAPE && SHAPE.items) || [])
    .find((it) => it.url === url && it.master) || null;
}

// The raw-link door's face: a chain, drawn rather than typed — no font on
// any of the three platforms carries a link glyph reliably (v0.5.26).
function linkGlyph() {
  try {
    if (typeof document.createElementNS !== "function") return null;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "12");
    svg.setAttribute("height", "12");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2.2");
    svg.setAttribute("stroke-linecap", "round");
    const a = document.createElementNS(ns, "path");
    a.setAttribute("d", "M10.5 13.5a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1");
    const b = document.createElementNS(ns, "path");
    b.setAttribute("d", "M13.5 10.5a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1");
    svg.append(a, b);
    return svg;
  } catch (_) {
    return null;   // a shell without SVG still gets the word
  }
}

function streamLabel(m) {
  const child = shapeChild(m.url);
  if (child.role === "variant" && child.res) return t("Video") + " · " + child.res;
  if (child.role === "audio") return t("Audio") + (child.name ? " · " + child.name : "");
  const role = roleOf(m.url);
  if (role.role === "master") return t("All qualities");
  if (role.role === "audio") return role.name ? t("Audio") + " · " + role.name : t("Audio");
  const info = streamName(m.url);
  // The response knows what the URL does not: an audio-only track is not a
  // lower-quality video, and calling it one made the list lie (v0.5.20).
  if (/^audio\//.test(m.mime || "")) {
    return info.name ? t("Audio") + " · " + info.name : t("Audio");
  }
  const base = info.name || kindWord(m);
  return info.res ? base + " · " + info.res : base;
}

// When the list has exactly one master, the other playlists on its origin
// are that stream's parts: variants and audio tracks. They fold under the
// master row — picking the master is picking the whole stream (best video
// plus its audio), which is what "download this video" means.
function groupRows(vis) {
  const roles = vis.map((m) => roleOf(m.url));
  const masters = [];
  roles.forEach((r, i) => { if (r.role === "master") masters.push(i); });
  if (masters.length !== 1) return null;
  const mi = masters[0];
  let origin = "";
  try { origin = new URL(vis[mi].url).origin; } catch (_) { return null; }
  const parts = [];
  const rest = [];
  vis.forEach((m, i) => {
    if (i === mi) return;
    const r = roles[i];
    let same = false;
    try { same = new URL(m.url).origin === origin; } catch (_) { /* keep apart */ }
    if (same && (r.role === "variant" || r.role === "audio" || r.role === "playlist")) {
      parts.push({ m, role: r });
    } else {
      rest.push({ m, role: r });
    }
  });
  if (!parts.length) return null;
  return { master: vis[mi], role: roles[mi], parts, rest };
}

function checkedUrls() {
  return INPUTS.filter((i) => i.checked).map((i) => i.value);
}

// The quality door's pick: the first ticked row — the app's chooser is for
// ONE stream, and the list order is the reading order.
function primaryUrl() {
  return checkedUrls()[0] || (visibleItems()[0] || {}).url || "";
}

// The doors re-label themselves as the ticks change: one find is a download,
// several are a batch.
function refreshDoors() {
  const n = checkedUrls().length;
  const quick = $("quick");
  if (quick) {
    quick.textContent = n > 1
      ? t("Queue all {n} at best quality", { n: n })
      : t("Quick download — best quality");
  }
  const all = $("allbtn");
  if (all) {
    const every = INPUTS.length > 0 && INPUTS.every((i) => i.checked);
    all.textContent = every ? t("Select none") : t("Select all");
    all.setAttribute("aria-pressed", String(every));
  }
}

// The two doors: "quality" hands the find over (the app opens on the format
// list); "quick" queues the best quality right now — no window, no choosing.
async function send(url, mode, audio) {
  if (SENT || !url) return;
  const quick = mode === "quick";
  const picks = quick ? checkedUrls() : [];
  const single = !quick || picks.length <= 1;
  const btn = quick ? $("quick") : $("send");
  btn.classList.add("busy");
  $("send").disabled = true;
  $("quick").disabled = true;
  status(t("Sending to suravidl…"), "");
  let res = null;
  try {
    res = await api.runtime.sendMessage(quick
      ? (single
          // the feed's soundtrack rides with the picture: one job, one
          // playable file, no silent download (v0.5.24)
          ? { type: "sendToEngine", url: picks[0] || url, audioUrl: (audio || ""),
              tabId: TAB && TAB.id }
          : { type: "sendBatch", urls: picks, tabId: TAB && TAB.id })
      : {
          type: "sendHandoff",
          url,
          // each find's slice fallback rides after the canonical addresses:
          // the engine prefers the whole file and still has the address the
          // player itself used if the CDN refuses it (v0.5.21)
          urls: visibleItems().map((m) => m.url)
            .concat(visibleItems().filter((m) => m.alt).map((m) => m.alt)).slice(0, 20),
          tabUrl: (TAB && TAB.url) || "",
          tabId: TAB && TAB.id,
        });
  } catch (e) {
    res = { ok: false, error: String(e) };
  }
  if (res && res.ok) {
    SENT = true;
    btn.classList.remove("busy");
    const sentLine = quick
      ? (single
          ? t("✓ Sent — suravidl is downloading it in best quality.")
          : t("✓ Sent — {n} downloading at best quality.", { n: res.queued })
            + (res.skipped ? " " + t("{n} skipped.", { n: res.skipped }) : ""))
      : res.mode === "job"
        ? t("✓ Sent — this suravidl build downloads it straight away.")
        : t("✓ Sent — choose the quality in suravidl.");
    status(sentLine, "ok");
    // the mirror catches up too, so the open moment shows the new job
    api.runtime.sendMessage({ type: "recentJobs" }).then(renderRecent).catch(() => {});
    // long enough for the line to be read (and announced), then get out of the way
    setTimeout(() => { try { window.close(); } catch (_) { /* not a popup */ } }, 2400);
  } else {
    btn.classList.remove("busy");
    $("send").disabled = false;
    $("quick").disabled = false;
    // the background's reasons are written for a console, not a person: say
    // the plain sentence, and only mark the engine unreachable when it is
    const why = (res && res.error) || "";
    if (/cannot reach/i.test(why)) setEngine({ ok: false });
    status("✗ " + plainSendError(why), "bad");
  }
}

// One plain sentence per failure kind — no addresses, no status codes.
function plainSendError(why) {
  if (/cannot reach/i.test(why)) return t("Couldn't reach suravidl — open the app, then try again.");
  if (/refused the token/i.test(why))
    return t("suravidl didn't accept the saved token — open Engine settings and paste the current one.");
  if (/^engine \d/i.test(why)) return t("suravidl couldn't read this one — the app knows why.");
  return t("something went wrong sending it — try again.");
}

function status(text, kind) {
  const el = $("status");
  el.textContent = text;
  el.className = "status" + (kind ? " " + kind : "");
  // the region is always present (screen readers announce display:none
  // unhides unreliably); the stylesheet hides it while it is empty
}

// A feed plays one video and fetches the next one early, so the newest
// network find is usually NOT the video on screen — the tick used to land on
// the upcoming reel, and the download felt random. Nothing in the URLs or the
// timings separates the two, so the popup stops guessing: one card per video,
// drawn from the file itself, and nothing is picked until a person picks
// (v0.5.22).
const MAX_CARDS = 10;

function clockText(sec) {
  if (!isFinite(sec) || sec <= 0) return "";
  const s = Math.round(sec);
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}

// A frame from the file itself. The CDN's frame is cross-origin and would
// taint the canvas, so the first 640 KB are fetched with the page's own
// cookies and played from a blob: same-origin, drawable, and a working URL is
// proof the card can be downloaded at all.
async function cardFrame(url) {
  if (typeof HTMLVideoElement === "undefined" || typeof fetch !== "function") return null;
  if (typeof URL === "undefined" || !URL.createObjectURL) return null;
  let obj = "";
  const drop = () => { if (obj) URL.revokeObjectURL(obj); };
  try {
    const res = await fetch(url, {
      credentials: "include", cache: "force-cache",
      headers: { Range: "bytes=0-655359" },
    });
    if (!res || (!res.ok && res.status !== 206)) { drop(); return null; }
    const part = await res.blob();
    if (!part || !part.size) { drop(); return null; }
    obj = URL.createObjectURL(new Blob([part], { type: "video/mp4" }));
    const v = document.createElement("video");
    v.muted = true;
    v.playsInline = true;
    v.preload = "auto";
    v.src = obj;
    const meta = await new Promise((resolve) => {
      const t = setTimeout(() => resolve(false), 5000);
      v.onloadedmetadata = () => { clearTimeout(t); resolve(true); };
      v.onerror = () => { clearTimeout(t); resolve(false); };
    });
    if (!meta) { drop(); return null; }
    const dur = v.duration;
    const at = Math.min(Math.max(dur / 3, 0.1), 1.5);
    await new Promise((resolve) => {
      const t = setTimeout(resolve, 4000);
      v.onseeked = () => { clearTimeout(t); resolve(); };
      try { v.currentTime = at; } catch (_) { clearTimeout(t); resolve(); }
    });
    const c = document.createElement("canvas");
    c.width = 240;
    c.height = 135;
    const ctx = c.getContext && c.getContext("2d");
    if (!ctx) { drop(); return { shot: "", dur }; }
    const vw = v.videoWidth || 16;
    const vh = v.videoHeight || 9;
    const scale = Math.max(c.width / vw, c.height / vh);
    const dw = vw * scale;
    const dh = vh * scale;
    ctx.drawImage(v, (c.width - dw) / 2, (c.height - dh) / 2, dw, dh);
    return { shot: c.toDataURL("image/jpeg", 0.72), dur };
  } catch (_) {
    drop();
    return null;
  } finally {
    if (obj) setTimeout(drop, 4000);
  }
}

// One video on the page: its own frame above the rows, with its duration.
// The same fetch that draws it also proves the URL plays (v0.5.26).
function showOne(m) {
  const ov = $("onevideo");
  if (!ov || !m) return;
  const size = sizeText(m.bytes);
  ov.hidden = false;
  $("onemeta").textContent = size;
  cardFrame(m.url).then((got) => {
    if (!got) return;
    if (got.shot && $("onethumb").style) {
      $("onethumb").style.backgroundImage = "url(" + got.shot + ")";
    }
    if (got.dur) $("onemeta").textContent = clockText(got.dur) + (size ? " · " + size : "");
  }).catch(() => {});
}

function renderCards(groups) {
  const box = $("cards");
  if (!box) return;
  box.textContent = "";
  box.hidden = false;
  groups.slice(0, MAX_CARDS).forEach((c, i) => {
    const best = recommend(c.items);
    if (!best) return;
    const card = document.createElement("div");
    card.className = "card";
    const thumb = document.createElement("span");
    thumb.className = "thumb";
    const meta = document.createElement("span");
    meta.className = "cmeta";
    const line = document.createElement("span");
    line.className = "cline";
    const size = sizeText(best.bytes);
    line.textContent = (i === 0 ? t("Newest") : t("Earlier")) + (size ? " · " + size : "");
    // both doors stay, on the video this card names: the quick one takes the
    // best quality straight away, the other opens the app's chooser. A feed
    // answers the first; a page with real formats needs the second (v0.5.25)
    const acts = document.createElement("span");
    acts.className = "cacts";
    const dl = document.createElement("button");
    dl.type = "button";
    dl.className = "cdl";
    dl.textContent = t("Download");
    const track = c.items.find((m) => /^audio\//.test(m.mime || ""));
    dl.onclick = () => send(best.url, "quick", track && track.url);
    const q = document.createElement("button");
    q.type = "button";
    q.className = "cqual";
    q.textContent = t("Quality");
    q.onclick = () => send(best.url, "quality");
    acts.append(dl, q);
    meta.append(line, acts);
    card.append(thumb, meta);
    box.append(card);
    cardFrame(best.url).then((got) => {
      if (!got) return;
      if (got.shot && thumb.style) thumb.style.backgroundImage = "url(" + got.shot + ")";
      if (got.dur) line.textContent = clockText(got.dur) + (size ? " · " + size : "");
    }).catch(() => {});
  });
}

function render() {
  const vis = visibleItems();
  $("found").hidden = vis.length === 0;
  $("empty").hidden = vis.length > 0;
  if (!vis.length) return;

  if (TAB && TAB.url) {
    let host = "";
    try { host = new URL(TAB.url).hostname.replace(/^www\./, ""); } catch (_) { /* opaque tab */ }
    if (host) {
      $("site").hidden = false;
      $("hostline").textContent = host;
      if (TAB.favIconUrl) {
        $("favicon").onerror = () => { $("favicon").hidden = true; };
        $("favicon").src = TAB.favIconUrl;
        $("favicon").hidden = false;
      } else {
        $("favicon").hidden = true;
      }
    }
  }

  const many = vis.length > 1;
  $("headline").textContent = many
    ? t("{n} streams found on this page", { n: vis.length })
    : t("Video found on this page");
  $("subline").textContent = many
    ? t("Tick the ones you want — queue them all at best, or choose quality for the first in the app.")
    : t("The quality picker is in the app — suravidl opens ready to choose.");

  const group = $("pickgroup");
  group.hidden = !many;
  const grouped = groupRows(vis);

  // A feed leaves one cluster per video, and which of them is on screen is
  // not knowable from the network. With more than one, the pick belongs to a
  // person: cards with a frame and a duration, nothing ticked (v0.5.22).
  const pickable = many && !grouped
    ? clusters(vis).filter((c) => c.items.some((m) => !/^audio\//.test(m.mime || "")))
    : [];
  $("send").onclick = () => send(primaryUrl(), "quality");
  $("quick").onclick = () => send(primaryUrl(), "quick");
  if (pickable.length > 1) {
    INPUTS = [];
    $("streams").textContent = "";
    group.hidden = true;
    $("send").hidden = true;
    $("quick").hidden = true;
    $("foldline").hidden = true;
    $("onevideo").hidden = true;
    $("headline").textContent = t("{n} videos found on this page", { n: pickable.length });
    $("subline").textContent =
      t("Pick the one you are watching — the newest find is often the next reel.");
    if ($("cardhint")) $("cardhint").hidden = false;
    renderCards(pickable);
    refreshDoors();
    return;
  }
  $("send").hidden = false;
  $("quick").hidden = false;
  $("cards").hidden = true;
  if ($("cardhint")) $("cardhint").hidden = true;

  const box = $("streams");
  box.textContent = "";
  INPUTS = [];
  if (many) {
    // quiet rows, no URLs on their face: each row is named (resolution or
    // filename when the URL offers one, the kind word when it doesn't), and
    // an ordinal only when two names still read the same. The URL door on
    // the right unfolds the raw link for anyone who wants it.
    // Rows say what they are; a master's parts fold beneath it and unfold
    // on demand (SHOW_PARTS). The master row carries the summary, so one
    // glance answers "which one do I pick?" — the top, checked row.
    const rows = [];
    let pickUrl = "";
    let foldCount = 0;
    if (grouped && !SHOW_PARTS) {
      const sm = shapeMaster(grouped.master.url);
      const quals = sm
        ? [...new Set((sm.variants || []).map((v) => resFromResolution(v.res)).filter(Boolean))]
        : [...new Set(grouped.parts.filter((p) => p.role.res).map((p) => p.role.res))];
      const audio = (sm ? (sm.audio || []).length : 0) ||
        grouped.parts.filter((p) => p.role.role === "audio").length;
      let label = streamLabel(grouped.master);
      if (quals.length) label += " · " + quals.join(" ");
      if (audio) label += " · " + t("{n} audio", { n: audio });
      rows.push({ m: grouped.master, label, parts: grouped.parts.length });
      for (const x of grouped.rest) rows.push({ m: x.m, label: streamLabel(x.m) });
      pickUrl = grouped.master.url;
    } else if (grouped) {
      rows.push({ m: grouped.master, label: streamLabel(grouped.master) });
      for (const p of grouped.parts) {
        rows.push({ m: p.m, label: streamLabel(p.m), part: true });
      }
      for (const x of grouped.rest) rows.push({ m: x.m, label: streamLabel(x.m) });
      rows.push({ toggle: "hide" });
      pickUrl = grouped.master.url;
    } else {
      // A feed leaves several videos in one list: the finds that arrived
      // together are one video's streams, and the newest bunch is the one on
      // screen. The rest fold away, so the top row is the answer rather than
      // a lucky guess (v0.5.20).
      const cl = clusters(vis);
      const newest = cl[0] ? cl[0].items : [];
      // The fold line lives OUTSIDE the scrolling list: inside it, it sat
      // below the fold and nobody ever saw that older finds were there.
      foldCount = cl.length > 1 && !SHOW_OLDER
        ? cl.slice(1).reduce((n, c) => n + c.items.length, 0) : 0;
      if (cl.length > 1 && !SHOW_OLDER) {
        for (const m of newest) rows.push({ m, label: streamLabel(m) });
      } else {
        cl.forEach((c, i) => {
          if (i > 0) rows.push({ divider: t("Earlier on this page") });
          for (const m of c.items) rows.push({ m, label: streamLabel(m) });
        });
      }
      pickUrl = (recommend(newest) || {}).url || "";
    }
    const counts = {};
    for (const r of rows) if (r.label) counts[r.label] = (counts[r.label] || 0) + 1;
    const seen = {};
    for (const r of rows) {
      if (r.divider) {
        const line = document.createElement("div");
        line.className = "earlier";
        line.textContent = r.divider;
        box.append(line);
        continue;
      }
      if (r.toggle) {
        const line = document.createElement("div");
        line.className = "partsline";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "partstoggle";
        btn.textContent = t("Hide the separate streams");
        btn.onclick = () => { SHOW_PARTS = false; render(); };
        line.append(btn);
        box.append(line);
        continue;
      }
      const m = r.m;
      seen[r.label] = (seen[r.label] || 0) + 1;
      const suffix = counts[r.label] > 1 ? " " + seen[r.label] : "";
      const row = document.createElement("div");
      row.className = "stream" + (r.part ? " part" : "");
      const pick = document.createElement("label");
      pick.className = "pickline";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.name = "stream";
      input.value = m.url;
      input.checked = m.url === pickUrl;
      input.onchange = refreshDoors;
      INPUTS.push(input);
      const say = document.createElement("span");
      say.className = "ssay";
      const size = sizeText(m.bytes);
      say.textContent = r.label + suffix + (size ? " · " + size : "");
      pick.append(input, say);
      if (m.url === pickUrl && !r.part) {
        const best = document.createElement("span");
        best.className = "best";
        best.textContent = t("best");
        pick.append(best);
      }
      const raw = document.createElement("pre");
      raw.className = "raw";
      raw.hidden = true;
      raw.textContent = m.url;
      const more = document.createElement("button");
      more.type = "button";
      more.className = "more icon";
      // a link glyph says "the raw address" at a glance; the word "URL"
      // read as another action next to Download (v0.5.26)
      const glyph = linkGlyph();
      if (glyph) more.append(glyph); else more.textContent = "URL";
      more.setAttribute("aria-expanded", "false");
      more.setAttribute("aria-label",
        t("Show the raw link — {name}", { name: say.textContent }));
      more.onclick = () => {
        const opening = raw.hidden;
        raw.hidden = !opening;
        row.classList.toggle("open", opening);
        more.setAttribute("aria-expanded", String(opening));
        if (opening && raw.scrollIntoView) raw.scrollIntoView({ block: "nearest" });
      };
      row.append(pick, more, raw);
      box.append(row);
      if (r.parts) {
        const line = document.createElement("div");
        line.className = "partsline";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "partstoggle";
        btn.textContent = t("Show the {n} separate streams", { n: r.parts });
        btn.onclick = () => { SHOW_PARTS = true; render(); };
        line.append(btn);
        box.append(line);
      }
    }
    // the headline counts the video on screen, not the whole page: with the
    // older finds folded away, "20 streams" described a list nobody could see
    if (foldCount) {
      $("headline").textContent = t("This video — {n} streams", { n: rows.length });
    }
    // the fold line, outside the scroll box so it is always in sight
    const fold = $("foldline");
    if (fold) {
      fold.textContent = "";
      fold.hidden = foldCount === 0;
      if (foldCount) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "partstoggle";
        btn.textContent = foldCount === 1
          ? t("Show 1 earlier find on this page")
          : t("Show {n} earlier finds on this page", { n: foldCount });
        btn.onclick = () => { SHOW_OLDER = true; render(); };
        fold.append(btn);
      }
    }
    const first = box.querySelector("input");
    // Something is always ticked — both doors need a pick — but the tick is a
    // recommendation now, not list position: the newest video's biggest file
    // (v0.5.20). Before this, a feed page pre-ticked the OLDEST find, which is
    // usually the video that already finished playing.
    if (first && !INPUTS.some((i) => i.checked)) first.checked = true;
    const all = $("allbtn");
    if (all) {
      all.onclick = () => {
        const every = INPUTS.length > 0 && INPUTS.every((i) => i.checked);
        for (const i of INPUTS) i.checked = !every;
        refreshDoors();
      };
    }
    const shown = rows.find((r) => r.m && r.m.url === pickUrl) || rows.find((r) => r.m);
    showOne((shown && shown.m) || vis[0]);
  } else {
    showOne(vis[0]);
  }

  refreshDoors();
}

// The mirror (v0.5.12): the engine's honest states and notes, at the door
// the jobs came through. Same words the app uses; a note renders with the
// same ⓘ the queue cards wear — a finished download that had to compromise
// must say so wherever it is seen.
const STATE_WORD = {
  queued: "Queued",
  downloading: "Downloading",
  merging: "Finalizing",
  completed: "Done",
  failed: "Failed",
  stopped: "Stopped",
  cancelled: "Cancelled",
  paused: "Paused",
  interrupted: "Paused",
};

function jobHost(url) {
  try { return new URL(url).hostname.replace(/^www\./, ""); } catch (_) { return ""; }
}

function renderRecent(rec) {
  const plate = $("recent");
  const list = $("recentList");
  if (!plate || !list) return;
  const jobs = (rec && rec.ok && rec.jobs) || [];
  list.textContent = "";
  plate.hidden = jobs.length === 0;
  if (!jobs.length) return;
  for (const j of jobs) {
    const row = document.createElement("div");
    row.className = "recent-row st-" + (j.status || "queued");
    const dot = document.createElement("span");
    dot.className = "rdot";
    const name = document.createElement("span");
    name.className = "rname";
    name.textContent = j.title || jobHost(j.url) || t("Stream");
    const state = document.createElement("span");
    state.className = "rstate";
    state.textContent = t(STATE_WORD[j.status] || "Queued");
    row.append(dot, name, state);
    list.append(row);
    if (j.note) {
      const note = document.createElement("div");
      note.className = "rnote";
      note.textContent = "\u24d8 " + j.note;
      list.append(note);
    }
  }
}

function setEngine(state) {
  const chip = $("engine");
  if (state && state.ok) {
    chip.className = "engine ok";
    $("engineText").textContent = t("engine ready");
  } else {
    chip.className = "engine down";
    $("engineText").textContent = t("not running");
  }
}

const opts = $("optsLink");
if (opts) {
  opts.onclick = (e) => {
    e.preventDefault();
    api.runtime.openOptionsPage();
  };
}
$("retry").onclick = () => location.reload();
$("rescan").onclick = () => location.reload();

(async () => {
  const [tab] = await api.tabs.query({ active: true, currentWindow: true });
  TAB = tab || null;
  const state = await api.runtime.sendMessage({ type: "engineState" });
  setEngine(state);
  if (!tab || !state || !state.ok) {
    // engine down wins: one thing to fix beats a list you cannot send
    $("down").hidden = false;
    $("found").hidden = true;
    $("empty").hidden = true;
    return;
  }
  try {
    renderRecent(await api.runtime.sendMessage({ type: "recentJobs" }));
  } catch (_) { /* nothing to mirror */ }
  const res = await api.runtime.sendMessage({ type: "getMedia", tabId: tab.id });
  ITEMS = (res && res.items) || [];
  try {
    RANK = await api.runtime.sendMessage({ type: "rank", items: ITEMS });
    SHAPE = await api.runtime.sendMessage({
      type: "shape", items: ITEMS, tabId: (TAB || {}).id,
    });
  } catch (_) { /* engine not answering: show everything */ }
  render();
})();
