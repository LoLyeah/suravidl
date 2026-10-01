// The popup is a doorman, not a download manager (v0.39.0).
//
// It shows what the page is playing, in plain words, and offers two doors:
// the quality route hands the find to the suravidl app (where the real
// formats are, and where the user picks); the quick route queues the best
// quality straight away for people who just want the file. No raw URLs, no
// per-stream rows: the engine does the work, with the captured request
// headers, from either door.
//
// Firefox's `chrome` namespace is callback-only (measured on Firefox 157):
// every `await` here needs the promise namespace, which Firefox calls
// `browser`; Chrome has no `browser` and its `chrome.*` returns promises.
const api = globalThis.browser || chrome;
const $ = (id) => document.getElementById(id);

let TAB = null;
let ITEMS = [];      // every find on the tab
let RANK = null;     // the engine's shape for them (hides fragments)
let SENT = false;

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
  if (kind === "manifest") return "Playlist";
  if (kind === "media") return "Video";
  if (kind === "segment") return "Fragment";
  return "Stream";
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

function selectedUrl() {
  const checked = document.querySelector("#streams input:checked");
  return (checked && checked.value) || (visibleItems()[0] || {}).url || "";
}

// The two doors: "quality" hands the find over (the app opens on the format
// list); "quick" queues the best quality right now — no window, no choosing.
async function send(url, mode) {
  if (SENT || !url) return;
  const quick = mode === "quick";
  const btn = quick ? $("quick") : $("send");
  btn.classList.add("busy");
  $("send").disabled = true;
  $("quick").disabled = true;
  status("Sending to suravidl…", "");
  let res = null;
  try {
    res = await api.runtime.sendMessage(quick
      ? { type: "sendToEngine", url }
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
    status(quick
      ? "✓ Sent — suravidl is downloading it in best quality."
      : res.mode === "job"
        ? "✓ Sent — this suravidl build downloads it straight away."
        : "✓ Sent — choose the quality in suravidl.", "ok");
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
  if (/cannot reach/i.test(why)) return "Couldn't reach suravidl — open the app, then try again.";
  if (/refused the token/i.test(why))
    return "suravidl didn't accept the saved token — open Engine settings and paste the current one.";
  if (/^engine \d/i.test(why)) return "suravidl couldn't read this one — the app knows why.";
  return "something went wrong sending it — try again.";
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
    ? vis.length + " streams found on this page"
    : "Video found on this page";
  $("subline").textContent = many
    ? "Pick one, then choose the quality in the suravidl app."
    : "The quality picker is in the app — suravidl opens ready to choose.";

  const group = $("pickgroup");
  group.hidden = !many;
  const box = $("streams");
  box.textContent = "";
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
      input.type = "radio";
      input.name = "stream";
      input.value = m.url;
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
      more.setAttribute("aria-label", "Show the raw link — " + say.textContent);
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
  }

  $("send").onclick = () => send(selectedUrl(), "quality");
  $("quick").onclick = () => send(selectedUrl(), "quick");
}

function setEngine(state) {
  const chip = $("engine");
  if (state && state.ok) {
    chip.className = "engine ok";
    $("engineText").textContent = "engine ready";
  } else {
    chip.className = "engine down";
    $("engineText").textContent = "not running";
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
