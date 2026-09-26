package com.suravidl.app

import org.json.JSONArray
import org.json.JSONObject

/**
 * The scripts the sniffer runs *inside the page* (capture layers 3 and 4).
 *
 * Why scripts at all: `shouldInterceptRequest` is never called for `blob:`
 * URLs — Chromium does not report them, by design (verified in the M1
 * research). A player that builds a MediaSource and plays it gives the network
 * layer nothing to see, so the only place left to stand is inside the page.
 *
 * The hooks are installed with `evaluateJavascript`, which needs no extra
 * dependency (this WebView already has JS on — it renders the page) and cannot
 * be blocked by the page's CSP. The known limit: `onPageStarted` runs after a
 * very early inline script, so the hooks also re-install at `onPageFinished`
 * and the layer-4 resource scan sweeps up anything that ran before them.
 *
 * Frames: hooks are re-installed into every *same-origin* child frame (found
 * by walking the DOM and watching for new iframes plus their `load` events),
 * and each report carries the frame's own URL — a signed media URL's referer
 * is usually the player iframe, not the page in the address bar. A
 * cross-origin frame's `blob:` player stays invisible to this layer; its plain
 * media URLs are still caught by the network layer, which sees every frame.
 */
object SniffScript {

    /**
     * The body, with the pattern list spliced in. Deliberately self-contained:
     * it is also the text handed to child frames, which is why the source is
     * published on `window.__svSniffSrc` instead of quoting itself (a script
     * cannot contain its own final form).
     */
    private val BODY = """
        if (window.__svSniffDoc === document) return; window.__svSniffDoc = document;
        var EX = __EX__, HI = __HI__;
        var RE = new RegExp('\\.(' + EX.join('|') + ')(\\?|${'$'})', 'i');
        var B = window.SuravidlSniff;
        if (!B) return;
        function P(u) {
          if (!u || typeof u !== 'string') return false;
          var s = u.split('#')[0].toLowerCase();
          if (RE.test(s)) return true;
          for (var i = 0; i < HI.length; i++) { if (s.indexOf(HI[i]) >= 0) return true; }
          return false;
        }
        function rep(u, via) {
          try {
            if (!u) return;
            u = String(u);
            if (u.indexOf('mse:') === 0) { B.report(u, 'mse', location.href); return; }
            u = new URL(u, location.href).href;
            if (!/^(https?:|blob:)/i.test(u)) return;
            if (!P(u) && via !== 'mse') return;
            B.report(u, via, location.href);
          } catch (e) {}
        }
        function srcs() {
          try {
            var v = document.querySelectorAll('video, audio, source');
            for (var i = 0; i < v.length; i++) {
              var s = v[i].currentSrc || v[i].src;
              if (!s) continue;
              // A blob: source *is* a JavaScript-fed stream (MediaSource), so it
              // is reported as one even when the hooks that would have watched
              // it being created were installed too late to see that happen.
              if (String(s).indexOf('blob:') === 0) rep(s, 'mse'); else rep(s, 'player');
            }
          } catch (e) {}
        }
        function injectFrame(f) {
          try {
            var w = f.contentWindow; if (!w) return;
            var src = window.__svSniffSrc || '';
            if (!src) return;
            w.__svSniffSrc = src;
            w.eval(src);
          } catch (e) {}
        }
        function injectFrames() {
          try {
            var fr = document.querySelectorAll('iframe, frame');
            for (var i = 0; i < fr.length; i++) {
              var f = fr[i];
              try { if (!f.__svWatched) { f.__svWatched = true; f.addEventListener('load', function () { injectFrame(this); }); } } catch (e) {}
              injectFrame(f);
            }
          } catch (e) {}
        }
        try { var f0 = window.fetch; if (f0) window.fetch = function (i) { try { rep(typeof i === 'string' ? i : (i && i.url), 'fetch'); } catch (e) {} return f0.apply(this, arguments); }; } catch (e) {}
        try { var x0 = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function (m, u) { try { rep(u, 'xhr'); } catch (e) {} return x0.apply(this, arguments); }; } catch (e) {}
        try {
          var d = Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'src');
          if (d && d.set) Object.defineProperty(HTMLMediaElement.prototype, 'src', {
            configurable: true, get: d.get,
            set: function (u) { try { rep(u, 'player'); } catch (e) {} return d.set.call(this, u); }
          });
        } catch (e) {}
        try {
          var c0 = URL.createObjectURL;
          if (c0) URL.createObjectURL = function (o) {
            var u = c0.apply(this, arguments);
            try { var n = o && o.constructor ? o.constructor.name : ''; if (n === 'MediaSource' || n === 'SourceBuffer') rep(u, 'mse'); } catch (e) {}
            return u;
          };
        } catch (e) {}
        try {
          if (window.MediaSource && MediaSource.prototype.addSourceBuffer) {
            var a0 = MediaSource.prototype.addSourceBuffer;
            MediaSource.prototype.addSourceBuffer = function (t) {
              try { rep('mse:' + t, 'mse'); } catch (e) {}
              return a0.apply(this, arguments);
            };
          }
        } catch (e) {}
        srcs();
        injectFrames();
        try { new MutationObserver(function () { srcs(); injectFrames(); }).observe(document.documentElement || document, { childList: true, subtree: true }); } catch (e) {}
        try { window.addEventListener('load', function () { srcs(); injectFrames(); }); } catch (e) {}
    """.trimIndent()

    /** Layer 4: what the page already loaded, straight from the performance
     *  timeline — catches media that started before the hooks were installed. */
    private val SCAN = """
        (function () {
          try {
            var B = window.SuravidlSniff; if (!B) return;
            var es = performance.getEntriesByType ? performance.getEntriesByType('resource') : [];
            var EX = __EX__, HI = __HI__;
            var RE = new RegExp('\\.(' + EX.join('|') + ')(\\?|${'$'})', 'i');
            for (var i = 0; i < es.length; i++) {
              var u = es[i] && es[i].name; if (!u) continue;
              var s = u.split('#')[0].toLowerCase();
              var hit = RE.test(s);
              if (!hit) { for (var j = 0; j < HI.length; j++) { if (s.indexOf(HI[j]) >= 0) { hit = true; break; } } }
              if (hit) B.report(u, 'scan', location.href);
            }
          } catch (e) {}
        })();
    """.trimIndent()

    /** The hooks, ready to inject: source published, then the body runs. */
    fun js(): String {
        val wrapped = "(function () {\n" + fill(BODY) + "\n})();"
        return "try { window.__svSniffSrc = " + JSONObject.quote(wrapped) +
            "; } catch (e) {}" + wrapped
    }

    fun scan(): String = fill(SCAN)

    private fun fill(script: String): String = script
        .replace("__EX__", JSONArray(SniffPatterns.extList()).toString())
        .replace("__HI__", JSONArray(SniffPatterns.hintList()).toString())
}
