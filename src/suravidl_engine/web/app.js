const CFG = window.__SURAVIDL__ || {};
const H = () => ({
  "Authorization": "Bearer " + CFG.token,
  "Content-Type": "application/json",
});

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: H() });
  if (!r.ok) {
    let msg = `${r.status}`;
    try {
      const body = await r.json();
      msg = body.detail ? String(body.detail) : JSON.stringify(body);
    } catch (_) {
      msg += " " + (await r.text().catch(() => ""));
    }
    throw new Error(msg);
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

/* ---------- toasts ---------- */
function toast(msg, kind = "ok") {
  const t = el("div", "toast " + kind);
  t.append(el("span", "dot"), el("span", "", msg));
  t.onclick = () => dismiss(t);
  $("toasts").append(t);
  setTimeout(() => dismiss(t), 4200);
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
function applyTheme(theme, glass) {
  const r = document.documentElement;
  if (theme) r.dataset.theme = theme;
  if (glass) r.dataset.glass = glass;
}
function markSwatches(values) {
  document.querySelectorAll("#themeSwatches .swatch").forEach((b) =>
    b.classList.toggle("on", b.dataset.theme === values.theme));
  document.querySelectorAll("#glassSwatches .swatch").forEach((b) =>
    b.classList.toggle("on", b.dataset.glass === values.glass));
}
let CURRENT = { theme: CFG.theme || "dark", glass: CFG.glass || "frosted" };
let SETTINGS_SNAPSHOT = null;   // last /settings payload (used by the preset diff)

async function setAppearance(patch, label) {
  try {
    const s = await api("/settings", { method: "POST", body: JSON.stringify(patch) });
    CURRENT = { theme: s.theme, glass: s.glass };
    applyTheme(s.theme, s.glass);
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
  $("probeMsg").textContent = "probing…";
  $("probeBtn").classList.add("busy");
  try {
    const info = await api("/probe", {
      method: "POST", body: JSON.stringify({ url }),
    });
    if (seq !== PROBE_SEQ) return;
    renderProbe(url, info);
    $("probeMsg").textContent = "";
  } catch (e) {
    if (seq !== PROBE_SEQ) return;
    // the engine explains a failure (it owns the "sign-in wall" judgement and
    // says so in its own words) — the UI does not second-guess it
    $("probeMsg").textContent = "probe failed: " + e.message;
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

/** What the stream contains — the thing the old table made you guess. */
function fmtKind(f) {
  const v = hasVideo(f), a = hasAudio(f);
  if (v && a) return { label: "video + audio", cls: "k-both" };
  if (v) return { label: "video only — sound is added on download", cls: "k-video" };
  if (a) return { label: "audio only", cls: "k-audio" };
  // a plain file (direct link): the site told us nothing about its tracks
  return { label: "single file", cls: "k-audio" };
}

/** Picking a video-only stream must not produce a silent file: pair it with
 *  the site's separate audio track when one exists (yt-dlp merges both with
 *  ffmpeg). Direct-link files have no separate audio, so they stay as-is. */
function fmtSpec(f, hasSeparateAudio) {
  return hasSeparateAudio && hasVideo(f) && !hasAudio(f)
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
    td.title = "the site does not advertise a size for this stream — " +
               "the real size shows once the download starts";
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

/** The subtitle languages the site actually offers — click to add one to the
 *  wish list (typing codes blind was the review's #4 complaint). */
function renderSubsChips(info) {
  const box = $("subsChips");
  box.replaceChildren();
  const manual = Object.keys(info.subtitles || {});
  const auto = Object.keys(info.automatic_captions || {});
  const langs = [...new Set([...manual, ...auto])].slice(0, 14);
  $("subsRow").classList.toggle("hidden", !langs.length);
  for (const lang of langs) {
    const isAuto = !manual.includes(lang);
    const chip = el("button", "chip", lang + (isAuto ? " (auto)" : ""));
    chip.type = "button";
    chip.title = "download subtitles in " + lang +
      (isAuto ? " (auto-generated — pick the site pair for real captions)" : "");
    chip.onclick = () => {
      const field = $("ovSubLangs");
      const have = field.value.split(",").map((s) => s.trim()).filter(Boolean);
      if (!have.includes(lang)) have.push(lang);
      field.value = have.join(", ");
      if (!$("ovSubs").value) $("ovSubs").value = "sidecar";
      if (typeof renderOvCount === "function") renderOvCount();
      toast(`subtitles: ${field.value}`);
    };
    box.append(chip);
  }
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
  const dur = info.duration
    ? " · " + Math.round(info.duration / 60) + " min" : "";
  $("probeMeta").textContent = (info.extractor || "") + dur;

  // the probe has always carried these three; the UI now shows them
  const live = info.is_live === true || info.live_status === "is_live";
  $("liveRow").classList.toggle("hidden", !live);
  renderSubsChips(info);
  renderChapterChips(info);

  const tb = $("formats").querySelector("tbody");
  tb.innerHTML = "";

  if (info.playlist) {
    $("playlistRow").classList.remove("hidden");
    $("qualityRow").classList.add("hidden");
    $("probeMeta").textContent =
      (info.count ? info.count + " videos" : "playlist") +
      (info.extractor ? " · " + info.extractor : "");
    const entries = info.entries || [];
    PLAYLIST = { count: info.count || entries.length, shown: entries.length };
    PLAYLIST_NONE = false;
    for (const [i, e] of entries.entries()) {
      const tr = el("tr", "enter");
      tr.style.animationDelay = Math.min(i * 30, 240) + "ms";
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
    tr.style.animationDelay = Math.min(i * 30, 240) + "ms";
    const kind = fmtKind(f);
    const cell = el("td", "fmt-c");
    cell.append(el("div", "", fmtCodecs(f) || "—"));
    cell.append(el("div", "fmt-kind " + kind.cls, kind.label));
    tr.append(
      el("td", "fmt-q", fmtQuality(f) || "—"),
      cell,
      sizeCell(f),
    );
    const td = el("td");
    const btn = el("button", "get", "Get");
    btn.onclick = () => startJob(url, fmtSpec(f, separateAudio));
    td.append(btn);
    tr.append(td);
    tb.append(tr);
  }
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
    // click is still yours (M20)
    const last = remembered && q.key === remembered;
    const btn = el("button",
      "btn sm" + (last ? " pick" : (q.key === "best" ? " prime" : "")),
      last ? q.label + " ✓" : q.label);
    btn.title = last
      ? "your pick for this site last time — click to download at " + q.label
      : "download the best stream up to " + q.label + " (" + q.fmt + ")";
    btn.onclick = () => startJob(url, q.fmt);
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

async function startJob(url, fmt, preset, playlist) {
  if (playlist && PLAYLIST_NONE && !playlistFieldText()) {
    toast("pick at least one item first", "bad");
    return;
  }
  try {
    const body = { url };
    if (fmt) body.fmt = fmt;
    // the audio intent only applies when no explicit format was picked
    // (yt-dlp refuses fmt + preset together)
    const audio = fmt ? null : (preset || OV.preset);
    if (audio) body.preset = audio;
    if (playlist) body.playlist_items = playlistFieldText();
    const overrides = readOv();
    if (overrides) body.overrides = overrides;
    await api("/jobs", { method: "POST", body: JSON.stringify(body) });
    // the block says "this download only" — so it is spent on this download
    // (v0.21.1 audit: it used to stick to every job for the rest of the session)
    clearOv();
    PLAYLIST_NONE = false;
    toast(playlist ? "Playlist added to downloads" : "Added to downloads", "info");
    refreshJobs();
  } catch (e) {
    toast("could not start download: " + e.message, "bad");
  }
}

/* --- "This download only": a patch over the saved settings ---------------- */

// the audio intent of an applied preset (fmt and preset are exclusive in yt-dlp)
// plus its full patch: the block only shows a few of the options a preset may
// carry, so the rest must ride along instead of being lost on apply
const OV = { preset: null, patch: {}, defaults: null, perJobKeys: null };

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
  renderOvCount();
}

/** The little "N options" chip on the collapsed summary. */
function renderOvCount() {
  const patch = readOv();
  const n = (patch ? Object.keys(patch).length : 0) + (OV.preset ? 1 : 0);
  const chip = $("ovCount");
  if (!n) {
    chip.classList.add("hidden");
    chip.textContent = "";
    return;
  }
  const parts = [];
  if (OV.preset) parts.push(OV.preset.replace("audio-", ""));
  if (patch) parts.push(Object.keys(patch).length + " option" +
    (Object.keys(patch).length === 1 ? "" : "s"));
  chip.textContent = parts.join(" · ");
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
  const n = Object.keys(readOv() || {}).length + (OV.preset ? 1 : 0);
  toast(`preset “${name}” applied — ${n} option(s) for the next download`);
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
  sel.value = keep;
}

function initOverrides() {
  $("ovApply").onclick = applyOvPreset;
  $("ovClear").onclick = () => { clearOv(); toast("cleared — using your settings"); };
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
  const pct = Math.round(progressPct(j));
  const spd = j.progress && j.progress.speed ? humanBytes(j.progress.speed) + "/s" : "";
  const eta = j.progress && j.progress.eta != null ? "ETA " + j.progress.eta + "s" : "";
  const pl = j.progress && j.progress.playlist_index && j.progress.playlist_count
    ? "video " + j.progress.playlist_index + "/" + j.progress.playlist_count : "";
  const size = `${humanBytes(j.progress && j.progress.downloaded_bytes)} / ${humanBytes(j.progress && j.progress.total_bytes)}`;
  return [...(pl ? [pl] : []), pct + "%", ...(spd ? [spd] : []), ...(eta ? [eta] : []), size];
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
  const b = el("button", "ghost-sm del", "🗑 Delete");
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
    } catch (e) {
      toast("could not delete: " + e.message, "bad");
    }
  };
  return b;
}

function jobRow(j) {
  const row = el("div", "job");
  const top = el("div", "jobtop");
  const title = el("span", "jobtitle", j.title || j.url);
  title.title = j.url;
  top.append(title, el("span", "pill " + j.status, j.status));
  // what this job actually carries (preset / per-download overrides)
  const extra = j.overrides ? Object.keys(j.overrides).length : 0;
  if (j.preset) {
    const chip = el("span", "chip tag", "⚙ " + j.preset.replace("audio-", ""));
    chip.title = "audio preset: " + j.preset;
    top.append(chip);
  }
  if (extra) {
    const chip = el("span", "chip tag",
      "⚙ " + extra + " option" + (extra === 1 ? "" : "s"));
    chip.title = Object.keys(j.overrides).join(", ") + " — this download only";
    top.append(chip);
  }
  row.append(top);

  let trashHost = null;   // the button row the trash belongs to

  if (ACTIVE.has(j.status)) {
    if (j.status === "downloading") {
      const bar = el("div", "bar");
      const fill = el("div", "fill active");
      fill.style.width = progressPct(j).toFixed(1) + "%";
      bar.append(fill);
      row.append(bar);
      const meta = el("div", "jmeta");
      meta.append(...metaParts(j).map((t) => el("span", "", t)));
      row.append(meta);
    }
  } else if (j.status === "error" || j.status === "interrupted") {
    const r = el("div", "jrow");
    r.append(el("span", "jerr", (j.error || "").slice(0, 160)));
    const retry = el("button", "ghost-sm", "Retry");
    retry.onclick = () => api(`/jobs/${j.id}/retry`, { method: "POST" })
      .then(refreshJobs).catch((e) => toast("retry failed: " + e.message, "bad"));
    r.append(retry);
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
    // Hand off a *file*. A playlist row's filepath is the download folder:
    // handing that to "open" (or share) does nothing useful, so the buttons
    // are for single-file rows only (v0.21.2 audit).
    const oneFile = !(j.files && j.files.length > 1);
    if (ANDROID() && oneFile && j.filepath) {
      // Android/data is off-limits to file managers, so hand the file itself
      // to another app (a provider grant) — play it or share it right here.
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
    if (j.status === "completed" && oneFile && j.filepath) {
      const play = el("button", "ghost-sm", "Play");
      play.onclick = () => openPlayer(j);
      r.append(play);
    }
    trashHost = r;
    row.append(r);
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
  } else if (j.status === "cancelled" || j.status === "error"
             || j.status === "interrupted") {
    const r = el("button", "ghost-sm", "Retry");
    r.onclick = () => api(`/jobs/${j.id}/retry`, { method: "POST" })
      .then(refreshJobs).catch((e) => toast("retry failed: " + e.message, "bad"));
    actions.append(r);
    if (j.status !== "cancelled") {
      // retrying the exact request that just failed is a loop; load its
      // settings into the form so the next try can differ (review #11)
      const edit = el("button", "ghost-sm", "Edit & retry");
      edit.title = "load this job's URL and options into the Download tab";
      edit.onclick = () => editAndRetry(j);
      actions.append(edit);
    }
  }
  // every row can be deleted (a running one is stopped first, after a confirm)
  if (!trashHost) trashHost = actions;
  trashHost.append(deleteButton(j));
  if (actions.children.length) row.append(actions);
  row.dataset.sig = jobSig(j);
  return row;
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
  if (fill) fill.style.width = progressPct(j).toFixed(1) + "%";
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
    const list = jobs.sort(
      (a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    if (!list.length) {
      if (!box.querySelector(".empty")) {
        box.innerHTML = "";
        box.append(el("div", "empty",
          "Nothing in the queue. Downloads you start land here — finished ones " +
          "stay put so you can open, share or delete them."));
      }
      return;
    }
    const empty = box.querySelector(".empty");
    if (empty) empty.remove();

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
      if (!keep.has(r.dataset.id)) r.remove();
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
  } catch (_) { $("versions").textContent = ""; }
}

async function checkAppUpdate() {
  try {
    const u = await api("/update-check");
    if (u.update_available && u.url) {
      // a button, not a link: embedded shells (pywebview, Android WebView)
      // cannot open target=_blank themselves
      const b = el("button", "updateLink", `⬆ suravidl ${u.latest} available`);
      b.onclick = () => openExternal(u.url);
      $("updateSlot").append(b);
    }
  } catch (_) { /* best-effort */ }
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
  } catch (e) {
    toast("update failed: " + e.message, "bad");
  }
  $("updateBtn").textContent = old;
  $("updateBtn").disabled = false;
};

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
  b.onclick = () => {
    const t = $("dlDir").textContent || "";
    const done = () => toast("path copied");
    if (navigator.clipboard) {
      navigator.clipboard.writeText(t).then(done).catch(() => toast("copy failed", "bad"));
    } else {
      toast("copy not supported here", "bad");
    }
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
    const imp = $("importCookies");
    imp.classList.remove("hidden");
    imp.onclick = () => window.AndroidHost.pickCookiesFile();
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
    } catch (_) {
      $("storageInfo").textContent = "size unavailable";
    }
  };
  await show();
  $("clearDownloadsBtn").onclick = async () => {
    const s = await api("/files/summary").catch(() => null);
    const known = s && typeof s.files === "number";
    const one = known && s.files === 1;
    const ok = await askConfirm(
      known ? (`Delete ${s.files} file${one ? "" : "s"} (${humanBytes(s.bytes)})` +
      (GALLERY() ? ` and ${one ? "its" : "their"} Gallery/Music cop${one ? "y" : "ies"}` : "") +
      "? This cannot be undone.")
        : "Delete every downloaded file? (its size could not be read) " +
          "This cannot be undone.",
      { okText: "Delete" });
    if (!ok) return;
    try {
      const r = await api("/files/clear", { method: "POST", body: JSON.stringify({ confirm: "delete" }) });
      if (ANDROID() && window.AndroidHost.deleteMediaCopies) {
        try { window.AndroidHost.deleteMediaCopies(); } catch (_) { }
      }
      toast(`deleted ${r.deleted} file${r.deleted === 1 ? "" : "s"} · ` +
            `freed ${humanBytes(r.freed_bytes)}`);
      refreshJobs();
      show();
    } catch (e) {
      toast("could not delete: " + e.message, "bad");
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
    markSwatches(CURRENT);
    SETTINGS_DIRTY = false;   // the form now mirrors the server
  } catch (e) {
    toast("could not load settings: " + e.message, "bad");
  }
}

/* ---------- settings sub-tabs ---------- */
function showSettingsTab(name) {
  document.querySelectorAll("#settingsTabs .stab").forEach((b) => {
    const on = b.dataset.stab === name;
    b.classList.toggle("active", on);
    // the row scrolls on phones: keep the active sub-tab in view
    if (on && b.scrollIntoView) {
      try { b.scrollIntoView({ inline: "center", block: "nearest" }); }
      catch (_) { /* older WebView */ }
    }
  });
  document.querySelectorAll(".spanel").forEach((p) =>
    p.classList.toggle("hidden", p.id !== "spanel-" + name));
}
document.querySelectorAll("#settingsTabs .stab").forEach((b) => {
  b.onclick = () => showSettingsTab(b.dataset.stab);
});

/* ---------- the shell: four tabs, hash-routed ---------- */
const TABS = ("download queue settings ytdlp").split(" ");
const TAB_KEY = "suravidl.tab";

function showTab(name, opts) {
  const target = TABS.includes(name) ? name : "download";
  TABS.forEach((t) => {
    const panel = $("panel-" + t);
    if (panel) panel.classList.toggle("hidden", t !== target);
    document.querySelectorAll(`#tabs .tab[data-tab="${t}"]`).forEach((b) => {
      b.classList.toggle("active", t === target);
      b.setAttribute("aria-selected", t === target ? "true" : "false");
    });
  });
  try { localStorage.setItem(TAB_KEY, target); } catch (_) { /* private mode */ }
  if (location.hash.slice(1) !== target) {
    history.replaceState(null, "", "#" + target);
  }
  if (target === "settings" && !SETTINGS_DIRTY) loadSettings();
  if (target === "ytdlp") loadOptions(false);
  if (target === "queue") refreshJobs();
  if (!(opts && opts.keepScroll)) scrollTo({ top: 0, behavior: "instant" });
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
    row.onclick = () => {
      const ta = $("setRawArgs");
      ta.value = (ta.value.trim() + " " +
        (o.takes_value ? `${o.name} ${o.metavar || "VALUE"}` : o.name)).trim();
      $("setRawEnabled").checked = true;
      renderRawAccess(true);
      toast(`added ${o.name} — save to keep it`);
    };
    box.append(row);
  }
  if (!list.length) box.append(el("div", "muted small", "nothing matches that search"));
  $("optionsCount").textContent = q ? `${list.length} match` : `${(OPTIONS || []).length} options`;
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
}

function renderPresetList() {
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
      box.append(el("div", "empty", "No presets yet — save one from your settings above."));
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
      const del = el("button", "ghost-sm del", "🗑 Delete");
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

function openSettings() {
  showTab("settings");
  showSettingsTab("general");
}
function closeSettings() {
  showTab("download");
}

$("settingsBtn").onclick = openSettings;
$("setClose").onclick = closeSettings;
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("confirmModal").classList.contains("hidden")) {
    return;   // the confirm dialog handles its own Escape
  }
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
    SETTINGS_DIRTY = false;  // the form was accepted as-is
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
      panel.addEventListener(ev, () => { SETTINGS_DIRTY = true; });
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

/* ---------- boot ---------- */
$("probeBtn").onclick = doProbe;
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") doProbe(); });
$("bestBtn").onclick = () => startJob($("url").value.trim(), null, null, playlistMode());
$("audioNativeBtn").onclick = () => startJob($("url").value.trim(), null, "audio-native", playlistMode());
$("audioM4aBtn").onclick = () => startJob($("url").value.trim(), null, "audio-m4a", playlistMode());
$("audioMp3Btn").onclick = () => startJob($("url").value.trim(), null, "audio-mp3", playlistMode());
// the formats people kept asking for (review #9) — a picker beats raw args
$("audioMore").onchange = () => {
  const preset = $("audioMore").value;
  $("audioMore").value = "";
  if (!preset) return;
  const url = $("url").value.trim();
  if (!url) { toast("paste a link first", "bad"); return; }
  startJob(url, null, preset, playlistMode());
};
$("playlistBtn").onclick = () => startJob($("url").value.trim(), null, null, true);
$("plAll").onclick = () => pickAll(true);
$("plNone").onclick = () => pickAll(false);
$("playlistItems").addEventListener("change", checkboxFromRange);

applyTheme(CURRENT.theme, CURRENT.glass);
if (ANDROID()) document.documentElement.dataset.host = "android";
renderWhere(CFG.downloadDir);
wireCopyPath();
initOverrides();
$("presetSave").onclick = saveCurrentAsPreset;
loadVersions();
loadPresets();
checkAppUpdate();
loadSettings();
initAppControls();
initPlayer();
initBatch();
initArchive();
/* start on the remembered tab, unless the URL names one */
(function bootTab() {
  let want = location.hash.slice(1);
  if (!TABS.includes(want)) {
    try { want = localStorage.getItem(TAB_KEY) || "download"; }
    catch (_) { want = "download"; }
  }
  showTab(want, { keepScroll: true });
})();
refreshJobs();
setInterval(refreshJobs, 1200);

/** Play a finished download without leaving the page (the v0.22 review's #10:
 *  "check what you downloaded, before you hunt for the file"). A media element
 *  cannot send an Authorization header, so the stream route also takes the
 *  page's own token in the query string. */
function openPlayer(job) {
  const ext = (String(job.filepath || "").split(".").pop() || "").toLowerCase();
  const isVideo = ["mp4", "m4v", "webm", "mkv", "mov"].includes(ext);
  const isText = ["srt", "vtt"].includes(ext);
  $("playTitle").textContent = job.title || "download";
  const body = $("playBody");
  body.replaceChildren();
  const src = `/jobs/${encodeURIComponent(job.id)}/stream?token=` +
    encodeURIComponent(CFG.token);
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
  $("playBody").replaceChildren();   // stops the audio of a hidden player
  $("playModal").classList.add("hidden");
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

/** Several links in the box at once: offer to queue them all (review #5).
 *  Pasting into a single-line input collapses the newlines to spaces, so a
 *  multi-line paste arrives as space-separated URLs — split on whitespace. */
function pastedUrls() {
  const text = $("url").value.trim();
  if (!text) return [];
  return text.split(/\s+/).filter((s) => /^(https?|ftp|magnet):/i.test(s));
}

function renderBatchRow() {
  const urls = pastedUrls();
  const many = urls.length > 1;
  $("batchRow").classList.toggle("hidden", !many);
  $("batchCount").textContent = many
    ? `${urls.length} links pasted — queue them all?` : "";
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
