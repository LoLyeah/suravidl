const $ = (id) => document.getElementById(id);
applyI18n();

chrome.storage.local.get({ engineUrl: "http://127.0.0.1:8787", engineToken: "" }, (v) => {
  $("engineUrl").value = v.engineUrl;
  $("engineToken").value = v.engineToken;
});

$("save").onclick = async () => {
  await chrome.storage.local.set({
    engineUrl: $("engineUrl").value.trim().replace(/\/$/, ""),
    engineToken: $("engineToken").value.trim(),
  });
  $("msg").textContent = t("saved");
  setTimeout(() => ($("msg").textContent = ""), 1500);
};
