// The extension's own phrasebook (v0.44.x): the same zero-build pattern the
// app ships — the English text is the key, one dictionary, one t(). The
// language follows the browser UI (navigator.language); anything starting
// with "id" gets Bahasa Indonesia.
//
// Loaded before popup.js / options.js (see the script tags). Nothing here
// touches the network, storage, or the DOM at import time — the guarded
// applyI18n() is what paints the static strings, and the Node test harness
// (no querySelectorAll) walks past it.
const I18N = {
  "checking…": "memeriksa…",
  "which ones": "yang mana saja",
  "Select all": "Pilih semua",
  "Select none": "Kosongkan",
  "Choose quality in suravidl": "Pilih kualitas di suravidl",
  "Quick download — best quality": "Unduh cepat — kualitas terbaik",
  "Nothing playing yet": "Belum ada yang diputar",
  "If this page has a video, play it for a moment, then press Check again.":
    "Kalau halaman ini memutar video, putar sebentar lalu tekan Cek lagi.",
  "Check again": "Cek lagi",
  "suravidl isn’t running": "suravidl sedang tidak berjalan",
  "Open the suravidl app, then try again.": "Buka aplikasi suravidl, lalu coba lagi.",
  "Try again": "Coba lagi",
  "Engine settings…": "Pengaturan mesin…",
  "Not installed yet?": "Belum terpasang?",
  "Get suravidl from GitHub ↗": "Dapatkan suravidl dari GitHub ↗",
  "Playlist": "Daftar putar",
  "Video": "Video",
  "Fragment": "Fragmen",
  "Stream": "Stream",
  "Queue all {n} at best quality": "Antre {n} sekaligus — kualitas terbaik",
  "Sending to suravidl…": "Mengirim ke suravidl…",
  "✓ Sent — suravidl is downloading it in best quality.":
    "✓ Terkirim — suravidl mengunduhnya dengan kualitas terbaik.",
  "✓ Sent — {n} downloading at best quality.":
    "✓ Terkirim — {n} diunduh dengan kualitas terbaik.",
  "{n} skipped.": "{n} dilewati.",
  "✓ Sent — this suravidl build downloads it straight away.":
    "✓ Terkirim — build suravidl ini langsung mengunduhnya.",
  "✓ Sent — choose the quality in suravidl.":
    "✓ Terkirim — pilih kualitasnya di suravidl.",
  "Couldn't reach suravidl — open the app, then try again.":
    "Tidak bisa menjangkau suravidl — buka aplikasinya, lalu coba lagi.",
  "suravidl didn't accept the saved token — open Engine settings and paste the current one.":
    "suravidl menolak token tersimpan — buka Pengaturan mesin dan tempel token terbaru.",
  "suravidl couldn't read this one — the app knows why.":
    "suravidl tidak bisa membaca yang ini — aplikasinya tahu kenapa.",
  "something went wrong sending it — try again.":
    "ada yang salah saat mengirim — coba lagi.",
  "Recent downloads": "Unduhan terbaru",
  "Queued": "Dalam antrean",
  "Downloading": "Mengunduh",
  "Finalizing": "Menyelesaikan",
  "Done": "Selesai",
  "Failed": "Gagal",
  "Stopped": "Dihentikan",
  "Cancelled": "Dibatalkan",
  "Paused": "Dijeda",
  "engine ready": "mesin siap",
  "not running": "tidak berjalan",
  "Video found on this page": "Video ditemukan di halaman ini",
  "{n} streams found on this page": "{n} stream ditemukan di halaman ini",
  "Tick the ones you want — queue them all at best, or choose quality for the first in the app.":
    "Centang yang kamu mau — antre semuanya sekaligus, atau pilih kualitas untuk yang pertama di aplikasi.",
  "The quality picker is in the app — suravidl opens ready to choose.":
    "Pemilih kualitas ada di aplikasi — suravidl terbuka siap memilih.",
  "Show the raw link — {name}": "Tampilkan tautan mentah — {name}",
  "Engine URL": "URL mesin",
  "API token": "API token",
  "Save": "Simpan",
  "saved": "tersimpan",
  "from suravidl → Settings → Authentication": "dari suravidl → Pengaturan → Autentikasi",
};

const LANG = (typeof navigator !== "undefined" && navigator
              && String(navigator.language || "").toLowerCase().startsWith("id"))
  ? "id" : "en";

function t(s, vars) {
  let out = (LANG === "id" && I18N[s] != null) ? I18N[s] : s;
  if (vars) {
    for (const k of Object.keys(vars)) {
      out = out.split("{" + k + "}").join(String(vars[k]));
    }
  }
  return out;
}

/** Everything static in the page, one pass — the app's own pattern. */
function applyI18n() {
  if (!document.querySelectorAll) return;   // the Node harness has no DOM
  document.querySelectorAll("[data-i18n]").forEach((n) => {
    n.textContent = t(n.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((n) => {
    n.placeholder = t(n.dataset.i18nPh);
  });
  if (document.documentElement) document.documentElement.lang = LANG;
}
