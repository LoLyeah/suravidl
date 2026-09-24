"""Extension end-to-end test in a real Chrome (headless, CDP-driven).

Launches Chrome with the unpacked extension, then over CDP:
  1. verifies the background service worker loaded
  2. configures storage (engine URL + token)
  3. calls sendToEngine() directly -> engine downloads the fixture
  4. opens a page with a <video>, verifies detection + header capture
  5. screenshots popup.html

Usage: python ext_e2e.py <chrome-binary> <extension-dir> <engine-url> <fixture-url> <token>
Requires: websocket-client (pip install websocket-client)
"""
import json
import subprocess
import sys
import time
import urllib.request

import websocket

chrome_bin, ext_dir, engine_url, fixture_url, token = sys.argv[1:6]
PORT = 9223
profile = "/tmp/ext_e2e_profile"

chrome = subprocess.Popen([
    chrome_bin, "--headless=new", "--no-sandbox", "--disable-gpu",
    "--no-first-run",
    "--user-data-dir=" + profile, "--remote-debugging-port=" + str(PORT),
    "--remote-allow-origins=*",
    "--load-extension=" + ext_dir, "about:blank",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=15)
        self.i = 0

    def call(self, method, **params):
        self.i += 1
        self.ws.send(json.dumps(
            {"id": self.i, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.i:
                if "error" in msg:
                    raise RuntimeError(str(msg["error"]))
                return msg.get("result", {})


try:
    ws_url = None
    ext_id = None
    deadline = time.time() + 20
    while time.time() < deadline and not ext_id:
        try:
            targets = json.loads(urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/json/list", timeout=2).read())
        except Exception:
            time.sleep(0.5)
            continue
        for t in targets:
            if t.get("type") == "service_worker" and \
                    t.get("url", "").startswith("chrome-extension://") and \
                    t.get("url", "").endswith("background.js"):
                probe = CDP(t["webSocketDebuggerUrl"])
                try:
                    name = probe.call("Runtime.evaluate",
                                      expression="chrome.runtime.getManifest().name",
                                      returnByValue=True).get(
                                          "result", {}).get("value")
                except Exception:
                    continue
                if name == "suravidl":
                    ext_id = t["url"].split("/")[2]
                    ws_url = t["webSocketDebuggerUrl"]
                    break
    if not ext_id:
        print("E2E_FAIL: extension service worker not found")
        sys.exit(1)
    print(f"extension id: {ext_id}")

    sw = CDP(ws_url)

    def evaluate(expr, await_promise=True):
        r = sw.call("Runtime.evaluate", expression=expr,
                    awaitPromise=await_promise, returnByValue=True)
        val = r.get("result", {})
        if val.get("subtype") == "error":
            raise RuntimeError(val.get("description", "eval error"))
        return val.get("value")

    # 2. configure storage
    evaluate(
        f'chrome.storage.local.set({{engineUrl: {json.dumps(engine_url)}, '
        f'engineToken: {json.dumps(token)}}})', await_promise=False)
    print("storage configured")

    # 3. direct handoff: sendToEngine downloads the fixture
    result = evaluate(
        f'sendToEngine({json.dumps(fixture_url)})')
    if not result or not result.get("ok"):
        print(f"E2E_FAIL: sendToEngine -> {result}")
        sys.exit(1)
    print(f"handoff OK, job {result['job']['id']}")

    # 4. open a video page, verify detection + header capture
    page = sw.call("Target.createTarget",
                   url=f"{fixture_url.rsplit('/', 1)[0]}/video-test.html")
    time.sleep(2.5)
    media = evaluate('new Promise(res => chrome.storage.local.get('
                     '{tabMedia: {}, reqHeaders: {}}, s => res(s)))')
    tab_urls = [m["url"] for lst in (media.get("tabMedia") or {}).values()
                for m in lst]
    if not any(u.endswith("tiny.mp4") for u in tab_urls):
        print(f"E2E_FAIL: detection missed the video: {tab_urls}")
        sys.exit(1)
    print("detection OK:", tab_urls)
    hdrs = (media.get("reqHeaders") or {}).get(fixture_url, {}).get("headers", {})
    if not hdrs.get("user-agent"):
        print(f"E2E_FAIL: no captured UA: {hdrs}")
        sys.exit(1)
    print("header capture OK:", sorted(hdrs))

    # 5. popup screenshot (popup is a page target — needs its own connection)
    pop = sw.call("Target.createTarget",
                  url=f"chrome-extension://{ext_id}/popup.html")
    pop_id = pop["targetId"]
    time.sleep(1.0)
    pop_ws = None
    for _ in range(20):
        targets = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/json/list", timeout=2).read())
        for t in targets:
            if t.get("type") == "page" and \
                    t.get("url") == f"chrome-extension://{ext_id}/popup.html":
                pop_ws = t["webSocketDebuggerUrl"]
                break
        else:
            time.sleep(0.3)
            continue
        break
    page_cdp = CDP(pop_ws)
    # the popup-as-tab has no "active tab" context; inject the detected item
    page_cdp.call("Runtime.evaluate", expression=(
        "render([{url: " + json.dumps(fixture_url) + ", hasHeaders: true}])"))
    time.sleep(0.5)
    shot = page_cdp.call("Page.captureScreenshot")
    import base64

    with open("/tmp/ext_popup.png", "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    try:
        sw.call("Target.closeTarget", targetId=pop_id)
    except Exception:
        pass  # cosmetic; some builds refuse cross-target closes
    print("popup screenshot -> /tmp/ext_popup.png")

    # wait for the engine jobs to finish and verify files on disk
    dl = json.loads(urllib.request.urlopen(
        urllib.request.Request(f"{engine_url}/jobs",
                               headers={"Authorization": f"Bearer {token}"}),
        timeout=10).read())
    states = {j["status"] for j in dl["jobs"]}
    files = [j["filepath"] for j in dl["jobs"] if j.get("filepath")]
    import os

    ok = states <= {"completed"} and all(os.path.exists(f) for f in files)
    print("E2E_PASS" if ok else f"E2E_FAIL: states={states} files={files}")
    sys.exit(0 if ok else 1)
finally:
    chrome.terminate()
