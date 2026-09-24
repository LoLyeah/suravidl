const CFG = window.__SURAVIDL__;
const H = () => ({
  "Authorization": "Bearer " + CFG.token,
  "Content-Type": "application/json",
});

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: H() });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
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

/* ---------- probe ---------- */
async function doProbe() {
  const url = $("url").value.trim();
  if (!url) return;
  $("probeMsg").textContent = "probing…";
  try {
    const info = await api("/probe", {
      method: "POST", body: JSON.stringify({ url }),
    });
    renderProbe(url, info);
    $("probeMsg").textContent = "";
  } catch (e) {
    $("probeMsg").textContent = "probe failed: " + e.message;
    $("probeCard").classList.add("hidden");
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
  const fmts = [...(info.formats || [])]
    .filter((f) => f.ext && f.format_id)
    .sort((a, b) => (b.height || b.abr || 0) - (a.height || a.abr || 0));

  for (const f of fmts) {
    const tr = el("tr");
    tr.append(
      el("td", "", f.ext),
      el("td", "", fmtQuality(f) || "—"),
      el("td", "muted small",
        [f.vcodec !== "none" ? f.vcodec : null, f.acodec !== "none" ? f.acodec : null]
          .filter(Boolean).join(" + ") || "—"),
      el("td", "", humanBytes(f.filesize || f.filesize_approx)),
    );
    const td = el("td");
    const btn = el("button", "small", "Download");
    btn.onclick = () => startJob(url, f.format_id);
    td.append(btn);
    tr.append(td);
    tb.append(tr);
  }
  if (!fmts.length) tb.append(el("tr")).append(el("td", "muted", "no formats found"));
}

/* ---------- jobs ---------- */
async function startJob(url, fmt) {
  try {
    await api("/jobs", { method: "POST", body: JSON.stringify({ url, fmt }) });
    refreshJobs();
  } catch (e) { alert("could not start download: " + e.message); }
}

function jobRow(j) {
  const row = el("div", "job");
  const top = el("div", "jobtop");
  const title = el("span", "jobtitle", j.title || j.url);
  title.title = j.url;
  const status = el("span", "badge " + j.status, j.status);
  top.append(title, status);
  row.append(top);

  if (ACTIVE.has(j.status)) {
    const pct = j.progress && j.progress.total_bytes
      ? Math.min(100, (j.progress.downloaded_bytes / j.progress.total_bytes) * 100)
      : 0;
    const bar = el("div", "bar");
    const fill = el("div", "fill");
    fill.style.width = pct.toFixed(1) + "%";
    bar.append(fill);
    row.append(bar);
    const meta = el("div", "muted small");
    const spd = j.progress?.speed ? humanBytes(j.progress.speed) + "/s" : "";
    const eta = j.progress?.eta != null ? " · ETA " + j.progress.eta + "s" : "";
    meta.textContent = `${humanBytes(j.progress?.downloaded_bytes)} / ${humanBytes(j.progress?.total_bytes)} ${spd}${eta}`;
    row.append(meta);
  } else if (j.status === "error" || j.status === "interrupted") {
    row.append(el("div", "muted small err", (j.error || "").slice(0, 160)));
  } else if (j.filepath) {
    row.append(el("div", "muted small", j.filepath));
  }

  const actions = el("div", "actions");
  if (ACTIVE.has(j.status)) {
    const c = el("button", "small ghost", "Cancel");
    c.onclick = () => api(`/jobs/${j.id}/cancel`, { method: "POST" }).then(refreshJobs);
    actions.append(c);
  } else if (["error", "interrupted", "cancelled"].includes(j.status)) {
    const r = el("button", "small ghost", "Retry");
    r.onclick = () => api(`/jobs/${j.id}/retry`, { method: "POST" }).then(refreshJobs);
    actions.append(r);
  }
  row.append(actions);
  return row;
}

async function refreshJobs() {
  try {
    const { jobs } = await api("/jobs");
    const box = $("jobs");
    box.innerHTML = "";
    if (!jobs.length) { box.append(el("div", "muted small", "no jobs yet")); return; }
    jobs
      .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""))
      .forEach((j) => box.append(jobRow(j)));
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
      const a = document.createElement("a");
      a.href = u.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.className = "updateLink";
      a.textContent = `⬆ suravidl ${u.latest} available`;
      $("versions").after(a);
    }
  } catch (_) { /* update check is best-effort (private repos need a token) */ }
}

async function loadHealth() {
  try {
    const r = await fetch("/health");
    const h = await r.json();
    $("dlDir").textContent = h.download_dir || "";
  } catch (_) {}
}

$("updateBtn").onclick = async () => {
  if (!confirm("Run yt-dlp self-update? The engine may briefly stall new jobs."))
    return;
  $("updateBtn").disabled = true;
  $("updateBtn").textContent = "updating…";
  try {
    const r = await api("/update", { method: "POST" });
    $("updateBtn").textContent = r.updated ? `updated → ${r.after}` : "already latest";
  } catch (e) { $("updateBtn").textContent = "update failed"; }
  setTimeout(() => { $("updateBtn").textContent = "Update yt-dlp"; $("updateBtn").disabled = false; }, 4000);
};

$("probeBtn").onclick = doProbe;
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") doProbe(); });
$("bestBtn").onclick = () => startJob($("url").value.trim(), null);

loadVersions();
checkAppUpdate();
loadHealth();
refreshJobs();
setInterval(refreshJobs, 1200);
