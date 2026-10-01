const CFG = window.__SURAVIDL__ || {};
const H = () => ({
  "Authorization": "Bearer " + CFG.token,
  "Content-Type": "application/json",
});

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: H() });
  if (!r.ok) {
    let msg = `${r.status}`;
    let detail = null;
    try {
      const body = await r.json();
      detail = body && body.detail != null ? body.detail : body;
      // the engine can answer with a structured error ("unsupported url"
      // carries a hint for the user and a flag for the browser offer), so the
      // whole detail rides along on the Error instead of being flattened
      msg = (typeof detail === "object" && detail !== null)
        ? (detail.message || JSON.stringify(detail))
        : String(detail);
    } catch (_) {
      msg += " " + (await r.text().catch(() => ""));
    }
    const err = new Error(msg);
    err.detail = detail;
    throw err;
  }
  return r.json();
}

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};

function humanBytes(n) {
  if (n == null) return "?";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i === 0 ? n : n.toFixed(1)) + " " + u[i];
}

const ACTIVE = new Set(["queued", "downloading", "merging"]);
let DESKTOP = false;
let APP_INFO = null;   // /app/info payload (desktop capabilities)

/* ---------- drawn icons (the sprite lives in index.html) ---------- */
/** `ico("play")` → a span the CSS sizes; one stroke system, no emoji. */
function ico(name) {
  const s = document.createElement("span");
  s.className = "ico";
  s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-' +
    name + '"/></svg>';
  return s;
}

/* ---------- the human voice of an engine error ---------- */
/** yt-dlp explains failures in its own dialect ("ERROR: unable to download
 *  video data: HTTP Error 403: Forbidden"). The first line a person reads
 *  says what it MEANS; the raw text stays one tap away (v0.37.0). */
function humanErr(s) {
  s = String(s == null ? "" : s);
  if (/HTTP Error 404|not found|does not exist/i.test(s))
    return "the site says this link does not exist (404) — check it was copied whole";
  if (/HTTP Error 403|forbidden/i.test(s))
    return "the site refused the request (403) — sign-in cookies or the Impersonate setting often fix this";
  if (/HTTP Error 429|too many requests/i.test(s))
    return "the site is rate-limiting this address (429) — wait a bit, then try once more";
  if (/sign ?in|log ?in|login required|private video|age/i.test(s))
    return "the site wants a signed-in session — load cookies in Settings → Authentication";
  if (/unsupported url/i.test(s))
    return "no extractor recognises this link — try the in-app browser, or a direct media link";
  if (/timed? ?out|timeout/i.test(s))
    return "the site never answered in time — check the connection and retry";
  if (/certificate|SSL/i.test(s))
    return "the secure connection could not be verified — a TLS-inspecting proxy can cause this";
  if (/ffmpeg/i.test(s))
    return "the last step needs ffmpeg — audio “keep original” avoids the conversion";
  const line = s.split("\n")[0];
  return line.length > 140 ? line.slice(0, 140) + "…" : (line || "the download failed");
}

/* ---------- the scope strip: instruments that read the source ---------- */
/** data-state drives the lamps and the reading colours (style.css). */
function setScopes(state, read) {
  const strip = $("scopeStrip");
  if (!strip) return;
  strip.dataset.state = state;
  if (read) {
    if (read.src != null) $("scopeSrc").textContent = read.src;
    if (read.fmt != null) $("scopeFmt").textContent = read.fmt;
    if (read.size != null) $("scopeSize").textContent = read.size;
    if (read.say != null) $("scopeSay").textContent = read.say;
  }
}

/** Per-site livery: the probe card takes a tint from the source (v0.37.0). */
function liveryOf(extractor) {
  const e = String(extractor || "").toLowerCase();
  for (const key of ["youtube", "twitter", "vimeo", "instagram", "tiktok"]) {
    if (e.indexOf(key) !== -1) return key;
  }
  return "";
}

/* ---------- the transport: arm a take, then commit it (v0.37.0) ---------- */
/** Choosing and downloading used to be the same click on eleven controls.
 *  The deck now works like a room: picks ARM a take (one at a time — the
 *  newest arm replaces the old), the START lamp commits it, and a commit
 *  spends the take (one-shot, like the patch bay below). */
let TAKE = { fmt: null, preset: null, label: "" };

function armTake(pick, label, btn) {
  if (!pick) return;
  if (TAKE.fmt === pick || TAKE.preset === pick) {
    // tapping the armed pick again disarms it
    TAKE.fmt = null;
    TAKE.preset = null;
    TAKE.label = "";
  } else if (pick.indexOf("audio-") === 0) {
    TAKE.fmt = null;
    TAKE.preset = pick;
    TAKE.label = label || pick.replace(/^audio-/, "");
  } else {
    TAKE.preset = null;
    TAKE.fmt = pick;
    TAKE.label = label || pick;
  }
  renderTake();
}

function renderTake() {
  const say = $("takeSay");
  const lamp = $("bestBtn");
  if (!say || !lamp) return;
  const armed = TAKE.fmt || TAKE.preset;
  say.textContent = armed
    ? (TAKE.preset ? "audio · " + TAKE.label : TAKE.label)
    : "best available";
  say.classList.toggle("set", !!armed);
  lamp.textContent = armed ? "START · " + (TAKE.label || "take") : "START · best";
  // the armed pick stays lit wherever it lives (chips, format rows, audio) —
  // and ONLY the armed one: a commit spends the take and every light goes out
  document.querySelectorAll("[data-pick]").forEach((b) => {
    b.classList.toggle("picked", b.dataset.pick === armed);
  });
}

async function commitTake(btn) {
  btn = btn || $("bestBtn");
  const url = $("url").value.trim();
  const ok = playlistMode()
    ? await startJob(url, null, TAKE.preset, true, btn)
    : await startJob(url, TAKE.fmt, TAKE.preset, false, btn);
  if (ok) {
    TAKE.fmt = null;
    TAKE.preset = null;
    TAKE.label = "";
    renderTake();
  }
}

/* ---------- toasts ---------- */
/** Keep the phone's toast lane clear of the functional strips that are
 *  ACTUALLY docked at the bottom right now — the transport once it pins
 *  (it is sticky, so at the top of a page it is not down there), the
 *  settings Save strip once it docks. Nothing docked: the lane drops to
 *  just above the tab bar (v0.38.2 report: a fixed 84px lane hovered
 *  "above something missing" on Queue). Desktop keeps the CSS lane. */
function syncToastLane() {
  const host = $("toasts");
  if (!host) return;
  if (!window.matchMedia || !matchMedia("(max-width: 899px)").matches) {
    host.style.bottom = "";
    return;
  }
  const vh = window.innerHeight;
  let top = Infinity;
  for (const el of document.querySelectorAll(".transport, #panel-settings .modal-foot")) {
    const r = el.getBoundingClientRect();
    if (r.height < 8 || r.top > vh || r.bottom < 0) continue;   // hidden or gone
    if (r.bottom < vh - 140) continue;                          // in the flow, not docked
    top = Math.min(top, r.top);
  }
  host.style.bottom = top === Infinity ? "" : Math.round(vh - (top - 8)) + "px";
}
window.addEventListener("resize", syncToastLane, { passive: true });
// capture: the phone panels can be their own scroll containers
window.addEventListener("scroll", () => {
  if ($("toasts").children.length) syncToastLane();
}, { passive: true, capture: true });

/** msg, kind ("ok" | "bad" | "info"), and optionally:
 *  - sticky:  do not time out; it stays until dismissed (an update notice)
 *  - actions: [{label, prime, onClick}] — real choices on the toast itself.
 *  The buttons stop the click from bubbling, so tapping one runs it and
 *  dismisses the toast, while a plain toast still dismisses on any tap. */
function toast(msg, kind = "ok", opts) {
  const t = el("div", "toast " + kind);
  t.append(el("span", "dot"));
  t.append(el("span", "tmsg", msg));
  const actions = opts && opts.actions;
  if (actions && actions.length) {
    const row = el("div", "toactions");
    for (const a of actions) {
      const b = el("button", "ghost-sm" + (a.prime ? " prime" : ""), a.label);
      b.onclick = (ev) => {
        ev.stopPropagation();
        dismiss(t);
        try { if (a.onClick) a.onClick(); } catch (_) { /* a choice must not throw */ }
      };
      row.append(b);
    }
    t.append(row);
  } else {
    t.onclick = () => dismiss(t);
  }
  syncToastLane();
  $("toasts").append(t);
  if (!(opts && opts.sticky)) setTimeout(() => dismiss(t), 4200);
  return t;
}
function dismiss(t) {
  if (!t.parentNode) return;
  t.classList.add("leaving");
  setTimeout(() => t.remove(), 260);
}

/* ---------- modal transitions ---------- */
function openModal(m) {
  clearTimeout(m._closeTimer);
  m.classList.remove("hidden", "closing");
}
function closeModal(m) {
  m.classList.add("closing");
  m._closeTimer = setTimeout(() => {
    m.classList.remove("closing");
    m.classList.add("hidden");
  }, 170);
}

/* ---------- clipboard ---------- */
/** Copy to the clipboard wherever the page runs.
 *
 *  navigator.clipboard wants a secure origin and a live user gesture, and
 *  some WebViews refuse it outright; a throwaway textarea + execCommand
 *  still works there. One helper, so every copy in the page behaves alike
 *  (the copy-path button and the Copy button on a failed row). */
async function copyText(t) {
  t = String(t == null ? "" : t);
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(t);
      return true;
    }
  } catch (_) { /* blocked: try the old way */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = t;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    ta.style.pointerEvents = "none";
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  } catch (_) {
    return false;
  }
}

/* ---------- confirm modal ---------- */
function askConfirm(message, { okText = "Confirm", danger = true } = {}) {
  return new Promise((resolve) => {
    const modal = $("confirmModal");
    $("confirmMsg").textContent = message;
    const yes = $("confirmYes"), no = $("confirmNo");
    yes.textContent = okText;
    yes.className = "btn " + (danger ? "danger" : "prime");
    const done = (val) => {
      closeModal(modal);
      yes.onclick = no.onclick = modal.onclick = null;
      document.removeEventListener("keydown", onKey);
      resolve(val);
    };
    const onKey = (e) => { if (e.key === "Escape") done(false); };
    yes.onclick = () => done(true);
    no.onclick = () => done(false);
    modal.onclick = (e) => { if (e.target === modal) done(false); };
    document.addEventListener("keydown", onKey);
    openModal(modal);
  });
}

/* ---------- theme / glass ---------- */
function applyTheme(theme, glass, accent) {
  const r = document.documentElement;
  const changed = (theme && r.dataset.theme !== theme)
    || (glass && r.dataset.glass !== glass)
    || (accent && r.dataset.accent !== accent);
  if (theme) r.dataset.theme = theme;
  if (glass) r.dataset.glass = glass;
  if (accent) r.dataset.accent = accent;
  // A theme switch repaints every surface. Without this the big cards eased
  // their colours over 350ms while every button, pill and input inside them
  // snapped instantly — the UI looked torn for a third of a second (motion
  // review). Scoped to a class that lives only for the switch, so hover
  // feedback keeps its own much faster timing the rest of the time.
  if (changed) {
    clearTimeout(applyTheme._t);
    r.classList.add("theming");
    applyTheme._t = setTimeout(() => r.classList.remove("theming"), 460);
  }
}
function markSwatches(values) {
  document.querySelectorAll("#themeSwatches .swatch").forEach((b) =>
    b.classList.toggle("on", b.dataset.theme === values.theme));
  document.querySelectorAll("#glassSwatches .swatch").forEach((b) =>
    b.classList.toggle("on", b.dataset.glass === values.glass));
  document.querySelectorAll("#schemeSwatches .swatch").forEach((b) =>
    b.classList.toggle("on", b.dataset.accent === values.accent));
}
let CURRENT = { theme: CFG.theme || "dark", glass: CFG.glass || "frosted",
                accent: CFG.accent || "amber" };
let SETTINGS_SNAPSHOT = null;   // last /settings payload (used by the preset diff)
let wnVersion = null;   // the version the open what's-new card belongs to

async function setAppearance(patch, label) {
  try {
    const s = await api("/settings", { method: "POST", body: JSON.stringify(patch) });
    CURRENT = { theme: s.theme, glass: s.glass, accent: s.accent };
    applyTheme(s.theme, s.glass, s.accent);
    markSwatches(CURRENT);
    toast(label, "info");
  } catch (e) {
    toast("could not apply: " + e.message, "bad");
  }
}

/* ---------- probe ---------- */
let PROBE_SEQ = 0;

async function doProbe() {
  const url = $("url").value.trim();
  if (!url) return;
  const seq = ++PROBE_SEQ;      // two probes in flight: the newest one wins
  // a previous failure's red clears before this probe starts speaking
  $("probeMsg").className = "msg muted";
  $("probeMsg").textContent = "probing…";
  $("probeMsg").classList.remove("hidden");
  $("probeSay").classList.add("hidden");
  $("probeSay").textContent = "";
  $("probeDetails").classList.add("hidden");
  setScopes("scan", { say: "reading the source…" });
  $("probeBtn").classList.add("busy");
  try {
    const info = await api("/probe", {
      method: "POST", body: JSON.stringify({ url }),
    });
    if (seq !== PROBE_SEQ) return;
    renderProbe(url, info);
    $("probeMsg").textContent = "";
    $("browserOffer").classList.add("hidden");   // it probed fine: no browser needed
  } catch (e) {
    if (seq !== PROBE_SEQ) return;
    // the engine explains a failure (it owns the "sign-in wall" judgement and
    // says so in its own words) — the UI does not second-guess it
    $("probeMsg").textContent = "probe failed: " + e.message;
    // an error is Nova Rose and machine text is mono; this line was the one
    // failure in the app that whispered in grey (polish pass)
    $("probeMsg").className = "msg bad mono";
    // the human line leads; the raw engine text sits behind "Show details"
    // (v0.37.0: yt-dlp's dialect was the FIRST thing a newcomer had to read)
    $("probeMsg").classList.add("hidden");
    $("probeSay").textContent = humanErr(e.message);
    $("probeSay").className = "msg bad";
    $("probeSay").classList.remove("hidden");
    $("probeDetails").textContent = "Show details";
    $("probeDetails").classList.remove("hidden");
    setScopes("bad", { say: "no readout — see the message above" });
    offerBrowser(e, url);
    $("probeCard").classList.add("hidden");
    $("dlEmpty").classList.remove("hidden");
    // chips from the *previous* probe still carry its URL: leaving them armed
    // downloads a link the user has already replaced (v0.21.1 audit)
    $("qualityRow").classList.add("hidden");
    $("qualityBtns").replaceChildren();
    $("playlistRow").classList.add("hidden");
    PLAYLIST = null;
    PLAYLIST_NONE = false;
  } finally {
    if (seq === PROBE_SEQ) $("probeBtn").classList.remove("busy");
  }
}

/* "No extractor for this page" is not a dead end on a host that has the in-app
   browser: the engine's structured answer carries `unsupported`, and that
   browser is exactly what it was built for (v0.24.2, M3). The offer is hidden
   again on the next probe — never left pointing at a URL the user replaced. */
function offerBrowser(err, url) {
  const row = $("browserOffer");
  if (!row) return;
  const detail = (err && err.detail) || {};
  const asked = detail.unsupported === true ||
    /unsupported url/i.test((err && err.message) || "");
  if (!asked || !window.AndroidHost || !window.AndroidHost.openBrowser) {
    row.classList.add("hidden");
    return;
  }
  row.classList.remove("hidden");
  $("browserOfferBtn").onclick = () => {
    try { window.AndroidHost.openBrowser(url); } catch (_) { }
  };
}

function fmtQuality(f) {
  if (f.height) return f.height + "p" + (f.fps && f.fps > 30 ? f.fps : "");
  if (f.abr) return f.abr + " kbps";
  return f.format_note || f.resolution || "";
}

/* ---------- format rows: read the codec soup, and never hand out silence --- */
const CODEC_NAMES = {
  avc1: "H.264", avc3: "H.264", hev1: "HEVC", hvc1: "HEVC", vp09: "VP9",
  vp9: "VP9", vp8: "VP8", av01: "AV1", mp4a: "AAC", opus: "Opus",
  vorbis: "Vorbis", ac3: "AC-3", ec3: "E-AC-3", flac: "FLAC",
};

const codecName = (c) => {
  if (!c || c === "none") return null;
  const base = String(c).split(".")[0].toLowerCase();
  return CODEC_NAMES[base] || c;
};

const hasVideo = (f) => !!f.vcodec && f.vcodec !== "none";
const hasAudio = (f) => !!f.acodec && f.acodec !== "none";

function fmtCodecs(f) {
  const parts = [f.ext];
  const v = codecName(f.vcodec), a = codecName(f.acodec);
  if (v) parts.push("video " + v);
  if (a) parts.push("audio " + a);
  return parts.join(" · ");
}

/** What the stream contains — the thing the old table made you guess.
 *
 *  A video-only row says what the download will DO with it: by default the
 *  app pairs the site's separate audio back in, or leaves the video silent
 *  when the "no sound" choice is ticked — and a site with no separate audio
 *  is said out loud instead of promising a sound track that does not exist.
 *  (2026-09-27 report: "'video only - sound added latter' is ambiguous for
 *  inexperienced user".) */
function fmtKind(f, hasSeparateAudio) {
  const v = hasVideo(f), a = hasAudio(f);
  if (v && a) return { label: "video + audio", cls: "k-both" };
  if (v) {
    if (!hasSeparateAudio) {
      return { label: "video only — no sound available", cls: "k-video" };
    }
    return { label: soundChoiceLabel(), cls: "k-video", sound: true };
  }
  if (a) return { label: "audio only", cls: "k-audio" };
  // a plain file (direct link): the site told us nothing about its tracks
  return { label: "single file", cls: "k-audio" };
}

/** The two states of a video-only row's label, read live from the checkbox
 *  so ticking it re-labels the whole table (refreshSoundLabels). The
 *  unticked state IS the default and stays unannotated: "video only — sound
 *  included" on every row read as noise (2026-09-27: "only show 'video
 *  only — no sound' if the checklist is checked"). */
function soundChoiceLabel() {
  const off = $("noSound") && $("noSound").checked;
  return off ? "video only — no sound" : "video only";
}

/** The "no sound" tick re-labels the rows it applies to, in place. Which
 *  rows those are is baked in at render time ([data-sound]): a row that
 *  never had separate audio says so and must not be re-labelled. */
function refreshSoundLabels() {
  for (const cell of document.querySelectorAll("#formats .fmt-kind[data-sound]")) {
    cell.textContent = soundChoiceLabel();
  }
}

/** Picking a video-only stream must not produce a silent file: pair it with
 *  the site's separate audio track when one exists (yt-dlp merges both with
 *  ffmpeg) — unless the user ticked "no sound", which is exactly the
 *  instruction not to (2026-09-27). Direct-link files have no separate
 *  audio, so they stay as-is. */
function fmtSpec(f, hasSeparateAudio) {
  return hasSeparateAudio && hasVideo(f) && !hasAudio(f) && !$("noSound").checked
    ? `${f.format_id}+bestaudio/best`
    : f.format_id;
}

function sizeCell(f) {
  const td = el("td", "fmt-s");
  const b = f.filesize || f.filesize_approx;
  if (b) {
    td.textContent = humanBytes(b);
  } else {
    td.textContent = "unknown";
    td.classList.add("muted");
    const why = "the site does not advertise a size for this stream — " +
                "the real size shows once the download starts";
    td.title = why;                    // desktops hover
    td.onclick = () => toast(why);     // phones tap
  }
  return td;
}

/** Sites announce the same stream twice (DASH + HLS, one without a size).
 *  Keep one row per real choice, preferring the copy that knows its size. */
function dedupeFormats(list) {
  const best = new Map();
  for (const f of list) {
    const key = [f.height || f.abr || 0, f.ext, f.vcodec, f.acodec,
                 f.fps || 0, f.format_note || ""].join("|");
    const prev = best.get(key);
    if (!prev) { best.set(key, f); continue; }
    const size = (x) => x.filesize || x.filesize_approx || 0;
    if (size(f) > 0 && size(prev) === 0) best.set(key, f);
  }
  return [...best.values()];
}

/** h:mm:ss (or m:ss) — the format the clip fields and yt-dlp both take. */
function clock(seconds) {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  const mm = String(m).padStart(2, "0"), ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

/** Subtitle chips: the languages THIS site offers for THIS video — click to
 *  toggle one in or out of the wish list, and every picked one stays lit
 *  (2026-09-27: "use highlights for the chosen language; I can't unclick the
 *  one I accidentally click"). The list opens with the languages a person is
 *  actually after — the device's own, then English — and the rest is one tap
 *  away; fourteen chips used to be a wall with Abkhazian at the front. */
let SUBS_EXPANDED = false;

/** The languages picked so far, in the override field's own spelling. */
function pickedSubs() {
  const field = $("ovSubLangs");
  return field
    ? field.value.split(",").map((s) => s.trim()).filter(Boolean)
    : [];
}

function renderSubsChips(info) {
  const box = $("subsChips");
  if (!box) return;
  box.replaceChildren();
  const manual = Object.keys(info.subtitles || {});
  const auto = Object.keys(info.automatic_captions || {});
  const all = [...new Set([...manual, ...auto])];
  const device = String(navigator.language || "").split("-")[0].toLowerCase();
  const rank = (l) => {
    const k = String(l).toLowerCase();
    return k === device ? 0 : (k === "en" || k.startsWith("en-")) ? 1 : 2;
  };
  all.sort((a, b) => rank(a) - rank(b));   // stable: the site's order survives
  $("subsRow").classList.toggle("hidden", !all.length);
  if (!all.length) return;
  const CAP = 14;

  const sync = () => {
    const picked = pickedSubs();
    for (const chip of box.querySelectorAll("button.chip[data-lang]")) {
      const on = picked.includes(chip.dataset.lang);
      chip.classList.toggle("on", on);
      chip.setAttribute("aria-pressed", on);
    }
  };
  const toggle = (lang) => {
    const have = pickedSubs();
    const next = have.includes(lang)
      ? have.filter((x) => x !== lang)
      : [...have, lang];
    $("ovSubLangs").value = next.join(", ");
    if (next.length && !$("ovSubs").value) $("ovSubs").value = "sidecar";
    if (typeof renderOvCount === "function") renderOvCount();
    sync();
    toast(next.length ? `subtitles: ${next.join(", ")}`
                       : "subtitles: none picked");
  };

  for (const lang of (SUBS_EXPANDED ? all : all.slice(0, CAP))) {
    const isAuto = !manual.includes(lang);
    const chip = el("button", "chip", lang + (isAuto ? " (auto)" : ""));
    chip.type = "button";
    chip.dataset.lang = lang;
    chip.title = "subtitles in " + lang + (isAuto ? " (auto-generated)" : "") +
      " — click again to unpick";
    chip.onclick = () => toggle(lang);
    box.append(chip);
  }
  if (all.length > CAP) {
    const more = el("button", "chip more",
      SUBS_EXPANDED ? "less" : `+${all.length - CAP} more`);
    more.type = "button";
    more.onclick = () => { SUBS_EXPANDED = !SUBS_EXPANDED; renderSubsChips(info); };
    box.append(more);
  }
  sync();
}

/** The wish list is per-download and the site is per-video: a language picked
 *  on the last video must not ride into one that does not offer it — the
 *  leftover pick is how "the engine refuses when the language isn't
 *  available" happened (2026-09-27). Prune against THIS probe, and say what
 *  went. A site that reports no subtitles at all is not ours to clear. */
function syncSubLangsWithProbe(info) {
  const field = $("ovSubLangs");
  if (!field || !field.value.trim()) return;
  const available = [...Object.keys(info.subtitles || {}),
                     ...Object.keys(info.automatic_captions || {})];
  if (!available.length) return;
  const gone = pickedSubs().filter((l) => !available.includes(l));
  if (!gone.length) return;
  field.value = pickedSubs().filter((l) => available.includes(l)).join(", ");
  if (typeof renderOvCount === "function") renderOvCount();
  toast(`subtitles: ${gone.join(", ")} — not on this video`);
}

/** Chapters: one click fills the clip start (and end) so a long video can be
 *  clipped at a chapter boundary instead of typing times from memory. */
function renderChapterChips(info) {
  const box = $("chapterChips");
  box.replaceChildren();
  const chapters = (info.chapters || []).slice(0, 20);
  $("chapterRow").classList.toggle("hidden", !chapters.length);
  for (const ch of chapters) {
    if (ch.start_time == null) continue;
    const start = clock(ch.start_time);
    const chip = el("button", "chip", ch.title || start);
    chip.type = "button";
    chip.title = "clip " + start +
      (ch.end_time != null ? " → " + clock(ch.end_time) : "");
    chip.onclick = () => {
      $("ovClipStart").value = start;
      $("ovClipEnd").value = ch.end_time != null ? clock(ch.end_time) : "";
      if (typeof renderOvCount === "function") renderOvCount();
      toast(`clip: ${ch.title || start}`);
    };
    box.append(chip);
  }
}

function renderProbe(url, info) {
  $("probeCard").classList.remove("hidden");
  $("dlEmpty").classList.add("hidden");
  $("probeTitle").textContent = info.title || url;
  // "0 min" is not a duration: round() alone said a 40-second clip was zero
  // minutes long (polish pass)
  const dur = info.duration
    ? " · " + (info.duration < 60 ? "<1 min"
                                  : Math.round(info.duration / 60) + " min") : "";
  $("probeMeta").textContent = (info.extractor || "") + dur;
  // the probe lands on the scope strip — source, formats, largest (v0.37.0)
  $("probeCard").dataset.livery = liveryOf(info.extractor || "");
  const scopeFmts = (info.formats || []).filter((f) => f.ext && f.format_id);
  const biggest = Math.max(0, ...scopeFmts.map(
    (f) => f.filesize || f.filesize_approx || 0));
  setScopes("live", {
    src: String(info.extractor || (info.playlist ? "playlist" : "direct")).slice(0, 22),
    fmt: info.playlist ? ((info.count || 0) + " items") : String(scopeFmts.length),
    size: biggest ? humanBytes(biggest) : "—",
    say: "take ready — set the deck, press START",
  });

  // the probe has always carried these three; the UI now shows them
  const live = info.is_live === true || info.live_status === "is_live";
  $("liveRow").classList.toggle("hidden", !live);
  SUBS_EXPANDED = false;              // every probe starts folded
  renderSubsChips(info);
  syncSubLangsWithProbe(info);        // a pick this video lacks goes now
  renderChapterChips(info);

  const tb = $("formats").querySelector("tbody");
  tb.innerHTML = "";

  if (info.playlist) {
    $("playlistRow").classList.remove("hidden");
    $("qualityRow").classList.add("hidden");
    $("soundRow").classList.add("hidden");
    $("probeMeta").textContent =
      (info.count ? info.count + " videos" : "playlist") +
      (info.extractor ? " · " + info.extractor : "");
    const entries = info.entries || [];
    PLAYLIST = { count: info.count || entries.length, shown: entries.length };
    PLAYLIST_NONE = false;
    setScopes("live", {
      fmt: (info.count || entries.length) + " items",
      say: "pick items on the deck, then START",
    });
    for (const [i, e] of entries.entries()) {
      const tr = el("tr", "enter");
      // capped lower than a full stagger: a table that takes a quarter second
      // to finish arriving reads as slow
      tr.style.animationDelay = Math.min(i * 30, 150) + "ms";
      const n = e.index || i + 1;
      const pick = el("td", "fmt-q");
      const box = el("input", "plpick");
      box.type = "checkbox";
      box.dataset.index = String(n);
      box.title = "include item " + n;
      box.onchange = syncPlaylistPicks;
      pick.append(el("span", "plnum", String(n)), box);
      tr.append(
        pick,
        el("td", "fmt-c", e.title || e.url || "—"),
        el("td", "fmt-s", e.duration ? Math.round(e.duration / 60) + " min" : "—"),
      );
      tb.append(tr);
    }
    if (info.count && entries.length < info.count) {
      const tr = el("tr");
      tr.append(el("td", "", ""),
                el("td", "muted",
                   `… ${info.count - entries.length} more — tick the listed ` +
                   "ones, or type a range like 501-600"),
                el("td"));
      tb.append(tr);
    }
    syncPlaylistPicks();
    return;
  }

  $("playlistRow").classList.add("hidden");
  PLAYLIST = null;
  PLAYLIST_NONE = false;
  renderQualityRow(url, info.site_quality);
  const usable = (info.formats || []).filter((f) => f.ext && f.format_id);
  // a video-only pick only makes sense to pair with audio when the site
  // actually publishes a separate audio stream (YouTube does, a plain .mp4 doesn't)
  const separateAudio = usable.some((f) => !hasVideo(f) && hasAudio(f));
  const fmts = dedupeFormats(usable)
    .sort((a, b) => (b.height || b.abr || 0) - (a.height || a.abr || 0));

  for (const [i, f] of fmts.entries()) {
    const tr = el("tr", "enter");
    // capped lower than a full stagger: a table that takes a quarter second
    // to finish arriving reads as slow
    tr.style.animationDelay = Math.min(i * 30, 150) + "ms";
    const kind = fmtKind(f, separateAudio);
    const cell = el("td", "fmt-c");
    cell.append(el("div", "", fmtCodecs(f) || "—"));
    const kindEl = el("div", "fmt-kind " + kind.cls, kind.label);
    // the rows the "no sound" tick re-labels carry a mark; a row that never
    // had separate audio says so and must not be re-labelled
    if (kind.sound) kindEl.dataset.sound = "1";
    cell.append(kindEl);
    tr.append(
      el("td", "fmt-q", fmtQuality(f) || "—"),
      cell,
      sizeCell(f),
    );
    const td = el("td");
    const btn = el("button", "get", "Take");
    btn.dataset.pick = fmtSpec(f, separateAudio);
    btn.onclick = () => armTake(btn.dataset.pick, fmtQuality(f) || "this file", btn);
    td.append(btn);
    tr.append(td);
    tb.append(tr);
  }
  // the "no sound" choice shows whenever there is a video row to explain
  // (the playlist branch above hid it again)
  const anyVideo = fmts.some(hasVideo);
  $("soundRow").classList.toggle("hidden", !anyVideo);
  if (!fmts.length) {
    const tr = el("tr");
    tr.append(el("td", "muted", "no formats found"));
    tb.append(tr);
  }
}

/* ---------- jobs ---------- */
/** One-click quality picks for the probed video: the engine owns the format
 *  expressions (see QUALITY_PRESETS) so every shell offers the same list. */
function renderQualityRow(url, remembered) {
  const row = $("qualityRow");
  const box = $("qualityBtns");
  if (!row || !box) return;
  box.innerHTML = "";
  const list = OV.qualities || [];
  if (!list.length) {
    row.classList.add("hidden");
    return;
  }
  for (const q of list) {
    // what you picked for this site last time is marked, not applied: the
    // click is still yours (M20). No chip glows like the lamp before it is
    // armed — "best" included (v0.38.3 audit #4: an unclicked chip read as
    // a second START button).
    const last = remembered && q.key === remembered;
    const btn = el("button", "btn sm" + (last ? " pick" : ""),
      last ? q.label + " · last used" : q.label);
    btn.dataset.pick = q.fmt;
    btn.title = last
      ? "your pick for this site last time — click to arm it as the take"
      : "arm the take at best up to " + q.label + " (" + q.fmt + ")";
    btn.onclick = () => armTake(q.fmt, q.label, btn);
    box.append(btn);
  }
  row.classList.remove("hidden");
}

/** How many jobs are in flight — shown on the Queue tab. */
function renderQueueBadge(jobs) {
  const badge = $("queueCount");
  if (!badge) return;
  const active = (jobs || []).filter((j) =>
    ["queued", "downloading", "merging"].includes(j.status)).length;
  badge.textContent = active > 9 ? "9+" : String(active);
  badge.classList.toggle("hidden", !active);
}

function playlistMode() {
  return !$("playlistRow").classList.contains("hidden");
}

/* --- picking playlist items -------------------------------------------------
   The range field is what the engine is sent (blank = every item). The pick
   list edits the part of the playlist it shows; the field keeps anything the
   list cannot represent, so a typed range is never silently narrowed
   (v0.21.1 audit: "1-600" on a 500-entry probe became "1-500"). */

// what the playlist on screen really holds, and whether "None" was pressed
// (blank means *everything* to the engine, so "none" needs its own state)
let PLAYLIST = null;
let PLAYLIST_NONE = false;

/** "1-5,8" → {1,2,3,4,5,8}; null when it is not a range at all (blank = all). */
function parseItemRange(text) {
  const out = new Set();
  if (!text) return null;
  for (const part of text.split(",")) {
    const t = part.trim();
    if (!t) continue;
    const m = t.match(/^(\d+)\s*-\s*(\d+)$/);
    if (m) {
      const a = Number(m[1]);
      const b = Number(m[2]);
      if (a < 1 || b < a || b - a > 5000) return null;
      for (let i = a; i <= b; i++) out.add(i);
    } else if (/^\d+$/.test(t)) {
      if (Number(t) < 1) return null;
      out.add(Number(t));
    } else {
      return null;
    }
  }
  return out;
}

function pickedBoxes() {
  return Array.from(document.querySelectorAll("#formats .plpick"));
}

/** The picked items, in the syntax the field and the engine speak. */
function selectedPlaylistItems() {
  return pickedBoxes()
    .filter((b) => b.checked)
    .map((b) => Number(b.dataset.index))
    .sort((a, b) => a - b)
    .join(",");
}

function playlistFieldText() {
  return (($("playlistItems") || {}).value || "").trim();
}

/** One place decides what the pick label and the button say. */
function renderPlaylistState() {
  const label = $("plCount");
  const btn = $("playlistBtn");
  if (!btn) return;
  const boxes = pickedBoxes();
  const shown = boxes.length;
  const total = (PLAYLIST && PLAYLIST.count) || shown;
  const text = playlistFieldText();
  const want = text ? parseItemRange(text) : null;
  const junk = text && want === null;
  const none = PLAYLIST_NONE && !text;
  const count = want ? want.size : 0;
  if (boxes.some((b) => b.checked)) PLAYLIST_NONE = false;
  if (label) {
    label.textContent = junk ? "type a range like 1-5,8"
      : none ? "none picked"
      : text ? `${count} picked` + (count <= total ? ` of ${total}` : "")
      : `all ${total}` + (shown < total ? ` · first ${shown} listed` : "");
  }
  btn.disabled = Boolean(junk || none);
  btn.textContent = junk ? "fix the range"
    : none ? "pick items first"
    : text ? `Download ${count} picked` : "Download playlist";
}

function syncPlaylistPicks() {
  const boxes = pickedBoxes();
  const shown = new Set(boxes.map((b) => Number(b.dataset.index)));
  const text = playlistFieldText();
  const want = text ? parseItemRange(text) : null;
  // boxes -> field, but only for indices the list can show: a range reaching
  // past the listed entries stays exactly as typed
  const representable = text ? (want !== null &&
    [...want].every((i) => shown.has(i))) : true;
  if (representable) {
    const value = selectedPlaylistItems();
    if ($("playlistItems").value !== value) $("playlistItems").value = value;
    // unchecking the last box has to mean NOTHING, never "all": an empty
    // field is the engine's word for the whole playlist, so arm the same
    // refusal the None button uses (UI review — this was the trap v0.21.2
    // closed for None, still open on the manual path)
    if (boxes.length > 0 && !boxes.some((b) => b.checked)) PLAYLIST_NONE = true;
  }
  renderPlaylistState();
}

/** A typed range ticks the matching boxes back; junk is shown, not hidden. */
function checkboxFromRange() {
  const text = playlistFieldText();
  const want = text ? parseItemRange(text) : null;
  if (text && want === null) { renderPlaylistState(); return; }
  PLAYLIST_NONE = false;
  for (const b of pickedBoxes()) {
    b.checked = want === null ? false : want.has(Number(b.dataset.index));
  }
  syncPlaylistPicks();
}

function pickAll(checked) {
  const boxes = pickedBoxes();
  for (const b of boxes) b.checked = checked;
  // "All" means the listed items; "None" means nothing at all — it must never
  // fall back to the blank field, which the engine reads as the whole playlist
  $("playlistItems").value = checked ? selectedPlaylistItems() : "";
  PLAYLIST_NONE = !checked && boxes.length > 0;
  renderPlaylistState();
}

async function startJob(url, fmt, preset, playlist, triggerBtn) {
  if (playlist && PLAYLIST_NONE && !playlistFieldText()) {
    toast("pick at least one item first", "bad");
    return false;
  }
  if (!url) {
    toast("paste a video link first", "bad");
    return false;
  }
  // A start can take most of a second (SQLite lock, a busy worker), and a
  // button that does not move invites a second and third tap — which queued
  // the same video twice (motion review). Disable it for the round-trip.
  if (triggerBtn) {
    triggerBtn.disabled = true;
    triggerBtn.classList.add("busy");
  }
  try {
    const body = { url };
    if (fmt) body.fmt = fmt;
    // the audio intent only applies when no explicit format was picked
    // (yt-dlp refuses fmt + preset together)
    const audio = fmt ? null : (preset || OV.preset);
    if (audio) body.preset = audio;
    if (playlist) body.playlist_items = playlistFieldText();
    let ov = readOv();
    // the "no sound" tick rides every start from this card — a format chip,
    // "best quality", or the whole playlist: no_audio is the engine's key
    // for "do not pair this video with the site's audio" (2026-09-27)
    if ($("noSound").checked) ov = { ...(ov || {}), no_audio: true };
    if (ov) body.overrides = ov;
    // say what rode — and what a format pick silently replaced: jobs used to
    // report a bare "Added to downloads" either way (v0.35.0)
    const ovK = ov ? Object.keys(ov).length : 0;
    const note = (fmt && OV.preset)
      ? ` — “${OV.name || OV.preset}” skipped: your format pick replaces it`
      : (OV.name && (body.preset === OV.preset || ovK)
        ? ` — with preset “${OV.name}”`
        : (ovK ? ` — with ${ovK} option${ovK === 1 ? "" : "s"} set below`
          : (TAKE.label ? " — " + TAKE.label : "")));
    await api("/jobs", { method: "POST", body: JSON.stringify(body) });
    // the block says "this download only" — so it is spent on this download
    // (v0.21.1 audit: it used to stick to every job for the rest of the session)
    clearOv();
    PLAYLIST_NONE = false;
    toast((playlist ? "Playlist added to downloads" : "Added to downloads") + note, "info");
    refreshJobs();
    return true;
  } catch (e) {
    toast("could not start download: " + e.message, "bad");
    return false;
  } finally {
    if (triggerBtn) {
      triggerBtn.disabled = false;
      triggerBtn.classList.remove("busy");
    }
  }
}

/* --- "This download only": a patch over the saved settings ---------------- */

// the audio intent of an applied preset (fmt and preset are exclusive in yt-dlp)
// plus its full patch: the block only shows a few of the options a preset may
// carry, so the rest must ride along instead of being lost on apply
// OV.name remembers WHICH preset is applied, so the block can show what it
// carries and offer to update it (v0.34.0)
const OV = { preset: null, name: null, patch: {}, defaults: null, perJobKeys: null };

/** The block's values as a patch — only what the user actually set.
 *  A field the user emptied or unticked *removes* the preset's value too:
 *  otherwise the form says "use my settings" while the download does not
 *  (v0.21.1 audit). */
function readOv() {
  const patch = { ...(OV.patch || {}) };
  const subs = $("ovSubs").value;
  if (subs) {
    patch.subtitles_mode = subs;
    const langs = $("ovSubLangs").value.trim();
    delete patch.subtitles_langs;          // no field, no claim
    if (langs) patch.subtitles_langs = langs;
  } else {
    delete patch.subtitles_mode;
    delete patch.subtitles_langs;
  }
  const sb = $("ovSb").value;
  if (sb) patch.sponsorblock_mode = sb; else delete patch.sponsorblock_mode;
  // three-state: "" = use my settings, "on"/"off" = a claim about this job.
  // A checkbox could only express "on", so switching a global embed off for
  // one download was impossible (v0.21.2 audit).
  const meta = $("ovMeta").value;
  if (meta === "on") patch.embed_metadata = true;
  else if (meta === "off") patch.embed_metadata = false;
  else delete patch.embed_metadata;
  const thumb = $("ovThumb").value;
  if (thumb === "on") patch.embed_thumbnail = true;
  else if (thumb === "off") patch.embed_thumbnail = false;
  else delete patch.embed_thumbnail;
  const raw = $("ovRaw").value.trim();
  if (raw) patch.raw_args = raw; else delete patch.raw_args;
  // clip: both times or none — half a range is not a range
  const clipStart = $("ovClipStart").value.trim();
  const clipEnd = $("ovClipEnd").value.trim();
  if (clipStart && clipEnd) patch.download_sections = `${clipStart}-${clipEnd}`;
  else delete patch.download_sections;
  const container = $("ovContainer").value;
  if (container) patch.video_container = container;
  else delete patch.video_container;
  if ($("ovArchive").value === "ignore") patch.archive_ignore = true;
  else delete patch.archive_ignore;
  return Object.keys(patch).length ? patch : null;
}

function clearOv() {
  OV.preset = null;
  OV.name = null;
  OV.patch = {};
  $("ovSubs").value = "";
  $("ovSubLangs").value = "";
  $("ovSb").value = "";
  $("ovMeta").value = "";
  $("ovThumb").value = "";
  $("ovRaw").value = "";
  $("ovClipStart").value = "";
  $("ovClipEnd").value = "";
  $("ovContainer").value = "";
  $("ovArchive").value = "";
  $("ovPreset").value = "";
  $("ovSaveRow").classList.add("hidden");
  $("ovSaveMsg").classList.add("hidden");
  $("ovSaveName").value = "";
  renderOvCount();
  renderOvPresetInfo();
  renderOvPresetActions();
}

/** 300+ rows must not become 300 tab stops: the catalogue owns ONE, and the
 *  arrow keys move inside it (the standard roving-tabindex pattern). Enter or
 *  Space picks, exactly as a click does. Without this the whole yt-dlp option
 *  browser was mouse-only (motion review). */
function makeOptionRowReachable(row, activate) {
  row.tabIndex = -1;
  row.setAttribute("role", "button");
  row.addEventListener("focus", () => {
    const list = row.closest(".optlist");
    if (!list) return;
    list.querySelectorAll('.optrow[tabindex="0"]')
      .forEach((r) => { r.tabIndex = -1; });
    row.tabIndex = 0;
  });
  row.addEventListener("keydown", (e) => {
    const list = row.closest(".optlist");
    if (!list) return;
    const rows = [...list.querySelectorAll(".optrow")];
    const i = rows.indexOf(row);
    if (e.key === "ArrowDown" && i >= 0 && i < rows.length - 1) {
      e.preventDefault();
      rows[i + 1].focus();
    } else if (e.key === "ArrowUp" && i > 0) {
      e.preventDefault();
      rows[i - 1].focus();
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      const target = e.key === "Home" ? rows[0] : rows[rows.length - 1];
      if (target) target.focus();
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      activate();
    }
  });
}

/** The single tab stop for the option list: focusing it lands on the first
 *  row, so Tab from the search box can reach the catalogue at all. */
function initOptionListKeyboard() {
  const list = $("optionsList");
  if (!list || list.tabIndex >= 0) return;
  list.tabIndex = 0;
  list.addEventListener("focus", () => {
    if (document.activeElement === list) {
      const first = list.querySelector(".optrow");
      if (first) first.focus();
    }
  });
}

/** The little "N options" chip on the collapsed summary. */
function renderOvCount() {
  const patch = readOv();
  const n = (patch ? Object.keys(patch).length : 0) + (OV.preset ? 1 : 0);
  // the same count, echoed on the card where the downloads actually start:
  // an armed preset used to be visible only in the collapsed block below the
  // formats table — nowhere near "Download best quality" (v0.35.0)
  const bar = $("armedBar");
  const txt = $("armedText");
  if (!n) {
    bar.classList.add("hidden");
    txt.textContent = "";
  } else {
    const entry = OV.name
      ? (PRESETS || []).find((p) => p.name === OV.name) : null;
    const k = patch ? Object.keys(patch).length : 0;
    const what = entry
      ? "“" + entry.name + "”" + (entry.description ? " — " + entry.description : "")
      : OV.name ? "“" + OV.name + "”"
        : k + " option" + (k === 1 ? "" : "s") + " set below";
    txt.textContent = "next download: " + what;
    bar.classList.remove("hidden");
  }
  const chip = $("ovCount");
  if (!n) {
    chip.classList.add("hidden");
    chip.textContent = "";
    chip.removeAttribute("title");
    return;
  }
  const parts = [];
  if (OV.preset) parts.push(OV.preset.replace(/^(audio|video)-/, ""));
  if (patch) parts.push(Object.keys(patch).length + " option" +
    (Object.keys(patch).length === 1 ? "" : "s"));
  chip.textContent = parts.join(" · ");
  // name them on hover/for screen readers: the chip says how many, but the
  // question people actually have is WHICH — a leftover clip or subtitle
  // filter from a preset used to be invisible until the download was wrong
  // (motion review)
  const keys = patch ? Object.keys(patch) : [];
  chip.title = [OV.preset ? "preset " + OV.preset : "", ...keys]
    .filter(Boolean).join(", ");
  chip.setAttribute("aria-label", chip.title
    ? "active for this download: " + chip.title : "");
  chip.classList.remove("hidden");
}

/** Apply a preset's patch to the block (and remember its audio intent). */
function applyOvPreset() {
  const name = $("ovPreset").value;
  if (!name) return;
  const entry = (PRESETS || []).find((p) => p.name === name);
  if (!entry) return;
  clearOv();
  const patch = entry.patch || {};
  OV.preset = patch.preset || null;
  OV.name = name;
  // keep every option the preset carries, even the ones the block cannot show
  OV.patch = { ...patch };
  delete OV.patch.preset;
  if (patch.subtitles_mode) $("ovSubs").value = patch.subtitles_mode;
  if (patch.subtitles_langs) $("ovSubLangs").value = patch.subtitles_langs;
  if (patch.sponsorblock_mode) $("ovSb").value = patch.sponsorblock_mode;
  // a preset that says "off" must show as off: with a checkbox it looked
  // untouched, and the next read re-sent the preset without the claim
  $("ovMeta").value =
    patch.embed_metadata === true ? "on"
      : patch.embed_metadata === false ? "off" : "";
  $("ovThumb").value =
    patch.embed_thumbnail === true ? "on"
      : patch.embed_thumbnail === false ? "off" : "";
  if (patch.raw_args) $("ovRaw").value = patch.raw_args;
  if (patch.download_sections) {
    // the preset stores one string; the block shows two fields
    const [start, end] = String(patch.download_sections)
      .replace(/^\*/, "").split("-");
    $("ovClipStart").value = (start || "").trim();
    $("ovClipEnd").value = (end || "").trim();
  }
  if (patch.video_container) $("ovContainer").value = patch.video_container;
  if (patch.archive_ignore) $("ovArchive").value = "ignore";
  $("ovPreset").value = name;
  renderOvCount();
  renderOvPresetInfo();
  renderOvPresetActions();
  const n = Object.keys(readOv() || {}).length + (OV.preset ? 1 : 0);
  toast(`preset “${name}” applied — ${n} option(s) for the next download`);
}

/** What the applied preset carries, spelled out — the block shows a few of
 *  these fields, but a preset may set options it has no field for, and those
 *  used to ride invisibly (v0.34.0). */
function renderOvPresetInfo() {
  const box = $("ovPresetInfo");
  const entry = OV.name
    ? (PRESETS || []).find((p) => p.name === OV.name) : null;
  if (!entry) {
    box.classList.add("hidden");
    box.textContent = "";
    return;
  }
  const patch = entry.patch || {};
  const sets = Object.keys(patch).map((k) => k + "=" + patch[k]).join(" · ");
  box.textContent = `preset “${entry.name}”`
    + (entry.builtin ? " (built-in)" : "")
    + (entry.description ? ` — ${entry.description}` : "")
    + (sets ? ` · sets ${sets}` : "");
  box.classList.remove("hidden");
}

/** "Update “name”" exists only for the user's own presets: a built-in is
 *  code, and overwriting it is not a thing — save a copy instead. */
function renderOvPresetActions() {
  const upd = $("ovUpdate");
  const entry = OV.name
    ? (PRESETS || []).find((p) => p.name === OV.name) : null;
  if (entry && !entry.builtin) {
    upd.textContent = `Update “${entry.name}”`;
    upd.title = "write the fields above into this preset";
    upd.classList.remove("hidden");
  } else {
    upd.classList.add("hidden");
  }
}

/** The block's fields as a patch — exactly what a download would carry. */
function presetFromPanel() {
  const patch = { ...(readOv() || {}) };
  if (OV.preset) patch.preset = OV.preset;
  return patch;
}

function showOvSaveMsg(text, cls) {
  const msg = $("ovSaveMsg");
  msg.textContent = text;
  msg.className = "msg " + cls;
}

async function savePanelPreset() {
  const name = $("ovSaveName").value.trim();
  const patch = presetFromPanel();
  if (!Object.keys(patch).length) {
    showOvSaveMsg("set an option first — a preset needs at least one", "warn");
    return;
  }
  if (!name) {
    showOvSaveMsg("give it a name first", "warn");
    return;
  }
  try {
    await api("/presets", { method: "POST", body: JSON.stringify({ name, patch }) });
    $("ovSaveMsg").classList.add("hidden");
    $("ovSaveRow").classList.add("hidden");
    $("ovSaveName").value = "";
    OV.name = name;               // it is what the block now carries
    await loadPresets();          // dropdown (selects it), info line, Settings
    toast(`saved “${name}” — ${Object.keys(patch).length} option(s)`);
  } catch (e) {
    showOvSaveMsg("could not save: " + e.message, "bad");
  }
}

async function updatePanelPreset() {
  const entry = OV.name
    ? (PRESETS || []).find((p) => p.name === OV.name) : null;
  if (!entry || entry.builtin) return;
  const patch = presetFromPanel();
  if (!Object.keys(patch).length) {
    toast("set an option first — a preset needs at least one", "bad");
    return;
  }
  try {
    await api("/presets", { method: "POST",
                            body: JSON.stringify({ name: entry.name, patch }) });
    await loadPresets();
    toast(`“${entry.name}” updated — ${Object.keys(patch).length} option(s)`);
  } catch (e) {
    toast("could not update: " + e.message, "bad");
  }
}

function renderOvPresets() {
  const sel = $("ovPreset");
  const keep = sel.value;
  sel.innerHTML = "";
  const blank = el("option", "", "— apply a preset —");
  blank.value = "";
  sel.append(blank);
  const groups = [[true, "built-in"], [false, "saved"]];
  for (const [builtin, label] of groups) {
    const items = (PRESETS || []).filter((p) => !!p.builtin === builtin);
    if (!items.length) continue;
    const group = document.createElement("optgroup");
    group.label = label;
    for (const p of items) {
      const o = el("option", "", p.name +
        (p.description ? " — " + p.description : ""));
      o.value = p.name;
      group.append(o);
    }
    sel.append(group);
  }
  // the select mirrors which preset is APPLIED (OV.name), not a stale pick:
  // a freshly saved preset only becomes selectable after this re-render
  sel.value = (OV.name && Array.from(sel.options).some((o) => o.value === OV.name))
    ? OV.name : keep;
}

function initOverrides() {
  $("ovApply").onclick = applyOvPreset;
  $("ovClear").onclick = () => { clearOv(); toast("cleared — using your settings"); };
  // the preset row grows the two actions it used to lack (v0.34.0): save
  // the block as a preset, and write the fields back into the applied one
  $("ovSaveLink").onclick = () => {
    $("ovSaveRow").classList.remove("hidden");
    $("ovSaveMsg").classList.add("hidden");
    $("ovSaveMsg").textContent = "";
    $("ovSaveName").focus();
  };
  $("ovSaveGo").onclick = savePanelPreset;
  $("ovSaveCancel").onclick = () => {
    $("ovSaveRow").classList.add("hidden");
    $("ovSaveMsg").classList.add("hidden");
    $("ovSaveMsg").textContent = "";
  };
  $("ovUpdate").onclick = updatePanelPreset;
  $("ovSaveName").addEventListener("keydown", (e) => {
    if (e.key === "Enter") savePanelPreset();
  });
  // the "whole video" button sat in the clip row since v0.22.0 with nothing
  // attached to it (UI review): pressing it did nothing at all
  $("ovClipClear").onclick = () => {
    $("ovClipStart").value = "";
    $("ovClipEnd").value = "";
    renderOvCount();
  };
  // the strip's clear button is the block's Clear; tapping its text brings
  // the block in — the card echoes the block, it does not duplicate it (v0.35.0)
  $("armedClear").onclick = () => {
    clearOv();
    toast("cleared — using your settings");
  };
  $("armedText").tabIndex = 0;
  $("armedText").setAttribute("role", "button");
  $("armedText").onkeydown = (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    $("armedText").onclick();   // one behaviour, two doors (v0.38.3 audit #12)
  };
  $("armedText").onclick = () => {
    $("ovBlock").open = true;
    // instant, not smooth: a smooth scroll proved inert in the stripped-down
    // headless browser — and a tap that appears to do nothing is worse than
    // a jump (v0.35.0)
    $("ovBlock").scrollIntoView({ block: "start" });
  };
  for (const id of ["ovSubs", "ovSubLangs", "ovSb", "ovMeta", "ovThumb", "ovRaw",
                    "ovClipStart", "ovClipEnd", "ovContainer", "ovArchive"]) {
    $(id).addEventListener("input", renderOvCount);
    $(id).addEventListener("change", renderOvCount);
  }
}

function progressPct(j) {
  const t = j.progress && j.progress.total_bytes;
  return t ? Math.min(100, (j.progress.downloaded_bytes / t) * 100) : 0;
}

function jobSig(j) {
  return j.status + "|" + (j.filepath ? "p" : "") + "|" + (j.error ? "e" : "");
}

function metaParts(j) {
  const downloading = j.status === "downloading";
  const pct = Math.round(progressPct(j));
  const spd = j.progress && j.progress.speed ? humanBytes(j.progress.speed) + "/s" : "";
  const eta = j.progress && j.progress.eta != null ? "ETA " + j.progress.eta + "s" : "";
  const pl = j.progress && j.progress.playlist_index && j.progress.playlist_count
    ? "video " + j.progress.playlist_index + "/" + j.progress.playlist_count : "";
  const size = `${humanBytes(j.progress && j.progress.downloaded_bytes)} / ${humanBytes(j.progress && j.progress.total_bytes)}`;
  // A queued or merging job has no percentage worth printing ("0%" beside a
  // moving bar reads as a stall) and nothing has been fetched yet, so its
  // bytes read as "0 B / 0 B" — show only what is actually known.
  const known = j.progress && (j.progress.total_bytes || j.progress.downloaded_bytes);
  return [...(pl ? [pl] : []), ...(downloading ? [pct + "%"] : []),
          ...(spd ? [spd] : []), ...(eta ? [eta] : []), ...(known ? [size] : [])];
}

/** Stop a still-running job (cancel + wait for the worker), then delete it. */
async function settleThenDelete(job) {
  if (ACTIVE.has(job.status)) {
    await api(`/jobs/${job.id}/cancel`, { method: "POST" });
    for (let i = 0; i < 12; i++) {
      const { jobs } = await api("/jobs");
      const cur = jobs.find((x) => x.id === job.id);
      if (!cur || !ACTIVE.has(cur.status)) break;
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  return api(`/jobs/${job.id}/delete`, { method: "POST" });
}

/** The trash button — one download gone, file and all, after a confirm. */
function deleteButton(j) {
  const running = ACTIVE.has(j.status);
  const b = el("button", "ghost-sm del", "Delete");
  b.prepend(ico("trash"));
  b.title = "Delete this download — the file on disk goes with it";
  b.onclick = async () => {
    const name = j.filepath ? j.filepath.split("/").pop()
      : String(j.title || j.url).slice(0, 60);
    const msg = (running ? `Stop “${name}” and delete the partial file?`
      : j.filepath ? `Delete “${name}”?`
        : `Remove “${name}” from the list?`)
      + (j.filepath && GALLERY() ? " Its Gallery/Music copy goes too." : "")
      + " This cannot be undone.";
    if (!(await askConfirm(msg, { okText: running ? "Stop and delete" : "Delete" }))) {
      return;
    }
    // The settle can take up to three seconds (cancel → the worker returns →
    // the delete lands). The confirm dialog is gone by then, so without a mark
    // the row sat there looking untouched and people clicked Delete again
    // (motion review). `.pending` dims it and says what is happening.
    const row = $("jobs").querySelector(`.job[data-id="${j.id}"]`);
    if (row) {
      row.classList.add("pending");
      const pill = row.querySelector(".pill");
      if (pill) pill.textContent = running ? "stopping…" : "deleting…";
    }
    try {
      const r = await settleThenDelete(j);
      // Gallery cleanup: one name per file. A playlist row's filepath is the
      // download *folder*, so the old code asked the gallery to delete a
      // folder name that matched nothing (v0.21.2 audit).
      if (ANDROID() && window.AndroidHost.deleteMediaNamed) {
        const names = (j.files && j.files.length ? j.files : [j.filepath || ""])
          .map((p) => String(p).split("/").pop()).filter(Boolean);
        for (const name of names) {
          try { window.AndroidHost.deleteMediaNamed(name); }
          catch (_) { /* the row is gone either way */ }
        }
      }
      toast(r.deleted
        ? `deleted ${r.deleted} file${r.deleted === 1 ? "" : "s"} · ` +
          `freed ${humanBytes(r.freed_bytes)}`
        : "removed from the list");
      refreshJobs();
      // a delete empties part of the folder the Settings row reports on: keep
      // that row from reading stale (the "Delete 0 files (0 B)?" bug)
      if (refreshStorageInfo) refreshStorageInfo();
    } catch (e) {
      toast("could not delete: " + e.message, "bad");
      if (row) row.classList.remove("pending");   // the row is staying: undo it
    }
  };
  return b;
}

function jobRow(j) {
  const row = el("div", "job");
  const top = el("div", "jobtop");
  const title = el("span", "jobtitle", j.title || j.url);
  title.title = j.url;
  // the title ellipsises on a phone and nothing hover-reveals it there: a
  // tap unfolds the whole line (2026-10-01 report). v0.38.3: it is a real
  // button to the keyboard too — focus, Enter/Space, and the expanded state
  // announced — while keeping the exact same click wiring.
  title.tabIndex = 0;
  title.setAttribute("role", "button");
  title.setAttribute("aria-expanded", "false");
  title.onclick = () => {
    title.classList.toggle("open");
    title.setAttribute("aria-expanded",
      title.classList.contains("open") ? "true" : "false");
  };
  title.onkeydown = (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    title.onclick();
  };
  top.append(title, el("span", "pill " + j.status, j.status));
  // a finished take gets the stamp (v0.37.0: completion used to be a pill
  // you never saw flip in a tab you were not on)
  if (j.status === "completed") {
    const stamp = el("span", "stamp", "FILED");
    stamp.title = "download finished — the file is in your downloads";
    top.append(stamp);
  }
  // what this job actually carries (preset / per-download overrides)
  const extra = j.overrides ? Object.keys(j.overrides).length : 0;
  if (j.preset) {
    const chip = el("span", "chip tag", j.preset.replace("audio-", "") + " preset");
    chip.title = "audio preset: " + j.preset;
    top.append(chip);
  }
  if (extra) {
    const chip = el("span", "chip tag",
      extra + " option" + (extra === 1 ? "" : "s"));
    chip.title = Object.keys(j.overrides).join(", ") + " — this download only";
    top.append(chip);
  }
  row.append(top);

  let trashHost = null;   // the button row the trash belongs to

  if (ACTIVE.has(j.status)) {
    // Every active state gets a bar: "downloading" carries real progress, and
    // queued/merging get an indeterminate track. A 15–45s ffmpeg mux with no
    // motion anywhere reads as a hung engine (motion review).
    const downloading = j.status === "downloading";
    const bar = el("div", "bar");
    const fill = el("div", "fill active" + (downloading ? "" : " indet"));
    fill.style.width = downloading ? progressPct(j).toFixed(1) + "%" : "100%";
    bar.append(fill);
    row.append(bar);
    const meta = el("div", "jmeta");
    meta.append(...metaParts(j).map((t) => el("span", "", t)));
    row.append(meta);
  } else if (j.status === "error" || j.status === "interrupted") {
    // the human consequence leads; the engine's own dialect goes below,
    // behind the toggle (v0.37.0 — it used to be the first thing you read)
    row.append(el("div", "jerrsay", humanErr(j.error || "")));
    // The whole message. A 160-char slice in a single ellipsised line cut
    // yt-dlp's explanation down to "ERROR: Unable to down…" — the part that
    // says what to do next was exactly the part that was hidden. Long text
    // starts clamped to two lines; a tap unfolds it (2026-09-27 report).
    // v0.37.1: it reads at its own full width — it used to share one flex
    // line with the buttons and wrapped to about one word per line on a
    // phone (2026-09-30 photo).
    const errText = j.error || "";
    const errEl = el("div", "jerr", errText);
    errEl.id = "jerr-" + j.id;   // the details toggle names its region
    if (errText.length > 90) {
      errEl.classList.add("clamp");
      errEl.title = "tap to show the whole message";
      errEl.onclick = () => {
        const open = errEl.classList.toggle("open");
        errEl.title = open ? "tap to collapse" : "tap to show the whole message";
      };
    }
    row.append(errEl);
    const r = el("div", "jrow");
    if (errEl.classList.contains("clamp")) {
      // a visible affordance, not just a hidden cursor (v0.37.0)
      const more = el("button", "linkbtn jrr-toggle", "Show details");
      more.setAttribute("aria-expanded", "false");
      more.setAttribute("aria-controls", errEl.id || "");
      more.onclick = () => {
        const open = errEl.classList.toggle("open");
        errEl.title = open ? "tap to collapse" : "tap to show the whole message";
        more.textContent = open ? "Hide details" : "Show details";
        more.setAttribute("aria-expanded", open ? "true" : "false");
      };
      r.append(more);
    }
    const copy = el("button", "ghost-sm", "Copy");
    copy.title = "copy the whole message";
    copy.onclick = async () => {
      const ok = await copyText(errText);
      toast(ok ? "error copied" : "copy failed", ok ? "ok" : "bad");
    };
    const retry = el("button", "ghost-sm", "Retry");
    retry.onclick = () => api(`/jobs/${j.id}/retry`, { method: "POST" })
      .then(refreshJobs).catch((e) => toast("retry failed: " + e.message, "bad"));
    r.append(copy, retry);
    trashHost = r;
    row.append(r);
    if (j.error && /ffmpeg/i.test(j.error) &&
        /not found|not installed|No such file/i.test(j.error)) {
      row.append(el("div", "jobhint",
        "This step needs ffmpeg. Use “keep original” for audio-only, or install ffmpeg."));
    }
  } else if (j.filepath) {
    const r = el("div", "jrow");
    r.append(el("span", "path", j.filepath));
    if (DESKTOP) {
      const open = el("button", "ghost-sm", "Open folder");
      open.onclick = () => api(`/jobs/${j.id}/reveal`, { method: "POST" })
        .catch((e) => toast("could not open: " + e.message, "bad"));
      r.append(open);
    }
    // A playlist row's filepath is the download folder, so the row-level
    // hand-offs would ask a player (or another app) to open a directory.
    // The row still owns real files — `files` — so it offers them, each
    // with the same Open / Share / Play a single-file row has (2026-09-27
    // report: "There's no open and share button for the playlist").
    //
    // A merged single-file download is NOT a playlist: its `files` also
    // lists the video/audio fragments it muxed (master.f200.mp4, …), but
    // its own filepath is among them — a folder is never (2026-09-27,
    // caught live: a merged row offered "Files (3)" instead of Play).
    const playlistRow = !!(j.files && j.files.length
    && j.files[0] !== j.filepath && !j.files.includes(j.filepath));
    if (playlistRow) {
      const count = j.files.length;
      const toggle = el("button", "ghost-sm", "Files (" + count + ")");
      toggle.title = "show every file this playlist downloaded";
      const listHost = el("div", "jobfiles hidden");
      toggle.onclick = () => {
        const hidden = listHost.classList.toggle("hidden");
        toggle.textContent = hidden
          ? "Files (" + count + ")"
          : "Hide files (" + count + ")";
      };
      for (const file of j.files) listHost.append(jobFileItem(j, file));
      r.append(toggle);
      row.append(listHost);
    } else {
      // Hand off a *file*: Android/data is off-limits to file managers, so
      // hand the file itself to another app (a provider grant).
      if (ANDROID() && j.filepath) {
        const open = el("button", "ghost-sm", "Open");
        open.onclick = () => {
          try { window.AndroidHost.openFile(j.filepath); }
          catch (e) { toast("could not open: " + e.message, "bad"); }
        };
        const share = el("button", "ghost-sm", "Share");
        share.onclick = () => {
          try { window.AndroidHost.shareFile(j.filepath); }
          catch (e) { toast("could not share: " + e.message, "bad"); }
        };
        r.append(open, share);
      }
      // Play it right here (v0.22.0). Works on every platform: the engine
      // answers Range requests, so the player can seek.
      if (j.status === "completed" && j.filepath) {
        const play = el("button", "ghost-sm", "Play");
        play.onclick = () => openPlayer(j);
        r.append(play);
      }
    }
    trashHost = r;
    row.append(r);
    // the unfolded card reads like a receipt (v0.38.2: "other than name show
    // us the file size and the location too — it's expanding for a reason").
    // Collapsed rows keep the compact strip; the title tap unfolds both.
    const details = el("div", "jdetails");
    details.append(
      el("span", "jdlbl", "size"),
      el("span", "jdval", j.size_bytes != null ? humanBytes(j.size_bytes) : "—"),
      el("span", "jdlbl", "saved"),
      el("span", "jdpath", j.filepath || "—"),
    );
    row.append(details);
    if (j.note) row.append(el("div", "jobhint", j.note));
  }

  if (j.raw_args) {
    row.append(el("div", "jobhint", "yt-dlp args: " + j.raw_args));
  }

  const actions = el("div", "jrow");
  if (ACTIVE.has(j.status)) {
    // pause keeps the bytes already fetched; cancel throws them away
    // (v0.22.0 review #6)
    const pause = el("button", "ghost-sm", "Pause");
    pause.onclick = () => api(`/jobs/${j.id}/pause`, { method: "POST" })
      .then(refreshJobs).catch((e) => toast("pause failed: " + e.message, "bad"));
    const c = el("button", "ghost-sm", "Cancel");
    c.onclick = () => api(`/jobs/${j.id}/cancel`, { method: "POST" })
      .then(refreshJobs).catch((e) => toast("cancel failed: " + e.message, "bad"));
    actions.append(pause, c);
  } else if (j.status === "paused") {
    const res = el("button", "ghost-sm", "Resume");
    res.onclick = () => api(`/jobs/${j.id}/resume`, { method: "POST" })
      .then(refreshJobs).catch((e) => toast("resume failed: " + e.message, "bad"));
    actions.append(res);
  } else if (j.status === "cancelled") {
    // a cancelled job shows no error line of its own, so its retry lives here
    const r = el("button", "ghost-sm", "Retry");
    r.onclick = () => api(`/jobs/${j.id}/retry`, { method: "POST" })
      .then(refreshJobs).catch((e) => toast("retry failed: " + e.message, "bad"));
    actions.append(r);
  } else if (j.status === "error" || j.status === "interrupted") {
    // only "Edit & retry": the plain Retry already sits beside the error
    // message above, and two buttons doing one thing made failed rows look
    // broken (UI review)
    const edit = el("button", "ghost-sm", "Edit & retry");
    edit.title = "load this job's URL and options into the Download tab";
    edit.onclick = () => editAndRetry(j);
    actions.append(edit);
  }
  // every row can be deleted (a running one is stopped first, after a confirm)
  if (!trashHost) trashHost = actions;
  trashHost.append(deleteButton(j));
  if (actions.children.length) row.append(actions);
  row.dataset.sig = jobSig(j);
  return row;
}

/** One entry of a playlist's file list: the same hand-offs a single-file
 *  row has, applied to the entry itself (2026-09-27). */
function jobFileItem(j, file) {
  const item = el("div", "jitem");
  const name = String(file).split("/").pop();
  const label = el("span", "jname", name);
  label.title = file;
  item.append(label);
  if (ANDROID() && window.AndroidHost) {
    const open = el("button", "ghost-sm", "Open");
    open.onclick = () => {
      try { window.AndroidHost.openFile(file); }
      catch (e) { toast("could not open: " + e.message, "bad"); }
    };
    const share = el("button", "ghost-sm", "Share");
    share.onclick = () => {
      try { window.AndroidHost.shareFile(file); }
      catch (e) { toast("could not share: " + e.message, "bad"); }
    };
    item.append(open, share);
  }
  if (j.status === "completed") {
    const play = el("button", "ghost-sm", "Play");
    play.onclick = () => openPlayer(j, file);
    item.append(play);
  }
  return item;
}

/** Patch an existing row in place (smooth progress); rebuild on status change. */
function updateJobRow(row, j) {
  if (row.dataset.sig !== jobSig(j)) {
    const fresh = jobRow(j);
    fresh.dataset.id = j.id;
    fresh.classList.add("swap");
    row.replaceWith(fresh);
    return fresh;
  }
  const title = row.querySelector(".jobtitle");
  const text = j.title || j.url;
  if (title && title.textContent !== text) title.textContent = text;
  const fill = row.querySelector(".fill");
  if (fill && !fill.classList.contains("indet")) {
    fill.style.width = progressPct(j).toFixed(1) + "%";
  }
  const meta = row.querySelector(".jmeta");
  if (meta) meta.replaceChildren(...metaParts(j).map((t) => el("span", "", t)));
  return row;
}

let JOBS_SEQ = 0;
let JOBS_BUSY = false;
let JOBS_FAILS = 0;

/** A poll that keeps failing has to say so: a silently empty queue reads as
 *  "nothing downloaded" when the truth is "could not ask" (v0.21.1 audit). */
function showQueueTrouble(e) {
  const box = $("jobs");
  if (!box || box.querySelector(".trouble")) return;
  box.prepend(el("div", "empty trouble",
    "cannot reach the engine (" + ((e && e.message) || "no answer") +
    ") — retrying every couple of seconds."));
}

/** Take a queue row (or the empty-state box) off screen with an exit.
 *
 *  Deleting used to `remove()` the node between two frames — a glitch next to
 *  toasts, which slide away properly — and it also meant the row was gone
 *  before anyone could see WHICH row left. Transform/opacity only: animating
 *  height would put layout on the main thread on every tick, which is exactly
 *  what the WebView cannot afford. The node is dropped when the animation
 *  ends, with a timer as a backstop for a hidden tab (where animations do not
 *  run and `animationend` never arrives), and the guard keeps a second poll
 *  from restarting an exit already in flight. */
function leaveRow(node) {
  if (!node || node.classList.contains("leaving")) return;
  node.classList.add("leaving");
  let gone = false;
  const drop = () => {
    if (gone) return;
    gone = true;
    node.remove();
  };
  node.addEventListener("animationend", (e) => {
    if (e.target === node) drop();
  });
  setTimeout(drop, 400);
}

/* ---------- a finish that speaks (v0.37.0) ---------- */
/** The queue used to turn a pill green in a tab you were not on. The first
 *  poll that sees a job BECOME `completed` fires one toast with the real
 *  choices — play it, or open the folder it was filed in. */
let JOB_STATE = new Map();

function onFiled(j) {
  const name = j.filepath ? String(j.filepath).split("/").pop()
    : (j.title || j.url);
  const actions = [];
  if (j.filepath) {
    actions.push({ label: "Play", prime: true, onClick: () => openPlayer(j) });
  }
  actions.push({
    label: "Show folder",
    onClick: () => { const b = $("openDir"); if (b) b.click(); },
  });
  toast("Filed — " + name, "ok", { actions: actions });
}

/** The bins rail: the last few finished takes, newest first (v0.37.0). */
function renderBins(list) {
  const box = $("binsList");
  if (!box) return;
  const filed = (list || []).filter((j) => j.status === "completed");
  const count = $("binsCount");
  if (count) count.textContent = filed.length ? String(filed.length) : "";
  box.replaceChildren();
  if (!filed.length) {
    box.append(el("div", "bins-empty muted small",
      "Nothing filed yet — a finished download lands here."));
    return;
  }
  for (const j of filed.slice(0, 8)) {
    const b = el("button", "bin");
    b.type = "button";
    b.title = j.filepath || j.url;
    b.append(el("span", "bin-title", j.title || j.url));
    const file = j.filepath ? String(j.filepath).split("/").pop() : "";
    if (file) b.append(el("span", "bin-meta mono", file));
    b.onclick = () => { if (j.filepath) openPlayer(j); };
    box.append(b);
  }
}

async function refreshJobs() {
  if (JOBS_BUSY) return;      // one poll at a time: a slow, older snapshot
  JOBS_BUSY = true;           // must never repaint newer state
  const seq = ++JOBS_SEQ;
  try {
    const { jobs } = await api("/jobs");
    if (seq !== JOBS_SEQ) return;
    JOBS_FAILS = 0;
    renderQueueBadge(jobs);
    const box = $("jobs");
    // a banner raised by an outage has to die with the outage: it was only
    // ever removed on the non-empty path, so it stayed on screen forever over
    // an empty queue, claiming the engine was unreachable while everything
    // worked (UI review)
    const stale = box.querySelector(".trouble");
    if (stale) stale.remove();
    // the static boot line ("Checking the queue…") yields to real content
    const boot = box.querySelector("#jobsInitial");
    if (boot) boot.remove();
    const list = jobs.sort(
      (a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    // a finish that speaks: the FIRST poll that sees a job become completed
    // says so — once (v0.37.0)
    const seen = new Set();
    for (const j of list) {
      seen.add(j.id);
      const prev = JOB_STATE.get(j.id);
      if (j.status === "completed" && prev && prev !== "completed") onFiled(j);
      JOB_STATE.set(j.id, j.status);
    }
    for (const id of [...JOB_STATE.keys()]) if (!seen.has(id)) JOB_STATE.delete(id);
    renderBins(list);
    if (!list.length) {
      // rows that are gone should leave, not blink out: the same exit the
      // delete path uses, then the empty state fades in behind them
      box.querySelectorAll(".job").forEach(leaveRow);
      if (!box.querySelector(".empty")) {
        box.append(el("div", "empty",
          "Nothing in the queue. Downloads you start land here — finished ones " +
          "stay put so you can open, share or delete them."));
      }
      return;
    }
    const empty = box.querySelector(".empty");
    if (empty) leaveRow(empty);

    const keep = new Set();
    let prev = null;
    for (const j of list) {
      keep.add(j.id);
      let row = box.querySelector(`.job[data-id="${j.id}"]`);
      if (!row) {
        row = jobRow(j);
        row.dataset.id = j.id;
        row.classList.add("enter");
      } else {
        row = updateJobRow(row, j);
      }
      const anchor = prev ? prev.nextElementSibling : box.firstElementChild;
      if (row !== anchor) box.insertBefore(row, anchor);
      prev = row;
    }
    box.querySelectorAll(".job").forEach((r) => {
      if (!keep.has(r.dataset.id)) leaveRow(r);
    });
  } catch (e) {
    if (seq !== JOBS_SEQ) return;
    JOBS_FAILS += 1;
    if (JOBS_FAILS === 3) showQueueTrouble(e);   // then keep retrying quietly
  } finally {
    JOBS_BUSY = false;
  }
}

/* ---------- header ---------- */
async function loadVersions() {
  try {
    const v = await api("/version");
    $("versions").textContent = `engine ${v.engine} · yt-dlp ${v.yt_dlp}`;
    // the yt-dlp tab shows it beside its own update button
    const yv = $("ytdlpVer");
    if (yv) yv.textContent = v.yt_dlp;
  } catch (_) { $("versions").textContent = ""; }
}

/* ---------- app updates --------------------------------------------------- *
 * One check feeds two places: the Settings → General row (always visible, with
 * a way to ask again) and one persistent toast that carries the actual
 * choices. Skip and snooze are per-device, so they live in localStorage —
 * Android loads this UI from a fixed origin (127.0.0.1:8787), so they survive
 * a restart; on desktop the engine port can vary, in which case the notice may
 * ask once more. Nothing here installs anything: "Get it" only opens the
 * release page, because no build of this app can replace itself in place. */
const UPD = {
  skipped: "suravidl.upd.skipped",   // the version the user said no to
  snooze: "suravidl.upd.snooze",     // epoch ms until which to stay quiet
  last: "suravidl.upd.last",         // {at, latest, available, error}
  SNOOZE_MS: 24 * 60 * 60 * 1000,
};
const updStore = {
  get(k, dflt = "") {
    try { const v = localStorage.getItem(k); return v === null ? dflt : v; }
    catch (_) { return dflt; }
  },
  set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* private mode */ } },
};
let UPD_STATE = null;   // the last /update-check answer

function humanSince(ts) {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 90) return "just now";
  const m = Math.round(s / 60);
  if (m < 90) return `${m} minute${m === 1 ? "" : "s"} ago`;
  const h = Math.round(m / 60);
  if (h < 36) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const d = Math.round(h / 24);
  return `${d} day${d === 1 ? "" : "s"} ago`;
}

/** Settings → General → Updates: state, the versions, and what to do. */
function renderUpdateRow() {
  const state = $("updState"), meta = $("updMeta");
  if (!state) return;
  const get = $("updGet"), skip = $("updSkip");
  const u = UPD_STATE;
  let last = null;
  try { last = JSON.parse(updStore.get(UPD.last, "") || "null"); } catch (_) { last = null; }
  const when = last && last.at ? `checked ${humanSince(last.at)}` : "not checked yet";
  const err = (u && u.error) || (last && last.error) || null;
  if (err) {
    state.textContent = "could not check for updates";
    meta.textContent = `${err} · ${when}`;
    get.classList.add("hidden");
    skip.classList.add("hidden");
    return;
  }
  if (!u) {                       // no answer yet: say so, offer the button
    state.textContent = "not checked yet";
    meta.textContent = when;
    get.classList.add("hidden");
    skip.classList.add("hidden");
    return;
  }
  const skipped = !!u.latest && updStore.get(UPD.skipped, "") === u.latest;
  if (u.update_available && u.url) {
    state.textContent = `suravidl ${u.latest} is available`;
    meta.textContent = `you have ${u.current} · ${when}` + (skipped ? " · skipped" : "");
    get.textContent = `Get ${u.latest}`;
    get.classList.remove("hidden");
    get.onclick = () => openExternal(u.url);
    skip.textContent = skipped ? "Stop skipping" : "Skip this version";
    skip.classList.remove("hidden");
    skip.onclick = () => {
      updStore.set(UPD.skipped, skipped ? "" : u.latest);
      renderUpdateRow();
    };
  } else {
    state.textContent = "up to date";
    meta.textContent = `you have ${u.current} · ${when}`;
    get.classList.add("hidden");
    skip.classList.add("hidden");
  }
}

/** The one persistent notice: a toast that waits, with the three answers. */
function showUpdateBanner(u) {
  if (document.querySelector(".toast.update")) return;   // one notice, not a stack
  toast(`suravidl ${u.latest} is available — you have ${u.current}`, "info update", {
    sticky: true,
    actions: [
      { label: `Get ${u.latest}`, prime: true, onClick: () => openExternal(u.url) },
      { label: "Later", onClick: () => {
        updStore.set(UPD.snooze, String(Date.now() + UPD.SNOOZE_MS));
        toast("I'll remind you tomorrow");
      } },
      { label: "Skip this version", onClick: () => {
        updStore.set(UPD.skipped, u.latest);
        toast(`won't ask about ${u.latest} again`);
        renderUpdateRow();
      } },
    ],
  });
}

/** force = the user pressed Check now: show the notice even if skipped/snoozed. */
async function checkAppUpdate(force) {
  try {
    const u = await api("/update-check");
    UPD_STATE = u;
    updStore.set(UPD.last, JSON.stringify({
      at: Date.now(), latest: u.latest || null,
      available: !!u.update_available, error: u.error || null,
    }));
    renderUpdateRow();
    if (!u.update_available || !u.url || u.error) return;
    const skipped = updStore.get(UPD.skipped, "") === u.latest;
    const until = Number(updStore.get(UPD.snooze, "0")) || 0;
    if (force || (!skipped && Date.now() >= until)) showUpdateBanner(u);
  } catch (e) {
    updStore.set(UPD.last, JSON.stringify({
      at: Date.now(), latest: null, available: false,
      error: "the engine did not answer",
    }));
    renderUpdateRow();
  }
}

function wireUpdateRow() {
  const b = $("updCheck");
  if (!b) return;
  b.onclick = async () => {
    const old = b.textContent;
    b.disabled = true;
    b.textContent = "checking…";
    await checkAppUpdate(true);
    b.disabled = false;
    b.textContent = old;
    if (UPD_STATE && UPD_STATE.error) toast("update check failed: " + UPD_STATE.error, "bad");
    else if (UPD_STATE && !UPD_STATE.update_available)
      toast(`you're on the latest version (${UPD_STATE.current})`);
  };
  renderUpdateRow();
}

/** Open a link outside the app shell: host bridge -> desktop opener -> browser. */
function openExternal(url) {
  if (!url) return;
  if (window.AndroidHost && window.AndroidHost.openUrl) {
    try { window.AndroidHost.openUrl(url); return; } catch (_) { /* fall through */ }
  }
  if (APP_INFO && APP_INFO.can_open_url) {
    api("/app/open-url", { method: "POST", body: JSON.stringify({ url }) })
      .catch((e) => toast("could not open browser: " + e.message, "bad"));
    return;
  }
  window.open(url, "_blank", "noopener");
}

$("updateBtn").onclick = async () => {
  const ok = await askConfirm(
    "Run yt-dlp self-update? The engine may briefly stall new jobs.",
    { okText: "Update", danger: false });
  if (!ok) return;
  $("updateBtn").disabled = true;
  const old = $("updateBtn").textContent;
  $("updateBtn").textContent = "updating…";
  try {
    const r = await api("/update", { method: "POST" });
    toast(r.updated ? `yt-dlp updated → ${r.after}` : "yt-dlp already latest");
    loadVersions();          // the tab shows the version next to this button
  } catch (e) {
    toast("update failed: " + e.message, "bad");
  }
  $("updateBtn").textContent = old;
  $("updateBtn").disabled = false;
};

/* ---------- what's new ----------------------------------------------------- *
 * One card per DEVICE after an update: the engine answers with its version and
 * the notes for recent releases, and the UI shows the entries newer than the
 * last version this device has seen (localStorage — the same per-device
 * durability as the update skip/snooze; the Android WebView origin is fixed,
 * so it survives there). A device that has never seen a card gets the CURRENT
 * release's notes — the very first one; after that it is strictly what is new
 * to it. The card waits for "Got it": until then, the next launch asks again. */
const WN = {
  seen: "suravidl.whatsnew.seen", // the engine version this device has seen
  MAX: 3,                         // entries shown for one update, newest first
};

/** "0.32.0" -> [0, 32, 0]; junk floors at 0 so it only ever ranks below real versions. */
function versionTuple(v) {
  return String(v || "").split(".").map((x) => {
    const n = parseInt(x, 10);
    return Number.isFinite(n) ? n : 0;
  });
}

/** a > b ? 1 : a < b ? -1 : 0 — element by element, missing parts are 0. */
function versionCmp(a, b) {
  const A = versionTuple(a), B = versionTuple(b);
  for (let i = 0; i < Math.max(A.length, B.length); i++) {
    const d = (A[i] || 0) - (B[i] || 0);
    if (d) return d > 0 ? 1 : -1;
  }
  return 0;
}

/** The entries this device has not seen yet, newest first, capped. */
function whatsNewFor(seen, entries) {
  const pick = [];
  for (const e of entries || []) {
    if (!e || !e.version) continue;
    if (versionCmp(e.version, seen) <= 0) continue;
    pick.push(e);
    if (pick.length >= WN.MAX) break;
  }
  return pick;
}

function showWhatsNew(entries, version) {
  const box = $("whatsNewList");
  box.innerHTML = "";
  for (const e of entries) {
    const sec = document.createElement("div");
    sec.className = "wnentry";
    const head = document.createElement("div");
    head.className = "wntitle";
    head.textContent = e.title ? `${e.version} — ${e.title}` : e.version;
    sec.appendChild(head);
    const ul = document.createElement("ul");
    for (const item of e.items || []) {
      const li = document.createElement("li");
      li.textContent = item;
      ul.appendChild(li);
    }
    sec.appendChild(ul);
    box.appendChild(sec);
  }
  $("whatsNewDone").onclick = () => dismissWhatsNew(version);
  $("whatsNewClose").onclick = () => dismissWhatsNew(version);
  // Escape and the backdrop close it like every other dialog (v0.38.3
  // audit #2 — it used to toggle `hidden` directly, with no exit transition
  // and no keyboard way out)
  wnVersion = version;
  const modal = $("whatsNewModal");
  modal.onclick = (e) => { if (e.target === modal) dismissWhatsNew(version); };
  openModal(modal);
  $("whatsNewDone").focus({ preventScroll: true });
}

/** Record on dismiss: until "Got it" is pressed, the next launch asks again. */
function dismissWhatsNew(version) {
  wnVersion = null;
  if (version) updStore.set(WN.seen, version);
  closeModal($("whatsNewModal"));
}

async function maybeShowWhatsNew() {
  let data;
  try { data = await api("/whats-new"); } catch (_) { return; }
  const seen = updStore.get(WN.seen, "");
  if (seen === data.version) return;
  // never seen a card: the current release introduces itself; afterwards it
  // is strictly the entries newer than what this device last ran
  const pick = seen ? whatsNewFor(seen, data.entries)
                    : (data.entries || []).slice(0, 1);
  if (!pick.length) { updStore.set(WN.seen, data.version); return; }
  showWhatsNew(pick, data.version);
}

async function openWhatsNew() {
  let data;
  try { data = await api("/whats-new"); }
  catch (_) { toast("could not fetch what's new", "bad"); return; }
  const pick = (data.entries || []).filter((e) => e && e.version === data.version);
  if (!pick.length) { toast("nothing new to show"); return; }
  showWhatsNew(pick, data.version);
}

function wireWhatsNewRow() {
  const b = $("wnOpen");
  if (b) b.onclick = openWhatsNew;
}

/* ---------- window controls (desktop app) / host controls (android app) ---------- */
function wireQuitButton() {
  const quit = $("quitBtn");
  quit.classList.remove("hidden");
  quit.onclick = async () => {
    const ok = await askConfirm(
      "Quit suravidl? Active downloads will be interrupted.", { okText: "Quit" });
    if (!ok) return;
    if (window.AndroidHost) {
      window.AndroidHost.quit();          // stops the service + kills the process
    } else {
      try { await api("/app/quit", { method: "POST" }); } catch (_) {}
    }
  };
}

/* ---------- host-aware download location ---------- */
const ANDROID = () => !!window.AndroidHost;

/** Does this host give finished downloads a Gallery/Music copy?
 *
 *  The host answers, because only it knows: below Android 10 (API 29) there is
 *  no scoped storage, the app's own folder is already browsable, and the import
 *  is skipped — so promising "Gallery → suravidl" there sends the user looking
 *  for something that was never written. */
function GALLERY() {
  if (!ANDROID()) return false;
  try { return !!window.AndroidHost.galleryExport(); } catch (_) { return false; }
}

/** Android's app folder lives under Android/data/, which no file manager will
 *  open on Android 11+ — so say where the user can actually find their files
 *  (the gallery/music copies the app adds), and keep the raw path one tap away. */
function renderWhere(dir) {
  const d = dir || "";
  $("dlDir").textContent = d;
  if (ANDROID()) {
    const gallery = GALLERY();
    $("dlWhere").textContent = gallery
      ? "saved where you can open it — Gallery → suravidl (audio: Music → suravidl)"
      : "saved in the app's folder — use Open or Share on a finished download";
    $("dlDir").title = gallery
      ? "the app's own folder (not browsable): " + d
      : "the app's folder (reachable by file managers on this Android): " + d;
  } else {
    $("dlWhere").textContent = "downloads";
  }
}

function wireCopyPath() {
  const b = $("copyDir");
  if (!b) return;
  b.onclick = async () => {
    const ok = await copyText($("dlDir").textContent || "");
    toast(ok ? "path copied" : "copy failed", ok ? "ok" : "bad");
  };
}

async function initAppControls() {
  if (window.AndroidHost) {
    // inside the Android app: quit + battery settings, no minimize
    // (re-applied here too: the bridge may only appear after first paint)
    document.documentElement.dataset.host = "android";
    wireQuitButton();
    $("androidSection").classList.remove("hidden");
    $("tabDevice").classList.remove("hidden");
    $("batteryBtn").onclick = () => window.AndroidHost.openBatterySettings();
    $("quitAppBtn").onclick = () => $("quitBtn").onclick();
    // browser cookie DBs aren't readable on Android — offer file import instead
    $("browserRow").classList.add("hidden");
    $("impersonateRow").classList.add("hidden");   // no curl_cffi on the phone
    // the phone's two routes, said in its own terms: the app browser's session,
    // or a cookies.txt exported from a desktop browser (the encrypted import)
    const authHintEl = $("authHint");
    if (authHintEl) {
      authHintEl.textContent = "Two routes: sign in to the site in \u201cFind a video on a page\u201d — " +
        "that session goes with the download — or import a " +
        "cookies.txt exported from a desktop browser (encrypted on this device). " +
        "Instagram sessions expire in hours — re-import when a download asks for a sign-in.";
    }
    const imp = $("importCookies");
    imp.classList.remove("hidden");
    imp.onclick = () => window.AndroidHost.pickCookiesFile();
    // a page yt-dlp has no extractor for still has a player: this opens our own
    // browser with a sniffer attached (Android has no extensions — the browser
    // *is* the extension). Hidden on any host that cannot do it.
    if (window.AndroidHost.openBrowser) {
      $("sniffRow").classList.remove("hidden");
      $("sniffBtn").onclick = () => {
        try { window.AndroidHost.openBrowser(($("url").value || "").trim()); } catch (_) { }
      };
    }
    initVaultSection();
    initStorageSection();
    return;
  }
  try {
    const info = await api("/app/info");
    APP_INFO = info;
    if (!info.desktop) return;
    DESKTOP = true;
    if (info.can_minimize) {
      const min = $("minBtn");
      min.classList.remove("hidden");
      min.onclick = () => api("/app/minimize", { method: "POST" })
        .catch((e) => toast("could not minimize: " + e.message, "bad"));
    }
    if (info.can_pick_file) {
      const browse = $("browseCookies");
      browse.classList.remove("hidden");
      browse.onclick = async () => {
        try {
          const { path } = await api("/app/pick-file", { method: "POST" });
          if (path) {
            $("setCookies").value = path;
            toast("selected — press Save");
          }
        } catch (e) {
          toast("file picker unavailable: " + e.message, "bad");
        }
      };
    }
    wireQuitButton();
  } catch (_) { /* browser mode */ }
}

/** Android: the "cookies on this device" row (encrypted vault status + wipe). */
function initVaultSection() {
  const sec = $("vaultSection");
  if (!sec || !window.AndroidHost || !window.AndroidHost.cookiesStatus) return;
  sec.classList.remove("hidden");
  const show = () => {
    try { $("vaultStatus").textContent = window.AndroidHost.cookiesStatus(); }
    catch (_) { $("vaultStatus").textContent = "status unavailable"; }
  };
  show();
  $("deleteCookiesBtn").onclick = () => {
    try { window.AndroidHost.deleteCookies(); } catch (_) { }
    $("setCookies").value = "";
    api("/settings", { method: "POST", body: JSON.stringify({ cookies_file: "" }) })
      .catch(() => { });
    toast("stored cookies deleted");
    show();
  };
}

/** Android: storage row in Settings → Device — how much is downloaded, and a
 *  way to delete it, because the folder (Android/data/…) is unreachable. */
let refreshStorageInfo = null;   // set below; re-read on tab open and deletes

async function initStorageSection() {
  const sec = $("storageSection");
  if (!sec) return;
  sec.classList.remove("hidden");
  const show = async () => {
    try {
      const s = await api("/files/summary");
      $("storageInfo").textContent = s.files
        ? `${s.files} file${s.files === 1 ? "" : "s"} · ${humanBytes(s.bytes)}`
        : "no downloaded files";
      // the app cache (yt-dlp's player/signature data): counted apart from
      // the downloads, with its own button since v0.29.0
      const cache = typeof s.cache_bytes === "number" ? s.cache_bytes : 0;
      $("storageCache").textContent = cache
        ? `app cache · ${humanBytes(cache)}`
        : "app cache · empty";
    } catch (_) {
      $("storageInfo").textContent = "size unavailable";
      $("storageCache").textContent = "";
    }
  };
  await show();
  refreshStorageInfo = show;
  // Two deletes, one flow (the 2026-09-26 ask): the app's own folder can be
  // emptied while the Gallery/Music copy — the one the user can actually
  // open — stays. That copy is removed by a separate host call, so the
  // app-copies path simply never makes it. Since v0.29.0 these only touch
  // files: the cache has its own button below.
  const clearFiles = async (keepGallery) => {
    const s = await api("/files/summary").catch(() => null);
    const known = s && typeof s.files === "number";
    // Nothing to delete: do not offer it. The row above could have read
    // "2 files · 73.2 MB" a minute ago (it is only re-read on tab open)
    // while a delete elsewhere emptied the folder — and "Delete 0 files
    // (0 B)?" against a row that says 2 is the consistency bug this fixes.
    if (known && s.files === 0) {
      toast("nothing to delete");
      show();
      return;
    }
    const one = known && s.files === 1;
    const counted = known
      ? `Delete ${s.files} file${one ? "" : "s"} (${humanBytes(s.bytes)})`
      : "Delete every downloaded file";
    let msg;
    if (keepGallery) {
      msg = counted + " from the app's folder? The Gallery/Music copies stay.";
    } else if (known) {
      msg = counted +
        (GALLERY() ? ` and ${one ? "its" : "their"} Gallery/Music cop${one ? "y" : "ies"}` : "") +
        "? This cannot be undone.";
    } else {
      msg = counted + "? (its size could not be read) This cannot be undone.";
    }
    const ok = await askConfirm(msg, { okText: "Delete" });
    if (!ok) return;
    try {
      const r = await api("/files/clear", { method: "POST", body: JSON.stringify({ confirm: "delete" }) });
      if (!keepGallery && ANDROID() && window.AndroidHost.deleteMediaCopies) {
        try { window.AndroidHost.deleteMediaCopies(); } catch (_) { }
      }
      const parts = [];
      if (r.deleted > 0) {
        parts.push(`deleted ${r.deleted} file${r.deleted === 1 ? "" : "s"}`,
                   `freed ${humanBytes(r.freed_bytes)}`);
      }
      if (keepGallery && GALLERY()) parts.push("Gallery/Music copies kept");
      toast(parts.length ? parts.join(" · ") : "nothing freed");
      refreshJobs();
      show();
    } catch (e) {
      toast("could not delete: " + e.message, "bad");
    }
  };
  $("clearDownloadsBtn").onclick = () => clearFiles(false);
  $("clearAppCopiesBtn").onclick = () => clearFiles(true);
  // The distinction — and therefore this button — exists only where the host
  // actually writes gallery copies (Android 10+; the browser build has none).
  if (GALLERY()) $("clearAppCopiesBtn").classList.remove("hidden");
  // v0.29.0: the cache frees through its own endpoint, and it never touches
  // a download — the file deletes above no longer touch the cache either.
  $("clearCacheBtn").onclick = async () => {
    const s = await api("/files/summary").catch(() => null);
    const cacheBytes = s && typeof s.cache_bytes === "number" ? s.cache_bytes : 0;
    if (s && cacheBytes === 0) {
      toast("the app cache is already empty");
      show();
      return;
    }
    const what = s && cacheBytes ? ` (${humanBytes(cacheBytes)})` : "";
    const ok = await askConfirm(
      `Clear the app cache${what}? Player data yt-dlp simply fetches again — ` +
      "nothing downloaded is touched.", { okText: "Clear" });
    if (!ok) return;
    try {
      const r = await api("/cache/clear", { method: "POST", body: JSON.stringify({ confirm: "delete" }) });
      toast(r.freed_bytes > 0 ? `cache cleared (${humanBytes(r.freed_bytes)})`
                              : "cache was already empty");
      show();
    } catch (e) {
      toast("could not clear the cache: " + e.message, "bad");
    }
  };
}

/* called back by the Android host after the cookies file is imported */
window.onCookiesPicked = (path) => {
  if (!path) {
    toast("cookies import failed", "bad");
    return;
  }
  $("setCookies").value = path;
  saveSettings().then(() => toast("cookies imported")).catch((e) =>
    toast("could not save: " + e.message, "bad"));
};

/* ---------- settings ---------- */
// a tab switch reloads Settings from the server (showTab); that must not wipe
// what the user typed but has not saved yet (v0.21.1 audit)
let SETTINGS_DIRTY = false;

/** A dot on the Settings tab while the form holds edits the engine has not
 *  been told about. The tab is a primary destination: someone who changes the
 *  template and walks away had no way to know the next download would still
 *  use the OLD values (motion review). */
function markSettingsDirty(on) {
  SETTINGS_DIRTY = on;
  const tab = document.querySelector('#tabs .tab[data-tab="settings"]');
  if (tab) tab.classList.toggle("has-dirty", on);
}

async function loadSettings() {
  try {
    const s = await api("/settings");
    SETTINGS_SNAPSHOT = s;
    CURRENT = { theme: s.theme, glass: s.glass };
    $("setDir").value = s.download_dir || "";
    $("setConc").value = s.max_concurrent;
    $("setReveal").checked = !!s.open_dir_on_complete;
    $("setResume").checked = !!s.auto_resume;
    $("setCookies").value = s.cookies_file || "";
    $("setCookiesBrowser").value = s.cookies_from_browser || "";
    $("setImpersonate").value = s.impersonate || "";
    $("setTemplate").value = s.filename_template || "";
    $("setSubfolders").value = s.subfolders || "off";
    $("setContainer").value = s.video_container || "auto";
    $("setLiveFromStart").checked = !!s.live_from_start;
    $("setSubSrt").checked = !!s.subtitles_to_srt;
    $("setEmbMeta").checked = !!s.embed_metadata;
    $("setEmbThumb").checked = !!s.embed_thumbnail;
    $("setSubMode").value = s.subtitles_mode || "off";
    $("setSubLangs").value = s.subtitles_langs || "";
    $("setSubAuto").checked = !!s.subtitles_auto;
    $("setSbMode").value = s.sponsorblock_mode || "off";
    $("setSbCats").value = s.sponsorblock_categories || "";
    $("setArchive").checked = !!s.archive;
    $("setFragments").value = s.fragments != null ? s.fragments : 1;
    $("setRetries").value = s.retries != null ? s.retries : 10;
    $("setMaxDownloads").value = s.max_downloads != null ? s.max_downloads : 0;
    $("setRateLimit").value = s.rate_limit || "";
    $("setProxy").value = s.proxy || "";
    $("setRawEnabled").checked = !!s.raw_args_enabled;
    $("setRawArgs").value = s.raw_args || "";
    renderRawAccess(!!s.raw_args_enabled);
    // curated groups (yt-dlp tab)
    $("setVerbose").checked = !!s.verbose;
    $("setIpVersion").value = s.ip_version || "auto";
    $("setNoCheckCerts").checked = !!s.no_check_certificates;
    $("setSleepRequests").value = Number(s.sleep_requests || 0);
    $("setGeoBypass").checked = !!s.geo_bypass;
    $("setGeoCountry").value = s.geo_bypass_country || "";
    $("setExtractorArgs").value = s.extractor_args || "";
    renderWhere(s.download_dir);
    renderDefaultPreset();
    markSwatches(CURRENT);
    markSettingsDirty(false);   // the form now mirrors the server
  } catch (e) {
    toast("could not load settings: " + e.message, "bad");
  }
}

/* ---------- settings sub-tabs ---------- */
function showSettingsTab(name) {
  const incoming = $("spanel-" + name);
  const cur = document.querySelector("#settingsTabs .stab.active");
  const wasOn = !!cur && cur.dataset.stab === name;
  document.querySelectorAll("#settingsTabs .stab").forEach((b) => {
    const on = b.dataset.stab === name;
    b.classList.toggle("active", on);
    b.setAttribute("aria-selected", on ? "true" : "false");
    // the row scrolls on phones: keep the active sub-tab in view
    if (on && b.scrollIntoView) {
      try { b.scrollIntoView({ inline: "center", block: "nearest" }); }
      catch (_) { /* older WebView */ }
    }
  });
  document.querySelectorAll(".spanel").forEach((p) =>
    p.classList.toggle("hidden", p.id !== "spanel-" + name));
  // v0.37.1: the swap dresses itself — the sub-tabs were the only navigation
  // in the app with no transition at all (2026-09-30); a re-tap doesn't re-run
  if (incoming && !wasOn) {
    incoming.classList.remove("spanel-in");
    void incoming.offsetWidth;   // restart the fade on a rapid re-switch
    incoming.classList.add("spanel-in");
  }
}
document.querySelectorAll("#settingsTabs .stab").forEach((b) => {
  b.onclick = () => showSettingsTab(b.dataset.stab);
});

/* ---------- the shell: four tabs, hash-routed ---------- */
const TABS = ("download queue settings ytdlp").split(" ");

function showTab(name, opts) {
  const target = TABS.includes(name) ? name : "download";
  const current = document.body.dataset.tab;
  // the active tab on the body, so CSS can react to it (the mobile toast lane
  // needs to clear the Settings tab's pinned Save bar — theme review)
  document.body.dataset.tab = target;
  const panels = TABS.map((t) => $("panel-" + t)).filter(Boolean);
  const incoming = $("panel-" + target);
  // v0.37.1: the swap is immediate. It used to wait out the old screen's exit
  // fade and then wash the new one in over .4s — on a phone the next tab only
  // STARTED arriving after the previous one had finished leaving (2026-09-30
  // report). The arrival fade dresses the switch; it never delays it. Never on
  // first paint, and never when the target is already visible: the per-tab
  // refreshes at the end of this function call back into here and must not
  // restart the fade.
  const switching = !!(incoming && current && current !== target &&
    !panels.filter((p) => !p.classList.contains("hidden")).includes(incoming));
  panels.forEach((p) => p.classList.toggle("hidden", p !== incoming));
  if (switching) {
    incoming.classList.remove("tab-in");
    void incoming.offsetWidth;   // restart the fade on a rapid re-switch
    incoming.classList.add("tab-in");
  }
  TABS.forEach((t) => {
    document.querySelectorAll(`#tabs .tab[data-tab="${t}"]`).forEach((b) => {
      b.classList.toggle("active", t === target);
      b.setAttribute("aria-selected", t === target ? "true" : "false");
    });
  });
  if (location.hash.slice(1) !== target) {
    history.replaceState(null, "", "#" + target);
  }
  if (target === "settings" && !SETTINGS_DIRTY) loadSettings();
  // the storage row counts what is on disk — downloads land and deletes happen
  // while other tabs are up, so re-read it whenever Settings comes into view
  if (target === "settings" && refreshStorageInfo) refreshStorageInfo();
  if (target === "ytdlp") loadOptions(false);
  if (target === "queue") refreshJobs();
  if (!(opts && opts.keepScroll)) scrollTo({ top: 0, behavior: "instant" });
  syncToastLane();
}

document.querySelectorAll("#tabs .tab").forEach((b) => {
  b.onclick = () => showTab(b.dataset.tab);
});

/* ---------- yt-dlp tab: curated groups + option browser ---------- */
let OPTIONS = null;

async function loadOptions(force) {
  if (OPTIONS && !force) { renderOptions($("optionsSearch").value); return; }
  $("optionsList").textContent = "loading…";
  try {
    const r = await api("/options");
    OPTIONS = r.options || [];
    $("optionsCount").textContent = `${r.count} options`;
  } catch (e) {
    $("optionsList").textContent = "could not load options: " + e.message;
    return;
  }
  renderOptions($("optionsSearch").value);
}

async function openOptionsBrowser() {
  showTab("ytdlp");
  await loadOptions(false);
  $("optionsSearch").focus();
}

function renderOptions(query) {
  const q = (query || "").trim().toLowerCase();
  const list = (OPTIONS || []).filter((o) =>
    !q || o.name.toLowerCase().includes(q) || o.group.toLowerCase().includes(q) ||
    o.help.toLowerCase().includes(q));
  const box = $("optionsList");
  box.innerHTML = "";
  for (const o of list.slice(0, 400)) {
    const row = el("div", "optrow");
    const left = el("div");
    left.append(el("div", "flag", o.takes_value ? `${o.name} ${o.metavar || "VALUE"}` : o.name));
    left.append(el("div", "ogrp", o.group));
    row.append(left, el("div", "ohelp", o.help || ""));
    const add = () => {
      const ta = $("setRawArgs");
      ta.value = (ta.value.trim() + " " +
        (o.takes_value ? `${o.name} ${o.metavar || "VALUE"}` : o.name)).trim();
      $("setRawEnabled").checked = true;
      renderRawAccess(true);
      toast(`added ${o.name} — save to keep it`);
    };
    row.onclick = add;
    makeOptionRowReachable(row, add);
    box.append(row);
  }
  if (!list.length) box.append(el("div", "muted small", "nothing matches that search"));
  $("optionsCount").textContent = q
    ? `${list.length} match${list.length === 1 ? "" : "es"}`
    : `${(OPTIONS || []).length} options`;
}

/** Raw arguments only matter once enabled in Settings → Advanced. */
function renderRawAccess(enabled) {
  $("rawEditor").classList.toggle("hidden", !enabled);
  $("rawOffHint").classList.toggle("hidden", !!enabled);
  $("ovRawRow").classList.toggle("hidden", !enabled);
}

/* --- presets: named bundles the user saves and reuses --------------------- */

let PRESETS = [];          // [{name, patch, builtin, description}]

let PRESETS_ERROR = null;   // set when /presets could not be read: a server
                            // failure must not look like "you have no presets"
async function loadPresets() {
  try {
    const data = await api("/presets");
    PRESETS = data.presets || [];
    OV.defaults = data.defaults || {};
    OV.perJobKeys = data.per_job_keys || [];
    OV.qualities = data.qualities || [];
    PRESETS_ERROR = null;
  } catch (e) {
    PRESETS = [];
    PRESETS_ERROR = (e && e.message) || "no answer";
  }
  renderOvPresets();
  renderPresetList();
  renderOvPresetInfo();
  renderOvPresetActions();
}

/** The default-preset select (Settings → Presets): the permanent answer to
 *  "I always want this". It rides every NEW download; anything the download
 *  itself says — its own preset, a quality pick, per-download fields — still
 *  wins, the engine layers it that way (v0.36.0). */
function renderDefaultPreset() {
  const sel = $("defaultPreset");
  if (!sel) return;
  const stored = (SETTINGS_SNAPSHOT && SETTINGS_SNAPSHOT.default_preset) || "";
  const keep = sel.value || stored;
  sel.innerHTML = "";
  const none = el("option", "", "none — use my settings");
  none.value = "";
  sel.append(none);
  const groups = [[true, "built-in"], [false, "saved"]];
  for (const [builtin, label] of groups) {
    const items = (PRESETS || []).filter((p) => !!p.builtin === builtin);
    if (!items.length) continue;
    const group = document.createElement("optgroup");
    group.label = label;
    for (const p of items) {
      const o = el("option", "", p.name +
        (p.description ? " — " + p.description : ""));
      o.value = p.name;
      group.append(o);
    }
    sel.append(group);
  }
  if (keep && !Array.from(sel.options).some((o) => o.value === keep)) {
    // the setting outlived its preset (deleted later) — say so instead of
    // silently falling back to none
    const gone = el("option", "", "“" + keep + "” (no longer exists)");
    gone.value = keep;
    sel.append(gone);
  }
  sel.value = keep;
  sel.onchange = async () => {
    const name = sel.value;
    try {
      const s = await api("/settings", {
        method: "POST", body: JSON.stringify({ default_preset: name }) });
      if (SETTINGS_SNAPSHOT) SETTINGS_SNAPSHOT.default_preset = s.default_preset;
      toast(name
        ? `default preset: “${name}” rides every new download`
        : "default preset cleared — downloads use just your settings");
    } catch (e) {
      toast("could not save: " + e.message, "bad");
      sel.value = stored;       // the control goes back to what is stored
    }
  };
}

function renderPresetList() {
  renderDefaultPreset();        // the select keeps step with the list — save,
                                // delete and load all land here (v0.36.0)
  const box = $("presetList");
  if (!box) return;
  box.innerHTML = "";
  if (!PRESETS.length) {
    if (PRESETS_ERROR) {
      box.append(el("div", "empty",
        "could not load presets (" + PRESETS_ERROR + ") — "));
      const again = el("button", "btn sm ghost-sm", "retry");
      again.onclick = () => loadPresets();
      box.append(again);
      box.append(el("div", "muted",
        "your saved presets are not gone, they just could not be read"));
    } else {
      box.append(el("div", "empty", "No presets yet — save one from your settings above, or from the download panel."));
    }
    return;
  }
  for (const p of PRESETS) {
    const row = el("div", "optrow");
    const left = el("div", "col");
    left.append(el("span", "optname", p.name + (p.builtin ? " (built-in)" : "")));
    const keys = Object.keys(p.patch || {});
    left.append(el("span", "optsum small muted",
      (p.description || keys.map((k) => `${k}=${p.patch[k]}`).join(" · ")).slice(0, 140)));
    row.append(left);
    if (!p.builtin) {
      const del = el("button", "ghost-sm del", "Delete");
      del.prepend(ico("trash"));
      del.onclick = async () => {
        if (!(await askConfirm(`Delete the preset “${p.name}”? Downloads already
started keep their options.`, { okText: "Delete" }))) return;
        try {
          await api(`/presets/${encodeURIComponent(p.name)}`, { method: "DELETE" });
          toast("preset deleted");
          loadPresets();
        } catch (e) {
          toast("could not delete: " + e.message, "bad");
        }
      };
      row.append(del);
    }
    box.append(row);
  }
}

/** The patch "save my current settings" should store: what differs from the
 *  defaults, limited to the keys a single download may override. */
function presetPatchFromSettings() {
  const patch = {};
  const keys = OV.perJobKeys || [];
  const defaults = OV.defaults || {};
  for (const k of keys) {
    const v = SETTINGS_SNAPSHOT ? SETTINGS_SNAPSHOT[k] : undefined;
    if (v === undefined || v === null) continue;
    const d = defaults[k];
    const isDefault = Array.isArray(v) || typeof v === "object"
      ? JSON.stringify(v) === JSON.stringify(d)
      : v === d;
    if (!isDefault && v !== "") patch[k] = v;
  }
  return patch;
}

async function saveCurrentAsPreset() {
  const name = $("presetName").value.trim();
  const msg = $("presetMsg");
  const patch = presetPatchFromSettings();
  if (!Object.keys(patch).length) {
    msg.textContent = OV.perJobKeys ? ("Nothing to save yet — change a download option first " +
      "(Settings → Media / Network).")
      : "presets could not be loaded, so there is nothing to diff against — " +
        "retry from Settings → Presets.";
    msg.className = OV.perJobKeys ? "msg warn" : "msg bad";
    return;
  }
  try {
    await api("/presets", { method: "POST", body: JSON.stringify({ name, patch }) });
    msg.textContent = `saved “${name}” with ${Object.keys(patch).length} option(s): ` +
      Object.keys(patch).join(", ");
    msg.className = "msg ok";
    $("presetName").value = "";
    loadPresets();
  } catch (e) {
    msg.textContent = "could not save: " + e.message;
    msg.className = "msg bad";
  }
}

$("optionsBtn").onclick = openOptionsBrowser;
$("optionsSearch").oninput = (e) => renderOptions(e.target.value);

/** Escape is the keyboard way out of Settings (the tab bar is the visible one). */
function closeSettings() {
  showTab("download");
}

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("confirmModal").classList.contains("hidden")) {
    return;   // the confirm dialog handles its own Escape
  }
  // the what's-new card: a real dialog, so Escape is its way out (v0.38.3)
  if (wnVersion) { dismissWhatsNew(wnVersion); return; }
  // only when Settings is really open: this used to close it from any tab and
  // yank the user back to Download (v0.21.1 audit)
  const panel = $("panel-settings");
  if (panel && !panel.classList.contains("hidden")) closeSettings();
});

// the hash is a real address (reload lands on the same tab); when something
// else changes it — a link, a host gesture — follow it instead of disagreeing
window.addEventListener("hashchange", () => {
  const name = location.hash.slice(1);
  if (TABS.includes(name)) showTab(name);
});

document.querySelectorAll("#themeSwatches .swatch").forEach((b) => {
  b.onclick = () => setAppearance({ theme: b.dataset.theme },
    "Theme: " + b.querySelector(".sw-label").textContent);
});
document.querySelectorAll("#glassSwatches .swatch").forEach((b) => {
  b.onclick = () => setAppearance({ glass: b.dataset.glass },
    "Glass: " + b.querySelector(".sw-label").textContent);
});
document.querySelectorAll("#schemeSwatches .swatch").forEach((b) => {
  b.onclick = () => setAppearance({ accent: b.dataset.accent },
    "Scheme: " + b.querySelector(".sw-label").textContent);
});

function saveSettings() {
  return api("/settings", {
    method: "POST",
    body: JSON.stringify({
      download_dir: $("setDir").value.trim(),
      max_concurrent: Number($("setConc").value),
      open_dir_on_complete: $("setReveal").checked,
      auto_resume: $("setResume").checked,
      cookies_file: $("setCookies").value.trim(),
      cookies_from_browser: $("setCookiesBrowser").value,
      impersonate: $("setImpersonate").value,
      filename_template: $("setTemplate").value.trim(),
      subfolders: $("setSubfolders").value,
      video_container: $("setContainer").value,
      live_from_start: $("setLiveFromStart").checked,
      embed_metadata: $("setEmbMeta").checked,
      embed_thumbnail: $("setEmbThumb").checked,
      subtitles_mode: $("setSubMode").value,
      subtitles_langs: $("setSubLangs").value.trim(),
      subtitles_auto: $("setSubAuto").checked,
      subtitles_to_srt: $("setSubSrt").checked,
      sponsorblock_mode: $("setSbMode").value,
      sponsorblock_categories: $("setSbCats").value.trim(),
      archive: $("setArchive").checked,
      fragments: Number($("setFragments").value),
      retries: Number($("setRetries").value),
      max_downloads: Number($("setMaxDownloads").value),
      rate_limit: $("setRateLimit").value.trim(),
      proxy: $("setProxy").value.trim(),
      raw_args_enabled: $("setRawEnabled").checked,
      raw_args: $("setRawArgs").value.trim(),
      // curated groups (yt-dlp tab)
      verbose: $("setVerbose").checked,
      ip_version: $("setIpVersion").value,
      no_check_certificates: $("setNoCheckCerts").checked,
      sleep_requests: Number($("setSleepRequests").value || 0),
      geo_bypass: $("setGeoBypass").checked,
      geo_bypass_country: $("setGeoCountry").value.trim().toUpperCase(),
      extractor_args: $("setExtractorArgs").value.trim(),
    }),
  }).then((s) => {
    SETTINGS_SNAPSHOT = s;   // the preset diff reads this
    markSettingsDirty(false);  // the form was accepted as-is
    renderWhere(s.download_dir);
    $("setConc").value = s.max_concurrent;
    renderRawAccess(!!s.raw_args_enabled);
    return s;
  });
}

async function saveAndToast(msgEl) {
  msgEl.textContent = "saving…";
  try {
    await saveSettings();
    msgEl.textContent = "";
    $("setMsg").textContent = "";
    $("ytdlpMsg").textContent = "";
    toast("Settings saved");
  } catch (e) {
    msgEl.textContent = "save failed: " + e.message;
  }
}

$("setSave").onclick = () => saveAndToast($("setMsg"));
$("ytdlpSave").onclick = () => saveAndToast($("ytdlpMsg"));
$("setRawEnabled").onchange = (e) => renderRawAccess(e.target.checked);

// anything the user edits in Settings marks the form dirty, so a tab switch
// does not silently reload it from the server (v0.21.1 audit)
{
  const panel = $("panel-settings");
  if (panel) {
    for (const ev of ["input", "change"]) {
      panel.addEventListener(ev, () => { markSettingsDirty(true); });
    }
  }
}

/* ---------- test cookies: the button that answers "did it work?" ---------- */
async function testCookies() {
  const msg = $("cookiesMsg");
  const btn = $("testCookies");
  btn.disabled = true;
  msg.textContent = "testing…";
  msg.classList.remove("good", "bad");
  try {
    // save first: the test must check what is on screen, not what was saved
    await saveSettings();
    // the URL box is the natural subject when the user just pasted something
    const url = ($("url").value || "").trim();
    const r = await api("/auth/check", {
      method: "POST",
      body: JSON.stringify({ url: url || null }),
    });
    msg.textContent = r.message;
    msg.classList.toggle("good", !!r.ok);
    msg.classList.toggle("bad", !r.ok);
    if (r.detail) msg.title = r.detail;
    if (r.cookies) {
      msg.textContent += ` (${r.cookies.domains.join(", ") || "no domains"})`;
    }
  } catch (e) {
    msg.textContent = "test failed: " + e.message;
    msg.classList.add("bad");
  } finally {
    btn.disabled = false;
  }
}
$("testCookies").onclick = testCookies;

/* ---------- share target (Android): a link from another app --------------- */
/** MainActivity hands a shared link here once the UI is on screen: prefill the
 *  box and probe it. The format stays the user's choice, exactly like a paste. */
window.suravidlShared = (url) => {
  if (!url || typeof url !== "string") return;
  showTab("download");
  $("url").value = url.trim();
  doProbe();
  toast("shared link ready — pick a format");
};

/* the bay's door: summary clicks are intercepted (preventDefault) so
   <details> never snaps its content in or out; the .bay-body wrapper
   transitions max-height + opacity instead and the [open] attribute flips
   only when the door finishes moving. prefers-reduced-motion clamps the
   transition to .001s, so nothing waits there either. Programmatic opens
   (Studio, the armed strip) skip the door on purpose — they are
   "bring me there" actions. */
function wireBayDoor(d) {
  const body = d.querySelector(".bay-body");
  if (!body) return;
  const seal = () => { body.style.maxHeight = ""; body.style.opacity = ""; d.open = false; };
  d.querySelector("summary").addEventListener("click", (e) => {
    e.preventDefault();                            // <details> must not snap
    if (!d.open) {                                 // open: flip first, then play
      d.open = true;
      body.style.maxHeight = "0px";
      void body.offsetHeight;
      body.style.maxHeight = body.scrollHeight + "px";
      body.style.opacity = "1";
      body.addEventListener("transitionend", function h(ev) {
        if (ev.propertyName !== "max-height") return;
        body.removeEventListener("transitionend", h);
        if (d.open) body.style.maxHeight = "none";
      });
      return;
    }
    let done = false;                              // close: play the door, then flip
    const sealOnce = () => { if (!done) { done = true; seal(); } };
    body.style.maxHeight = body.scrollHeight + "px";
    void body.offsetHeight;
    body.style.maxHeight = "0px";
    body.style.opacity = "0";
    body.addEventListener("transitionend", function h(ev) {
      if (ev.propertyName !== "max-height") return;
      body.removeEventListener("transitionend", h);
      sealOnce();
    });
    setTimeout(sealOnce, 500);                     // a door that can never jam
  });
}
wireBayDoor($("ovBlock"));

/* ---------- boot ---------- */
$("probeBtn").onclick = doProbe;
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") doProbe(); });
// the transport: picks arm a take; the START lamp commits it (v0.37.0)
$("bestBtn").onclick = () => commitTake($("bestBtn"));
$("studioBtn").onclick = () => {
  $("ovBlock").open = true;
  $("ovBlock").scrollIntoView({ block: "start" });
};
$("probeDetails").setAttribute("aria-expanded", "false");
$("probeDetails").setAttribute("aria-controls", "probeMsg");
$("probeDetails").onclick = () => {
  const hidden = $("probeMsg").classList.toggle("hidden");
  $("probeDetails").textContent = hidden ? "Show details" : "Hide details";
  $("probeDetails").setAttribute("aria-expanded", hidden ? "false" : "true");
};
$("audioNativeBtn").dataset.pick = "audio-native";
$("audioM4aBtn").dataset.pick = "audio-m4a";
$("audioMp3Btn").dataset.pick = "audio-mp3";
$("audioNativeBtn").onclick = () => armTake("audio-native", "keep original", $("audioNativeBtn"));
$("audioM4aBtn").onclick = () => armTake("audio-m4a", "m4a", $("audioM4aBtn"));
$("audioMp3Btn").onclick = () => armTake("audio-mp3", "mp3", $("audioMp3Btn"));
// the formats people kept asking for (review #9) — a picker beats raw args
$("audioMore").onchange = () => {
  const preset = $("audioMore").value;
  $("audioMore").value = "";
  if (!preset) return;
  armTake(preset, preset.replace(/^audio-/, ""), $("audioMore"));
};
renderTake();
$("playlistBtn").onclick = () => startJob($("url").value.trim(), null, null, true, $("playlistBtn"));
$("plAll").onclick = () => pickAll(true);
$("plNone").onclick = () => pickAll(false);
$("playlistItems").addEventListener("input", checkboxFromRange);   // typing reacts at once
$("playlistItems").addEventListener("change", checkboxFromRange);

/** Keep the field being typed into above the sticky save bar. Tapping an
 *  input on a phone raises the keyboard, which shrinks the visual viewport —
 *  the field ended up underneath the pinned footer exactly when the user was
 *  looking at it (motion review). Only scrolls when the field is actually
 *  obscured, so desktop focus never moves the page. */
document.addEventListener("focusin", (e) => {
  const t = e.target;
  if (!t || !/^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName || "")) return;
  const r = t.getBoundingClientRect();
  const pad = 90;   // the sticky header and footer own this much of each edge
  if (r.top >= pad && r.bottom <= window.innerHeight - pad) return;   // visible
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  t.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
});

initOptionListKeyboard();

applyTheme(CURRENT.theme, CURRENT.glass, CURRENT.accent);
if (ANDROID()) document.documentElement.dataset.host = "android";
renderWhere(CFG.downloadDir);
wireCopyPath();
initOverrides();
$("presetSave").onclick = saveCurrentAsPreset;

/* The token the extension needs. It is already in this page's source — the
   engine inlines it so the UI can call its own API — so showing a masked copy
   costs nothing and saves a trip to ~/.suravidl/token, which the phone cannot
   make at all. Masked, because screenshots happen. */
function wireToken() {
  const el = $("apiToken");
  if (!el) return;
  const t = (CFG && CFG.token) || "";
  el.textContent = t ? t.slice(0, 6) + "…" + t.slice(-4) : "not set";
  const btn = $("copyToken");
  if (btn) {
    btn.onclick = () => {
      const done = (ok) => {
        btn.textContent = ok ? "Copied" : "Select it above";
        setTimeout(() => (btn.textContent = "Copy"), 1800);
      };
      if (navigator.clipboard) {
        navigator.clipboard.writeText(t).then(() => done(true), () => done(false));
      } else {
        done(false);
      }
    };
  }
  el.title = "send it as: Authorization: Bearer <token>";
}

wireToken();
loadVersions();
loadPresets();
wireUpdateRow();
wireWhatsNewRow();
checkAppUpdate();
maybeShowWhatsNew();
loadSettings();
initAppControls();
initPlayer();
initFolderSheet();
initBatch();
initArchive();
/* Start on Download — a quit and reopen is a fresh start, not a return to
   wherever the device was left (v0.38.1 report). The URL stays a real
   address: a hash that names a tab (#settings in a bookmark or a link)
   still opens it. */
(function bootTab() {
  const want = location.hash.slice(1);
  showTab(TABS.includes(want) ? want : "download", { keepScroll: true });
})();
refreshJobs();
setInterval(refreshJobs, 1200);

/** Play a finished download without leaving the page (the v0.22 review's #10:
 *  "check what you downloaded, before you hunt for the file"). A media element
 *  cannot send an Authorization header, so the stream route also takes the
 *  page's own token in the query string. */
function openPlayer(job, file) {
  // one entry of a playlist row plays by basename; everything else plays the
  // job's own filepath (2026-09-27: playlist rows had no Play at all)
  const stream = `/jobs/${encodeURIComponent(job.id)}/stream?`;
  if (file) {
    const name = String(file).split("/").pop();
    openPlayerSrc(job.title || "download",
      stream + "name=" + encodeURIComponent(name) +
      "&token=" + encodeURIComponent(CFG.token), extOf(name));
    return;
  }
  openPlayerSrc(job.title || "download",
    stream + "token=" + encodeURIComponent(CFG.token), extOf(job.filepath));
}

/** The file's extension, lowercased ("e1.MP4" → "mp4"). */
function extOf(p) {
  return (String(p || "").split(".").pop() || "").toLowerCase();
}

/** The player modal, driven by whatever URL carries the media. */
function openPlayerSrc(title, src, ext) {
  const isVideo = ["mp4", "m4v", "webm", "mkv", "mov"].includes(ext);
  const isText = ["srt", "vtt"].includes(ext);
  $("playTitle").textContent = title || "download";
  const body = $("playBody");
  body.replaceChildren();
  let node;
  if (isVideo) {
    node = document.createElement("video");
    node.controls = true;
    node.autoplay = true;
    node.className = "player-video";
    node.playsInline = true;
    node.src = src;
  } else if (isText) {
    node = document.createElement("pre");
    node.className = "player-text";
    fetch(src).then((r) => r.text()).then((t) => { node.textContent = t; })
      .catch(() => { node.textContent = "could not load the subtitles"; });
  } else {
    node = document.createElement("audio");
    node.controls = true;
    node.autoplay = true;
    node.className = "player-audio";
    node.src = src;
  }
  body.append(node);
  $("playModal").classList.remove("hidden");
}

function closePlayer() {
  // the same exit every other dialog uses, then release the media element so a
  // hidden player cannot keep playing; closing used to hard-cut (motion review)
  closeModal($("playModal"));
  setTimeout(() => $("playBody").replaceChildren(), 180);
}

function initPlayer() {
  $("playClose").onclick = closePlayer;
  $("playModal").onclick = (e) => {
    if (e.target === $("playModal")) closePlayer();
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("playModal").classList.contains("hidden")) {
      closePlayer();
    }
  });
}

/* ---------- the folder sheet ("open folder") ---------- */
/** Desktop shells reveal the folder itself in the OS file manager; on
 *  Android no file manager may open Android/data, so the folder is shown
 *  inside the app instead — every file with Play, and Open / Share through
 *  the host bridge (2026-09-27 report: "Add the open folder button too,
 *  below copy path"). */
async function openFolderSheet() {
  const list = $("folderList");
  list.replaceChildren(el("div", "muted", "loading…"));
  openModal($("folderModal"));
  try {
    const r = await api("/files/list");
    $("folderTitle").textContent = "downloads · " + r.files.length +
      (r.files.length === 1 ? " file" : " files");
    list.replaceChildren();
    if (!r.files.length) {
      list.append(el("div", "muted", "the folder is empty"));
      return;
    }
    for (const f of r.files) list.append(folderItem(f));
  } catch (e) {
    list.replaceChildren(
      el("div", "muted", "could not read the folder: " + e.message));
  }
}

/** One file line of the folder sheet. */
function folderItem(f) {
  const item = el("div", "jitem");
  const name = el("span", "jname", f.name);
  name.title = f.path;
  item.append(name, el("span", "fsize", humanBytes(f.bytes)));
  if (f.kind === "video" || f.kind === "audio") {
    const play = el("button", "ghost-sm", "Play");
    play.onclick = () => openPlayerSrc(f.name,
      "/files/stream?path=" + encodeURIComponent(f.name) +
      "&token=" + encodeURIComponent(CFG.token), extOf(f.name));
    item.append(play);
  }
  if (ANDROID() && window.AndroidHost) {
    const open = el("button", "ghost-sm", "Open");
    open.onclick = () => {
      try { window.AndroidHost.openFile(f.path); }
      catch (e) { toast("could not open: " + e.message, "bad"); }
    };
    const share = el("button", "ghost-sm", "Share");
    share.onclick = () => {
      try { window.AndroidHost.shareFile(f.path); }
      catch (e) { toast("could not share: " + e.message, "bad"); }
    };
    item.append(open, share);
  }
  return item;
}

function initFolderSheet() {
  const modal = $("folderModal");
  if (!modal) return;
  $("folderClose").onclick = () => closeModal(modal);
  modal.onclick = (e) => { if (e.target === modal) closeModal(modal); };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      closeModal(modal);
    }
  });
  $("openDir").onclick = async () => {
    if (DESKTOP) {
      try {
        await api("/app/reveal-dir", { method: "POST" });
        return;
      } catch (_) { /* no file manager on this shell — show the sheet */ }
    }
    openFolderSheet();
  };
  $("noSound").addEventListener("change", refreshSoundLabels);
}

/** Several links in the box at once: offer to queue them all (review #5).
 *  Pasting into a single-line input collapses the newlines to spaces, so a
 *  multi-line paste arrives as space-separated URLs — split on whitespace.
 *
 *  A link counts with a scheme, or as the bare host shape the engine already
 *  accepts ("youtu.be/x"): the UI used to demand a scheme, so pasting a bare
 *  link produced no batch at all while the engine would have taken it (UI
 *  review). */
const BARE_HOST = /^[a-z0-9-]+(\.[a-z0-9-]+)+(:\d+)?(\/\S*)?$/i;

function pastedUrls() {
  const text = $("url").value.trim();
  if (!text) return [];
  return text.split(/\s+/).filter((s) =>
    /^(https?|ftp|magnet):/i.test(s) || BARE_HOST.test(s));
}

function renderBatchRow() {
  const urls = pastedUrls();
  const many = urls.length > 1;
  const over = urls.length > 20;          // the engine's own batch ceiling
  $("batchRow").classList.toggle("hidden", !many);
  $("batchCount").textContent = !many ? ""
    : over ? `${urls.length} links pasted — only 20 fit in one batch`
    : `${urls.length} links pasted — queue them all?`;
  $("batchBtn").disabled = over;
}

function initBatch() {
  $("url").addEventListener("input", renderBatchRow);
  $("url").addEventListener("change", renderBatchRow);
  $("batchBtn").onclick = async () => {
    const urls = pastedUrls();
    if (urls.length < 2) return;
    const body = { urls };
    if (OV.preset) body.preset = OV.preset;
    const overrides = readOv();
    if (overrides) body.overrides = overrides;
    $("batchBtn").classList.add("busy");
    try {
      const r = await api("/jobs/batch",
        { method: "POST", body: JSON.stringify(body) });
      $("url").value = "";
      renderBatchRow();
      clearOv();
      const n = (r.jobs || []).length;
      const skipped = r.skipped || [];
      if (skipped.length) {
        toast(`${n} queued · ${skipped.length} skipped: ` + skipped[0].error,
          "bad");
      } else {
        toast(`${n} links queued`, "info");
      }
      refreshJobs();
    } catch (e) {
      toast("could not queue those links: " + e.message, "bad");
    } finally {
      $("batchBtn").classList.remove("busy");
    }
  };
}

/** The download archive used to be a black box (review #7): show what is in
 *  it, and let the user forget an entry so that video can be fetched again. */
async function loadArchive() {
  try {
    const a = await api("/archive");
    const n = a.count || 0;
    $("archiveCount").textContent = n
      ? `· ${n} entr${n === 1 ? "y" : "ies"}` : "· empty";
    const list = $("archiveList");
    list.replaceChildren();
    list.classList.remove("hidden");
    if (!n) {
      list.append(el("div", "muted small", "nothing archived yet"));
      return;
    }
    const entries = (a.entries || []).slice(-50).reverse();
    if (a.entries && entries.length < n) {
      list.append(el("div", "muted small",
        `showing the last ${entries.length} of ${n}`));
    }
    for (const line of entries) {
      const row = el("div", "jrow");
      row.append(el("span", "small mono", line));
      const forget = el("button", "ghost-sm", "forget");
      forget.onclick = async () => {
        try {
          await api("/archive/forget",
            { method: "POST", body: JSON.stringify({ entry: line }) });
          toast("forgotten — that video can be downloaded again", "info");
          loadArchive();
        } catch (e) {
          toast("could not forget: " + e.message, "bad");
        }
      };
      row.append(forget);
      list.append(row);
    }
  } catch (e) {
    toast("could not read the archive: " + e.message, "bad");
  }
}

function initArchive() {
  $("archiveShow").onclick = () => {
    const list = $("archiveList");
    if (!list.classList.contains("hidden") && list.childElementCount) {
      list.classList.add("hidden");
      return;
    }
    loadArchive();
  };
  $("archiveForget").onclick = async () => {
    const entry = $("archiveEntry").value.trim();
    if (!entry) { toast("paste an archive entry first", "bad"); return; }
    try {
      const r = await api("/archive/forget",
        { method: "POST", body: JSON.stringify({ entry }) });
      toast(`forgotten ${r.removed} entr${r.removed === 1 ? "y" : "ies"}`,
        "info");
      $("archiveEntry").value = "";
      loadArchive();
    } catch (e) {
      toast("could not forget: " + e.message, "bad");
    }
  };
}

/** Put a failed job's URL and options back into the Download tab so the next
 *  attempt can be different — a site that refused one format often takes
 *  another, and re-running the identical request is a loop (review #11). */
function editAndRetry(j) {
  $("url").value = j.url || "";
  clearOv();
  if (j.preset) { OV.preset = j.preset; $("ovPreset").value = j.preset; }
  const ov = j.overrides || {};
  if (ov.subtitles_mode) $("ovSubs").value = ov.subtitles_mode;
  if (ov.subtitles_langs) $("ovSubLangs").value = ov.subtitles_langs;
  if (ov.sponsorblock_mode) $("ovSb").value = ov.sponsorblock_mode;
  $("ovMeta").value = ov.embed_metadata === true ? "on"
    : ov.embed_metadata === false ? "off" : "";
  $("ovThumb").value = ov.embed_thumbnail === true ? "on"
    : ov.embed_thumbnail === false ? "off" : "";
  if (ov.raw_args) $("ovRaw").value = ov.raw_args;
  if (ov.video_container) $("ovContainer").value = ov.video_container;
  if (ov.archive_ignore) $("ovArchive").value = "ignore";
  if (ov.download_sections) {
    const [start, end] = String(ov.download_sections)
      .replace(/^\*/, "").split("-");
    $("ovClipStart").value = (start || "").trim();
    $("ovClipEnd").value = (end || "").trim();
  }
  renderOvCount();
  showTab("download");
  toast("loaded the failed settings — change what you like, then start it", "info");
}

addEventListener("scroll", () => {
  document.body.classList.toggle("scrolled", scrollY > 4);
}, { passive: true });
