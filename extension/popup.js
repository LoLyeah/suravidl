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
let SENT = false;
let INPUTS = [];     // the live row checkboxes, in list order

// Visible finds, playlists first: a manifest is the thing worth choosing —
// its fragments are pieces of it. No rank answer (engine down) shows
// everything; a shell never hides something on a guess.
function visibleItems() {
  const shape = {};
  for (const it of (RANK && RANK.items) || []) shape[it.url] = it;
  const visible = ITEMS.filter((m) => !(shape[m.url] && shape[m.url].hidden));
  const ordered = visible.length ? visible : ITEMS.slice();
  const kindOf = (m) => (shape[m.url] && shape[m.url].kind) || "";
  const manifests = ordered.filter((m) => kindOf(m) === "manifest");
  return manifests.concat(ordered.filter((m) => kindOf(m) !== "manifest"));
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

function streamLabel(m) {
  const info = streamName(m.url);
  const base = info.name || kindWord(m);
  return info.res ? base + " · " + info.res : base;
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
async function send(url, mode) {
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
          ? { type: "sendToEngine", url: picks[0] || url }
          : { type: "sendBatch", urls: picks })
      : {
          type: "sendHandoff",
          url,
          urls: visibleItems().map((m) => m.url),
          tabUrl: (TAB && TAB.url) || "",
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
  const box = $("streams");
  box.textContent = "";
  INPUTS = [];
  if (many) {
    // quiet rows, no URLs on their face: each row is named (resolution or
    // filename when the URL offers one, the kind word when it doesn't), and
    // an ordinal only when two names still read the same. The URL door on
    // the right unfolds the raw link for anyone who wants it.
    const labels = vis.map(streamLabel);
    const counts = {};
    for (const l of labels) counts[l] = (counts[l] || 0) + 1;
    const seen = {};
    vis.forEach((m, i) => {
      seen[labels[i]] = (seen[labels[i]] || 0) + 1;
      const suffix = counts[labels[i]] > 1 ? " " + seen[labels[i]] : "";
      const row = document.createElement("div");
      row.className = "stream";
      const pick = document.createElement("label");
      pick.className = "pickline";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.name = "stream";
      input.value = m.url;
      input.onchange = refreshDoors;
      INPUTS.push(input);
      const say = document.createElement("span");
      say.className = "ssay";
      say.textContent = labels[i] + suffix;
      pick.append(input, say);
      const raw = document.createElement("pre");
      raw.className = "raw";
      raw.hidden = true;
      raw.textContent = m.url;
      const more = document.createElement("button");
      more.type = "button";
      more.className = "more";
      more.textContent = "URL";
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
    });
    const first = box.querySelector("input");
    if (first) first.checked = true;
    const all = $("allbtn");
    if (all) {
      all.onclick = () => {
        const every = INPUTS.length > 0 && INPUTS.every((i) => i.checked);
        for (const i of INPUTS) i.checked = !every;
        refreshDoors();
      };
    }
  }

  $("send").onclick = () => send(primaryUrl(), "quality");
  $("quick").onclick = () => send(primaryUrl(), "quick");
  refreshDoors();
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
  const res = await api.runtime.sendMessage({ type: "getMedia", tabId: tab.id });
  ITEMS = (res && res.items) || [];
  try {
    RANK = await api.runtime.sendMessage({ type: "rank", items: ITEMS });
  } catch (_) { /* engine not answering: show everything */ }
  render();
})();
