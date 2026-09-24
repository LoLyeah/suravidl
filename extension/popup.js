const listEl = document.getElementById("list");
const statusEl = document.getElementById("status");

function render(items) {
  if (!items.length) {
    listEl.innerHTML = '<div class="empty">No media detected on this tab yet.<br/>Play the video, then reopen this popup.</div>';
    return;
  }
  listEl.innerHTML = "";
  items.reverse().forEach((m) => {
    const div = document.createElement("div");
    div.className = "item";
    const short = m.url.length > 90 ? m.url.slice(0, 90) + "…" : m.url;
    const title = document.createElement("div");
    title.textContent = short;
    const meta = document.createElement("div");
    meta.className = "url";
    meta.textContent = (m.hasHeaders ? "with site cookies · " : "") +
      new URL(m.url).protocol + " stream";
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
}

(async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab) return render([]);
  const res = await chrome.runtime.sendMessage({ type: "getMedia", tabId: tab.id });
  render((res && res.items) || []);
})();
