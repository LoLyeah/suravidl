const $ = (id) => document.getElementById(id);
applyI18n();

// the version chip reads the manifest — a bump can never leave it stale
const MANIFEST = (chrome.runtime && chrome.runtime.getManifest)
  ? chrome.runtime.getManifest() : null;
if (MANIFEST && $("ver")) $("ver").textContent = "v" + MANIFEST.version;

// The token is not a preference: without it the engine answers 401 to every
// request. The field is marked required, and an empty one keeps a warning on
// screen instead of waiting for a failed download to explain it (unreleased).
const tokenWarning = () => {
  const field = $("engineToken"), warn = $("tokenWarn");
  if (field && warn) warn.hidden = !!field.value.trim();
};

chrome.storage.local.get({ engineUrl: "http://127.0.0.1:8787", engineToken: "" }, (v) => {
  if ($("engineUrl")) $("engineUrl").value = v.engineUrl;
  if ($("engineToken")) $("engineToken").value = v.engineToken;
  tokenWarning();
});
if ($("engineToken")) $("engineToken").addEventListener("input", tokenWarning);

// the token is a secret on a shared screen: hidden until asked (v0.5.19)
const reveal = $("reveal");
if (reveal) {
  reveal.onclick = () => {
    const field = $("engineToken");
    const hidden = field.type === "password";
    field.type = hidden ? "text" : "password";
    reveal.textContent = t(hidden ? "Hide" : "Show");
  };
}

const form = $("engineForm");
if (form) {
  form.onsubmit = (e) => {
    e.preventDefault();      // Enter must save, not reload the page
    $("save").click();
  };
}

$("save").onclick = async () => {
  const token = $("engineToken").value.trim();
  await chrome.storage.local.set({
    engineUrl: $("engineUrl").value.trim().replace(/\/$/, ""),
    engineToken: token,
  });
  tokenWarning();
  $("msg").textContent = token
    ? t("saved")
    : t("saved — but no token: downloads will be refused");
  setTimeout(() => ($("msg").textContent = ""), 2500);
};
