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
async function doProbe() {
  const url = $("url").value.trim();
  if (!url) return;
  $("probeMsg").textContent = "probing…";
  $("probeBtn").classList.add("busy");
  try {
    const info = await api("/probe", {
      method: "POST", body: JSON.stringify({ url }),
    });
    renderProbe(url, info);
    $("probeMsg").textContent = "";
  } catch (e) {
    let msg = "probe failed: " + e.message;
    if (/sign in|age|not a bot|private video|members-only|cookies/i.test(e.message)) {
      msg += " — this video needs your account: add cookies in ⚙ Settings → Authentication.";
    }
    $("probeMsg").textContent = msg;
    $("probeCard").classList.add("hidden");
    $("dlEmpty").classList.remove("hidden");
  } finally {
    $("probeBtn").classList.remove("busy");
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

function renderProbe(url, info) {
  $("probeCard").classList.remove("hidden");
  $("dlEmpty").classList.add("hidden");
  $("probeTitle").textContent = info.title || url;
  const dur = info.duration
    ? " · " + Math.round(info.duration / 60) + " min" : "";
  $("probeMeta").textContent = (info.extractor || "") + dur;

  const tb = $("formats").querySelector("tbody");
  tb.innerHTML = "";

  if (info.playlist) {
    $("playlistRow").classList.remove("hidden");
    $("qualityRow").classList.add("hidden");
    $("probeMeta").textContent =
      (info.count ? info.count + " videos" : "playlist") +
      (info.extractor ? " · " + info.extractor : "");
    const entries = info.entries || [];
    for (const [i, e] of entries.entries()) {
      const tr = el("tr", "enter");
      tr.style.animationDelay = Math.min(i * 30, 240) + "ms";
      tr.append(
        el("td", "fmt-q", String(i + 1)),
        el("td", "fmt-c", e.title || e.url || "—"),
        el("td", "fmt-s", e.duration ? Math.round(e.duration / 60) + " min" : "—"),
      );
      tb.append(tr);
    }
    if (info.count && entries.length < info.count) {
      const tr = el("tr");
      tr.append(el("td", "", ""), el("td", "muted", `… ${info.count - entries.length} more`), el("td"));
      tb.append(tr);
    }
    return;
  }

  $("playlistRow").classList.add("hidden");
  renderQualityRow(url);
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
function renderQualityRow(url) {
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
    const btn = el("button", "btn sm" + (q.key === "best" ? " prime" : ""), q.label);
    btn.title = "download the best stream up to " + q.label + " (" + q.fmt + ")";
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

async function startJob(url, fmt, preset, playlist) {
  try {
    const body = { url };
    if (fmt) body.fmt = fmt;
    // the audio intent only applies when no explicit format was picked
    // (yt-dlp refuses fmt + preset together)
    const audio = fmt ? null : (preset || OV.preset);
    if (audio) body.preset = audio;
    if (playlist) body.playlist_items = $("playlistItems").value.trim();
    const overrides = readOv();
    if (overrides) body.overrides = overrides;
    await api("/jobs", { method: "POST", body: JSON.stringify(body) });
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

/** The block's values as a patch — only what the user actually set. */
function readOv() {
  const patch = { ...(OV.patch || {}) };
  const subs = $("ovSubs").value;
  if (subs) {
    patch.subtitles_mode = subs;
    const langs = $("ovSubLangs").value.trim();
    delete patch.subtitles_langs;          // no field, no claim
    if (langs) patch.subtitles_langs = langs;
  }
  const sb = $("ovSb").value;
  if (sb) patch.sponsorblock_mode = sb;
  if ($("ovMeta").checked) patch.embed_metadata = true;
  if ($("ovThumb").checked) patch.embed_thumbnail = true;
  const raw = $("ovRaw").value.trim();
  if (raw) patch.raw_args = raw;
  return Object.keys(patch).length ? patch : null;
}

function clearOv() {
  OV.preset = null;
  OV.patch = {};
  $("ovSubs").value = "";
  $("ovSubLangs").value = "";
  $("ovSb").value = "";
  $("ovMeta").checked = false;
  $("ovThumb").checked = false;
  $("ovRaw").value = "";
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
  if (patch.embed_metadata) $("ovMeta").checked = true;
  if (patch.embed_thumbnail) $("ovThumb").checked = true;
  if (patch.raw_args) $("ovRaw").value = patch.raw_args;
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
  for (const id of ["ovSubs", "ovSubLangs", "ovSb", "ovMeta", "ovThumb", "ovRaw"]) {
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
      + (j.filepath && ANDROID() ? " Its Gallery/Music copy goes too." : "")
      + " This cannot be undone.";
    if (!(await askConfirm(msg, { okText: running ? "Stop and delete" : "Delete" }))) {
      return;
    }
    try {
      const r = await settleThenDelete(j);
      if (j.filepath && ANDROID() && window.AndroidHost.deleteMediaNamed) {
        try { window.AndroidHost.deleteMediaNamed(j.filepath.split("/").pop()); }
        catch (_) { /* the row is gone either way */ }
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
    if (ANDROID()) {
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
    trashHost = r;
    row.append(r);
    if (j.note) row.append(el("div", "jobhint", j.note));
  }

  if (j.raw_args) {
    row.append(el("div", "jobhint", "yt-dlp args: " + j.raw_args));
  }

  const actions = el("div", "jrow");
  if (ACTIVE.has(j.status)) {
    const c = el("button", "ghost-sm", "Cancel");
    c.onclick = () => api(`/jobs/${j.id}/cancel`, { method: "POST" })
      .then(refreshJobs).catch((e) => toast("cancel failed: " + e.message, "bad"));
    actions.append(c);
  } else if (j.status === "cancelled") {
    const r = el("button", "ghost-sm", "Retry");
    r.onclick = () => api(`/jobs/${j.id}/retry`, { method: "POST" })
      .then(refreshJobs).catch((e) => toast("retry failed: " + e.message, "bad"));
    actions.append(r);
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

async function refreshJobs() {
  try {
    const { jobs } = await api("/jobs");
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
  } catch (_) { /* engine briefly unavailable */ }
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

/** Android's app folder lives under Android/data/, which no file manager will
 *  open — so say where the user can actually find their files (the gallery /
 *  music copies the app adds), and keep the raw path one tap away. */
function renderWhere(dir) {
  const d = dir || "";
  $("dlDir").textContent = d;
  if (ANDROID()) {
    $("dlWhere").textContent =
      "saved where you can open it — Gallery → suravidl (audio: Music → suravidl)";
    $("dlDir").title = "the app's own folder (not browsable): " + d;
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
      min.onclick = () => api("/app/minimize", { method: "POST" });
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
    const s = await api("/files/summary").catch(() => ({ files: 0, bytes: 0 }));
    const one = s.files === 1;
    const ok = await askConfirm(
      `Delete ${s.files} file${one ? "" : "s"} (${humanBytes(s.bytes)})` +
      (ANDROID() ? ` and ${one ? "its" : "their"} Gallery/Music cop${one ? "y" : "ies"}` : "") +
      "? This cannot be undone.", { okText: "Delete" });
    if (!ok) return;
    try {
      const r = await api("/files/clear", { method: "POST" });
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
  if (target === "settings") loadSettings();
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

async function loadPresets() {
  try {
    const data = await api("/presets");
    PRESETS = data.presets || [];
    OV.defaults = data.defaults || {};
    OV.perJobKeys = data.per_job_keys || [];
    OV.qualities = data.qualities || [];
  } catch (e) {
    PRESETS = [];
  }
  renderOvPresets();
  renderPresetList();
}

function renderPresetList() {
  const box = $("presetList");
  if (!box) return;
  box.innerHTML = "";
  if (!PRESETS.length) {
    box.append(el("div", "empty", "No presets yet — save one from your settings above."));
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
    msg.textContent = "Nothing to save yet — change a download option first " +
      "(Settings → Media / Network).";
    msg.className = "msg warn";
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
  if (e.key === "Escape" && !$("confirmModal").classList.contains("hidden")) {
    return;   // the confirm dialog handles its own Escape
  }
  if (e.key === "Escape") closeSettings();
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
      embed_metadata: $("setEmbMeta").checked,
      embed_thumbnail: $("setEmbThumb").checked,
      subtitles_mode: $("setSubMode").value,
      subtitles_langs: $("setSubLangs").value.trim(),
      subtitles_auto: $("setSubAuto").checked,
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
$("playlistBtn").onclick = () => startJob($("url").value.trim(), null, null, true);

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
addEventListener("scroll", () => {
  document.body.classList.toggle("scrolled", scrollY > 4);
}, { passive: true });
