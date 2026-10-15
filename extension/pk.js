// The key side of the sniffer (v0.5.16) — MAIN world, Chrome/Edge only.
//
// Some players scramble every playlist and keep the decode key in page
// memory (`window.__pk`, exported by the player's own WASM — the
// flixcloud embeds behind reanime.to do exactly this). The isolated-world
// sniffer cannot read page variables, so this little reader lives in the
// page's own world, watches for the key, and hands it to the content
// script over postMessage. It never touches the network, never writes
// anything, and reads exactly one variable.
//
// Firefox needs none of this: its MV2 content scripts read page globals
// through window.wrappedJSObject directly (see pagefind.js), so the
// Firefox manifest does not ship this file.
(() => {
  let last = null;

  function post() {
    try {
      const pk = window.__pk;
      if (typeof pk === "string" && pk.length >= 16 && pk.length <= 512
          && pk !== last) {
        last = pk;
        window.postMessage({ __svPk: pk }, "*");
      }
    } catch (_) { /* a reader must never break the page */ }
  }

  // The player sets the key once, shortly after it starts; poll for a
  // while, then keep answering on demand (the popup may send minutes
  // later, and the value stays on the window until a reload). Bounded and
  // unref'd: a Node harness evaluating this file must still be able to
  // exit (browsers have no unref — the guard keeps it honest there too).
  let ticks = 0;
  const t = setInterval(() => {
    post();
    if (++ticks > 600) clearInterval(t);   // ~10 minutes of looking
  }, 1000);
  if (t && t.unref) t.unref();
  window.addEventListener("message", (e) => {
    if (e.source !== window || !e.data || e.data.__svPkAsk !== true) return;
    post();
  });
  post();
})();
