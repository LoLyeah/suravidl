// The popup is a doorman, not a download manager (v0.39.0).
//
// It shows what the page is playing, in plain words, and hands the find to
// the suravidl app — where the real formats are, and where the user picks
// the quality. No raw URLs, no per-stream download buttons: the engine
// probes the handed-over stream itself, with the captured request headers,
// and the window opens ready to choose.
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

function selectedUrl() {
  const checked = document.querySelector("#streams input:checked");
  return (checked && checked.value) || (visibleItems()[0] || {}).url || "";
}

async function send(url) {
  if (SENT || !url) return;
  const btn = $("send");
  btn.classList.add("busy");
  btn.disabled = true;
  status("Sending to suravidl…", "");
  let res = null;
  try {
    res = await api.runtime.sendMessage({
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
    status(res.mode === "job"
      ? "✓ Sent — this suravidl build downloads it straight away."
      : "✓ Sent — choose the quality in suravidl.", "ok");
    // long enough for the line to be read (and announced), then get out of the way
    setTimeout(() => { try { window.close(); } catch (_) { /* not a popup */ } }, 2400);
  } else {
    btn.classList.remove("busy");
    btn.disabled = false;
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
    // quiet rows, no URLs: repeated kinds get an ordinal so two playlists
    // read as themselves (“Playlist 1”, “Playlist 2”)
    const words = vis.map(kindWord);
    vis.forEach((m, i) => {
      const row = document.createElement("label");
      row.className = "stream";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "stream";
      input.value = m.url;
      const word = kindWord(m);
      const repeated = words.filter((w) => w === word).length > 1;
      const txt = document.createElement("span");
      const ordinal = repeated
        ? " " + (words.slice(0, i + 1).filter((w) => w === word).length)
        : "";
      txt.textContent = word + ordinal;
      row.append(input, txt);
      box.append(row);
    });
    const first = box.querySelector("input");
    if (first) first.checked = true;
  }

  $("send").onclick = () => send(selectedUrl());
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
