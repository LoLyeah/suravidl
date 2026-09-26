const listEl = document.getElementById("list");
const statusEl = document.getElementById("status");

// The engine sorts the finds into shape (playlist / fragment / plain media) and
// says which fragments belong to a playlist that is already in the list. No
// answer — engine not up, token not set — means show everything: a shell never
// hides something on a guess.
function render(items, ranking) {
  const shape = {};
  let hidden = 0;
  for (const it of (ranking && ranking.items) || []) {
    shape[it.url] = it;
    if (it.hidden) hidden++;
  }
  const visible = items.filter((m) => !(shape[m.url] && shape[m.url].hidden));
  if (!visible.length) {
    listEl.innerHTML = '<div class="empty">No media detected on this tab yet.<br/>Play the video, then reopen this popup.</div>';
    return;
  }
  listEl.innerHTML = "";
  visible.reverse().forEach((m) => {
    const div = document.createElement("div");
    div.className = "item";
    const short = m.url.length > 90 ? m.url.slice(0, 90) + "…" : m.url;
    const title = document.createElement("div");
    title.textContent = short;
    const meta = document.createElement("div");
    meta.className = "url";
    const kind = (shape[m.url] && shape[m.url].kind) || "";
    meta.textContent = [
      kind === "manifest" ? "playlist" : "",
      kind === "segment" ? "fragment" : "",
      m.hasHeaders ? "with site cookies" : "",
      new URL(m.url).protocol + " stream",
    ].filter(Boolean).join(" · ");
    const btn = document.createElement("button");
    btn.textContent = "Download with suravidl";
    btn.onclick = async () => {
      statusEl.textContent = "sending…";
      statusEl.className = "";
      const res = await chrome.runtime.sendMessage({ type: "sendToEngine", url: m.url });
      if (res && res.ok) {
        statusEl.textContent = "✓ sent to engine (job " + res.job.id + ")";
        statusEl.className = "ok";
      } else {
        statusEl.textContent = "✗ " + ((res && res.error) || "engine unreachable — is it running?");
        statusEl.className = "err";
      }
    };
    div.append(title, meta, btn);
    listEl.appendChild(div);
  });
  if (hidden) {
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = hidden + (hidden === 1 ? " fragment" : " fragments") +
      " hidden — part of the playlist above";
    listEl.appendChild(note);
  }
}

(async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return render([]);
  const res = await chrome.runtime.sendMessage({ type: "getMedia", tabId: tab.id });
  const items = (res && res.items) || [];
  let ranking = null;
  try {
    ranking = await chrome.runtime.sendMessage({ type: "rank", items });
  } catch (e) {
    /* the engine is not answering — show everything */
  }
  render(items, ranking);
})();
