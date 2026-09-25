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
  } finally {
    $("probeBtn").classList.remove("busy");
  }
}

function fmtQuality(f) {
  if (f.height) return f.height + "p" + (f.fps && f.fps > 30 ? f.fps : "");
  if (f.abr) return f.abr + " kbps";
  return f.format_note || f.resolution || "";
}

function renderProbe(url, info) {
  $("probeCard").classList.remove("hidden");
  $("probeTitle").textContent = info.title || url;
  const dur = info.duration
    ? " · " + Math.round(info.duration / 60) + " min" : "";
  $("probeMeta").textContent = (info.extractor || "") + dur;

  const tb = $("formats").querySelector("tbody");
  tb.innerHTML = "";

  if (info.playlist) {
    $("playlistRow").classList.remove("hidden");
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
  const fmts = [...(info.formats || [])]
    .filter((f) => f.ext && f.format_id)
    .sort((a, b) => (b.height || b.abr || 0) - (a.height || a.abr || 0));

  for (const [i, f] of fmts.entries()) {
    const tr = el("tr", "enter");
    tr.style.animationDelay = Math.min(i * 30, 240) + "ms";
    tr.append(
      el("td", "fmt-q", fmtQuality(f) || "—"),
      el("td", "fmt-c",
        [f.ext, f.vcodec !== "none" ? f.vcodec : null, f.acodec !== "none" ? f.acodec : null]
          .filter(Boolean).join(" · ") || "—"),
      el("td", "fmt-s", humanBytes(f.filesize || f.filesize_approx)),
    );
    const td = el("td");
    const btn = el("button", "get", "Get");
    btn.onclick = () => startJob(url, f.format_id);
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
function playlistMode() {
  return !$("playlistRow").classList.contains("hidden");
}

async function startJob(url, fmt, preset, playlist) {
  try {
    const body = { url, fmt, preset };
    if (playlist) body.playlist_items = $("playlistItems").value.trim();
    await api("/jobs", { method: "POST", body: JSON.stringify(body) });
    toast(playlist ? "Playlist added to downloads" : "Added to downloads", "info");
    refreshJobs();
  } catch (e) {
    toast("could not start download: " + e.message, "bad");
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

function jobRow(j) {
  const row = el("div", "job");
  const top = el("div", "jobtop");
  const title = el("span", "jobtitle", j.title || j.url);
  title.title = j.url;
  top.append(title, el("span", "pill " + j.status, j.status));
  row.append(top);

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
    const box = $("jobs");
    const list = jobs.sort(
      (a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    if (!list.length) {
      if (!box.querySelector(".empty")) {
        box.innerHTML = "";
        box.append(el("div", "empty", "Nothing yet — paste a link above and hit Probe."));
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
    $("setRateLimit").value = s.rate_limit || "";
    $("setProxy").value = s.proxy || "";
    $("setRawEnabled").checked = !!s.raw_args_enabled;
    $("setRawArgs").value = s.raw_args || "";
    renderWhere(s.download_dir);
    markSwatches(CURRENT);
  } catch (e) {
    toast("could not load settings: " + e.message, "bad");
  }
}

/* ---------- settings sub-tabs ---------- */
function showSettingsTab(name) {
  document.querySelectorAll("#settingsTabs .stab").forEach((b) =>
    b.classList.toggle("active", b.dataset.stab === name));
  document.querySelectorAll(".spanel").forEach((p) =>
    p.classList.toggle("hidden", p.id !== "spanel-" + name));
}
document.querySelectorAll("#settingsTabs .stab").forEach((b) => {
  b.onclick = () => showSettingsTab(b.dataset.stab);
});

/* ---------- yt-dlp option browser (Advanced) ---------- */
let OPTIONS = null;

async function openOptionsBrowser() {
  openModal($("optionsModal"));
  $("optionsSearch").value = "";
  if (!OPTIONS) {
    $("optionsList").textContent = "loading…";
    try {
      const r = await api("/options");
      OPTIONS = r.options || [];
      $("optionsCount").textContent = `${r.count} options`;
    } catch (e) {
      $("optionsList").textContent = "could not load options: " + e.message;
      return;
    }
  }
  renderOptions("");
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
      toast(`added ${o.name}`);
      closeOptionsBrowser();
    };
    box.append(row);
  }
  if (!list.length) box.append(el("div", "muted small", "nothing matches that search"));
  $("optionsCount").textContent = q ? `${list.length} match` : `${(OPTIONS || []).length} options`;
}

function closeOptionsBrowser() {
  closeModal($("optionsModal"));
}

$("optionsBtn").onclick = openOptionsBrowser;
$("optionsClose").onclick = closeOptionsBrowser;
$("optionsModal").onclick = (e) => {
  if (e.target === $("optionsModal")) closeOptionsBrowser();
};
$("optionsSearch").oninput = (e) => renderOptions(e.target.value);

function openSettings() {
  openModal($("settingsModal"));
  showSettingsTab("general");
  loadSettings();
}
function closeSettings() {
  closeModal($("settingsModal"));
}

$("settingsBtn").onclick = openSettings;
$("setClose").onclick = closeSettings;
$("settingsModal").onclick = (e) => {
  if (e.target === $("settingsModal")) closeSettings();
};
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("optionsModal").classList.contains("hidden")) {
    closeOptionsBrowser();
    return;
  }
  if (e.key === "Escape" && !$("settingsModal").classList.contains("hidden")) {
    closeSettings();
  }
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
      rate_limit: $("setRateLimit").value.trim(),
      proxy: $("setProxy").value.trim(),
      raw_args_enabled: $("setRawEnabled").checked,
      raw_args: $("setRawArgs").value.trim(),
    }),
  }).then((s) => {
    renderWhere(s.download_dir);
    $("setConc").value = s.max_concurrent;
    return s;
  });
}

$("setSave").onclick = async () => {
  $("setMsg").textContent = "saving…";
  try {
    await saveSettings();
    $("setMsg").textContent = "";
    toast("Settings saved");
  } catch (e) {
    $("setMsg").textContent = "save failed: " + e.message;
  }
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
renderWhere(CFG.downloadDir);
wireCopyPath();
loadVersions();
checkAppUpdate();
loadSettings();
initAppControls();
refreshJobs();
setInterval(refreshJobs, 1200);
addEventListener("scroll", () => {
  document.body.classList.toggle("scrolled", scrollY > 4);
}, { passive: true });
