const CFG = window.__SURAVIDL__ || {};
const H = () => ({
  "Authorization": "Bearer " + CFG.token,
  "Content-Type": "application/json",
});

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: H() });
  if (!r.ok) {
    let msg = `${r.status}`;
    let detail = null;
    try {
      const body = await r.json();
      detail = body && body.detail != null ? body.detail : body;
      // the engine can answer with a structured error ("unsupported url"
      // carries a hint for the user and a flag for the browser offer), so the
      // whole detail rides along on the Error instead of being flattened
      msg = (typeof detail === "object" && detail !== null)
        ? (detail.message || JSON.stringify(detail))
        : String(detail);
    } catch (_) {
      msg += " " + (await r.text().catch(() => ""));
    }
    const err = new Error(msg);
    err.detail = detail;
    throw err;
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

/** The last segment of a path, whichever slash the platform uses. A Windows
 *  path has no "/" at all, so the old slash-only split handed the whole path
 *  back — the filed-takes rail printed "C:\Users\Han\Downloads\index.mp4"
 *  on one line, and nothing clipped it: it slid out of the 236px rail, under
 *  the queue card, and bled through the glass into the card's title row
 *  (2026-10-02 report). */
function baseName(p) {
  return String(p ?? "").split(/[\\/]/).pop();
}

/* ---------- i18n: zero-build strings (v0.44.0) -----------------------------
   No bundler, no build step — a plain dictionary and one t(), by house rule.
   The English string IS the key: t("Open folder") looks itself up in the
   chosen language and falls back to the key, so a missing dictionary or a
   missing entry can only ever show English. {name} placeholders inside a
   value are filled from t()'s second argument. `id` carries the
   translations; `en` stays empty on purpose — the keys ARE English. */
/* i18n-dicts:start */
const STRINGS = { en: {}, id: {
  " Bypass “not available in your country” ": " Lewati “tidak tersedia di negaramu” ",
  " Convert subtitles to .srt ": " Konversi subtitle ke .srt ",
  " Embed metadata (title, artist, description) ": " Sematkan metadata (judul, artis, deskripsi) ",
  " Embed thumbnail ": " Sematkan thumbnail ",
  " Enable raw yt-dlp arguments ": " Aktifkan argumen mentah yt-dlp ",
  " Include auto-generated captions ": " Sertakan subtitle otomatis ",
  " Live streams: record from the beginning ": " Siaran langsung: rekam dari awal ",
  " Open the folder when a download finishes ": " Buka folder saat unduhan selesai ",
  " Paste a link above and hit ": " Tempel tautan di atas lalu tekan ",
  " Resume interrupted downloads after a restart ": " Lanjutkan unduhan yang terputus setelah mulai ulang ",
  " Skip TLS certificate checks ": " Lewati pemeriksaan sertifikat TLS ",
  " Skip videos already downloaded before (archive) ": " Lewati video yang sudah pernah diunduh (arsip) ",
  " Verbose log ": " Log verbose ",
  " becomes editable, and every option yt-dlp supports can be browsed there.": " menjadi bisa diedit, dan semua opsi yt-dlp bisa dijelajahi di sana.",
  " keeps things tidy": " membuat semuanya rapi",
  " tab holds the option groups, the ": " memuat kelompok opsi, tab ",
  " tab your defaults and presets. ": " menyimpan bawaan dan presetmu. ",
  " · a relative folder like ": " · folder relatif seperti ",
  " — queue them all?": " — antrekan semuanya?",
  " — the formats, sizes and what each stream contains show up here. The ": " — format, ukuran, dan isi setiap stream muncul di sini. Tab ",
  " — with 1 option set below": " — dengan 1 opsi di bawah",
  " — with preset “{name}”": " — dengan preset “{name}”",
  " — with {n} options set below": " — dengan {n} opsi di bawah",
  " — {label}": " — {label}",
  " — “{name}” skipped: your format pick replaces it": " — “{name}” dilewati: pilihan formatmu menggantikannya",
  "(TVs and most players cannot read the .vtt that YouTube serves)": "(TV dan kebanyakan pemutar tidak bisa membaca .vtt dari YouTube)",
  "(built-in)": "(bawaan)",
  "(bundled)": "(bawaan)",
  "(desktop app)": "(aplikasi desktop)",
  "(downloaded)": "(diunduh)",
  "(for a TLS-inspecting proxy)": "(untuk proxy yang memeriksa TLS)",
  "(frees memory)": "(membebaskan memori)",
  "(keeps the .jpg too)": "(menyimpan .jpg-nya juga)",
  "(power users — off by default)": "(pengguna mahir — bawaan mati)",
  "(when the site still serves it — otherwise from the moment you hit download)": "(saat situsnya masih menyediakannya — kalau tidak, sejak kamu menekan unduh)",
  "(yt-dlp's full log — debugging)": "(log penuh yt-dlp — debugging)",
  "({domains})": "({domains})",
  "+{n} more": "+{n} lagi",
  ", several separated by ": ", beberapa dipisah dengan ",
  "0–30 · per download, on a flaky connection": "0–30 · per unduhan, di koneksi yang tidak stabil",
  "1 day ago": "1 hari lalu",
  "1 file": "1 berkas",
  "1 hour ago": "1 jam lalu",
  "1 job hidden by this filter": "1 unduhan disembunyikan oleh filter ini",
  "1 link": "1 tautan",
  "1 match": "1 cocok",
  "1 minute ago": "1 menit lalu",
  "1 option": "1 opsi",
  "1 option set below": "1 opsi disiapkan di bawah",
  "1 skipped — not a link": "1 dilewati — bukan tautan",
  "1–16 · faster HLS/DASH downloads": "1–16 · unduhan HLS/DASH lebih cepat",
  "1–4 · applied live": "1–4 · langsung diterapkan",
  "<1 min": "<1 menit",
  "? (its size could not be read) This cannot be undone.": "? (ukurannya tidak bisa dibaca) Ini tidak bisa dibatalkan.",
  "? This cannot be undone.": "? Ini tidak bisa dibatalkan.",
  "A download that picks its own preset or quality still wins over this one; it fills in the rest.": "Unduhan yang membawa preset atau kualitas sendiri tetap menang atas ini; preset ini mengisi sisanya.",
  "A link or a direct stream — which one do I paste?": "Tautan atau stream langsung — mana yang kucolok?",
  "A link says 'unsupported URL'. What now?": "Ada tautan bilang 'unsupported URL'. Bagaimana?",
  "A page keeps bouncing me at ads.": "Ada halaman yang terus menghadang dengan iklan.",
  "A site asks me to turn off my ad blocker.": "Ada situs meminta mematikan pemblokir iklan.",
  "A site won't offer 1080p or 4K.": "Ada situs yang tidak menawarkan 1080p atau 4K.",
  "API token": "Token API",
  "Active": "Aktif",
  "Added to downloads": "Masuk ke unduhan",
  "Advanced": "Lanjutan",
  "After a probe this area lists the real formats: take one, or arm a take for the transport below.": "Setelah Cek, area ini menampilkan format aslinya: ambil satu, atau siapkan pilihan untuk bar di bawah.",
  "All": "Semua",
  "All yt-dlp options ": "Semua opsi yt-dlp ",
  "Already downloaded before": "Sudah pernah diunduh",
  "Any site yt-dlp knows, or a direct mp4/m3u8 stream — then press Probe.": "Situs apa pun yang dikenal yt-dlp, atau stream mp4/m3u8 langsung — lalu tekan Cek.",
  "Appearance": "Tampilan",
  "Applied to every download. Flags the engine owns are refused (playlists, cookies, archive, ": "Diterapkan ke setiap unduhan. Flag yang dimiliki engine ditolak (playlist, cookie, arsip, ",
  "Apply": "Terapkan",
  "Arguments": "Argumen",
  "Audio only:": "Audio saja:",
  "Audio track:": "Trek audio:",
  "Authentication": "Autentikasi",
  "Authentication ": "Autentikasi ",
  "Auto — whatever the site serves": "Otomatis — apa pun dari situsnya",
  "Automatic": "Otomatis",
  "Back": "Kembali",
  "Battery settings — allow background downloads": "Setelan baterai — izinkan unduhan latar belakang",
  "Browser cookies: off": "Cookie browser: mati",
  "Browser to impersonate": "Browser yang ditiru",
  "Browser to take cookies from": "Browser sumber cookie",
  "Browse…": "Telusuri…",
  "Cancel": "Batalkan",
  "Cancel download": "Batalkan unduhan",
  "Chapters:": "Bab:",
  "Check now": "Cek sekarang",
  "Checking the queue…": "Memeriksa antrean…",
  "Clear": "Bersihkan",
  "Clear app cache": "Bersihkan cache aplikasi",
  "Clear the app cache{what}? Player data yt-dlp simply fetches again — nothing downloaded is touched.": "Bersihkan cache aplikasi{what}? Data player tinggal diambil ulang yt-dlp — tidak ada unduhan yang tersentuh.",
  "Clip end time": "Waktu akhir klip",
  "Clip — only a section": "Klip — hanya sebagian",
  "Close": "Tutup",
  "Concurrent downloads": "Unduhan bersamaan",
  "Confirm": "Konfirmasi",
  "Container": "Kontainer",
  "Cookies on this device": "Cookie di perangkat ini",
  "Cookies, tools, updates, appearance — and the yt-dlp tab lists every option the engine takes.": "Cookie, alat, pembaruan, tampilan — dan tab yt-dlp mencantumkan semua opsi yang diterima engine.",
  "Copied": "Tersalin",
  "Copy": "Salin",
  "Curated options": "Opsi terkurasi",
  "Dark": "Gelap",
  "Default preset ": "Preset bawaan ",
  "Delete": "Hapus",
  "Delete 1 file ({size})": "Hapus 1 berkas ({size})",
  "Delete app copies — keep Gallery/Music": "Hapus salinan aplikasi — simpan Galeri/Musik",
  "Delete downloaded files": "Hapus berkas unduhan",
  "Delete every downloaded file": "Hapus semua berkas unduhan",
  "Delete stored cookies": "Hapus cookie tersimpan",
  "Delete the copy downloaded from PyPI — suravidl falls back to the yt-dlp bundled with the app": "Hapus salinan dari PyPI — suravidl kembali ke yt-dlp bawaan aplikasi",
  "Delete the preset “{name}”? Downloads already started keep their options.": "Hapus preset “{name}”? Unduhan yang sudah berjalan tetap memakai opsinya.",
  "Delete this download — the file on disk goes with it": "Hapus unduhan ini — berkasnya di disk ikut terhapus",
  "Delete {n} files ({size})": "Hapus {n} berkas ({size})",
  "Delete “{name}”?": "Hapus “{name}”?",
  "Device": "Perangkat",
  "Done": "Selesai",
  "Download": "Unduh",
  "Download archive ": "Arsip unduhan ",
  "Download as files (.vtt)": "Unduh sebagai berkas (.vtt)",
  "Download folder": "Folder unduhan",
  "Download manually": "Unduh manual",
  "Download playlist": "Unduh daftar putar",
  "Download {count} picked": "Unduh {count} terpilih",
  "Downloaded files": "Berkas unduhan",
  "Downloading…": "Mengunduh…",
  "Downloads": "Unduhan",
  "Downloads land in the app's own folder, which a file manager cannot open. \"Delete app copies\" frees that folder and keeps the Gallery/Music copy you can open; \"Delete downloaded files\" removes both. \"Clear app cache\" frees only the player data yt-dlp re-fetches — no download is touched.": "Unduhan mendarat di folder aplikasi sendiri, yang tidak bisa dibuka oleh pengelola berkas. \"Hapus salinan aplikasi\" membebaskan folder itu dan menyimpan salinan Galeri/Musik yang bisa kamu buka; \"Hapus berkas unduhan\" menghapus keduanya. \"Bersihkan cache aplikasi\" hanya membebaskan data pemutar yang diambil ulang yt-dlp — tidak ada unduhan yang tersentuh.",
  "ETA {n}s": "sisa {n} dtk",
  "Edit & retry": "Ubah & coba lagi",
  "Embed into the video": "Sematkan ke video",
  "Errors": "Eror",
  "Extractor arguments": "Argumen extractor",
  "FAQ has the common answers; this tour replays from the same row whenever you like.": "FAQ berisi jawaban umum; tur ini bisa diputar ulang dari baris yang sama kapan saja.",
  "FILED": "SELESAI",
  "Filed": "Selesai",
  "Filed takes": "Unduhan selesai",
  "Filed — {name}": "Tersimpan — {name}",
  "Filename template": "Templat nama berkas",
  "Files ({n})": "Berkas ({n})",
  "Filter the queue": "Filter antrean",
  "Find a video on a page": "Temukan video di halaman",
  "Finished downloads land in this rail — click one to play it.": "Unduhan yang selesai mendarat di rel ini — klik satu untuk memutarnya.",
  "Formats": "Format",
  "Frosted": "Buram",
  "Gallery/Music copies kept": "salinan Gallery/Music dipertahankan",
  "General": "Umum",
  "Get it": "Ambil",
  "Get {v}": "Ambil {v}",
  "Glass style": "Gaya kaca",
  "Glass: {name}": "Kaca: {name}",
  "Got it": "Mengerti",
  "Hide details": "Sembunyikan detail",
  "Hide files ({n})": "Sembunyikan berkas ({n})",
  "How do I update?": "Bagaimana cara memperbarui?",
  "I'll remind you tomorrow": "Aku ingatkan besok",
  "IPv4 only": "Hanya IPv4",
  "IPv4-only fixes downloads that stall or reset on a network with broken IPv6.": "Hanya IPv4 memperbaiki unduhan yang macet atau terputus di jaringan dengan IPv6 bermasalah.",
  "IPv6 only": "Hanya IPv6",
  "Impersonate Chrome — strict bot checks (e.g. Facebook)": "Tiru Chrome — pemeriksaan bot ketat (mis. Facebook)",
  "Impersonate Edge": "Tiru Edge",
  "Impersonate Firefox": "Tiru Firefox",
  "Impersonate Safari": "Tiru Safari",
  "Impersonate: off": "Tiru: mati",
  "Imported cookies are encrypted with a key that only this device holds (Android Keystore). A readable copy exists only while the app is running, and is removed when you quit or delete them.": "Cookie impor dienkripsi dengan kunci yang hanya dipegang perangkat ini (Android Keystore). Salinan yang bisa dibaca hanya ada selama aplikasi berjalan, dan dihapus saat kamu keluar atau menghapusnya.",
  "Import…": "Impor…",
  "Install now": "Pasang sekarang",
  "Install update": "Pasang pembaruan",
  "Installed: ": "Terpasang: ",
  "Its Gallery/Music copy goes too.": "Salinan Gallery/Music-nya ikut terhapus.",
  "Language": "Bahasa",
  "Language: {name}": "Bahasa: {name}",
  "Largest": "Terbesar",
  "Later": "Nanti",
  "Light": "Terang",
  "Links go through the full lookup (playlists, subtitles, chapters and all). A direct mp4/m3u8 address skips the lookup, for anything already playing in front of you.": "Tautan melewati pemeriksaan penuh (daftar putar, subtitle, bab, semuanya). Alamat mp4/m3u8 langsung melewati pemeriksaan, untuk apa pun yang sedang diputar di hadapanmu.",
  "Liquid": "Cair",
  "MKV — plays on media players": "MKV — jalan di pemutar media",
  "MP4 remuxes the streams without re-encoding": "MP4 me-remux stream tanpa enkode ulang",
  "MP4 — plays on everything": "MP4 — jalan di semua perangkat",
  "MP4 — remux, plays everywhere": "MP4 — remux, jalan di mana saja",
  "Mark in": "Tandai awal",
  "Mark out": "Tandai akhir",
  "Mark segments as chapters": "Tandai segmen sebagai bab",
  "Media": "Media",
  "Minimize to tray": "Kecilkan ke tray",
  "More audio presets": "Preset audio lainnya",
  "Named switches for the options that come up most — no syntax to remember. They apply to downloads, and the network ones to probing too, so a restricted video can still be listed.": "Tombol bernama untuk opsi yang paling sering dipakai — tanpa sintaks untuk dihafal. Opsi ini berlaku untuk unduhan, dan yang jaringan juga untuk pengecekan, jadi video terbatas pun tetap bisa didaftar.",
  "Network": "Jaringan",
  "Next": "Lanjut",
  "No presets yet — save one from your settings above, or from the download panel.": "Belum ada preset — simpan satu dari pengaturan di atas, atau dari panel unduhan.",
  "None": "Tidak ada",
  "Nothing filed yet — a finished download lands here.": "Belum ada yang tersimpan — unduhan yang selesai mendarat di sini.",
  "Nothing in the queue. Downloads you start land here — finished ones stay put so you can open, share or delete them.": "Antrean kosong. Unduhan yang kamu mulai mendarat di sini — yang selesai tetap ada supaya bisa dibuka, dibagikan, atau dihapus.",
  "Nothing to save yet — change a download option first (Settings → Media / Network).": "Belum ada yang bisa disimpan — ubah salah satu opsi unduhan dulu (Pengaturan → Media / Jaringan).",
  "Off": "Mati",
  "Off — enable “raw yt-dlp arguments” in Settings → Advanced to edit them.": "Mati — aktifkan “argumen mentah yt-dlp” di Pengaturan → Lanjutan untuk mengeditnya.",
  "Off — everything in one folder": "Mati — semuanya dalam satu folder",
  "On this machine alone, in the app's own data folder, readable only by your user account. They never leave your devices.": "Hanya di perangkat ini, di folder data aplikasi, hanya bisa dibaca oleh akun penggunamu. Cookie tidak pernah meninggalkan perangkatmu.",
  "One per playlist or channel": "Satu per daftar putar atau kanal",
  "One per site": "Satu per situs",
  "Open": "Buka",
  "Open folder": "Buka folder",
  "Open in the browser": "Buka di browser",
  "Open the releases page": "Buka halaman rilis",
  "Parallel fragments": "Fragmen paralel",
  "Paste a video URL — any yt-dlp site, or a direct mp4/m3u8 link": "Tempel URL video — situs apa pun yang dikenal yt-dlp, atau tautan mp4/m3u8 langsung",
  "Paste any video link": "Tempel tautan video apa saja",
  "Path to cookies file": "Path ke berkas cookie",
  "Pause": "Jeda",
  "Pine & cream": "Pinus & krem",
  "Play": "Putar",
  "Playlist added to downloads": "Daftar putar masuk ke unduhan",
  "Playlist items to download": "Item daftar putar untuk diunduh",
  "Playlist items:": "Item daftar putar:",
  "Playlist limit": "Batas daftar putar",
  "Preferred container": "Kontainer pilihan",
  "Presets": "Preset",
  "Presets ": "Preset ",
  "Probe": "Cek",
  "Probe reads the page": "Cek membaca halamannya",
  "Progress, speed and a live receipt for everything you start.": "Progres, kecepatan, dan rincian hidup untuk semua yang kamu mulai.",
  "Quality:": "Kualitas:",
  "Questions live down here": "Pertanyaan ada di bawah sini",
  "Questions, answered": "Pertanyaan, dijawab",
  "Queue": "Antrean",
  "Queue all": "Antrekan semua",
  "Quit": "Keluar",
  "Quit completely ": "Keluar sepenuhnya ",
  "Quit suravidl": "Keluar dari suravidl",
  "Quit suravidl? Active downloads will be interrupted.": "Keluar dari suravidl? Unduhan yang berjalan akan terputus.",
  "Raw yt-dlp arguments": "Argumen mentah yt-dlp",
  "Read from the yt-dlp actually installed, so the list can never go stale. Click an option to add it to the raw arguments above.": "Dibaca dari yt-dlp yang benar-benar terpasang, jadi daftarnya tidak pernah basi. Klik opsi untuk menambahkannya ke argumen mentah di atas.",
  "Remove": "Hapus",
  "Remove downloaded copy": "Hapus salinan terunduh",
  "Remove segments (re-encodes cuts)": "Hapus segmen (memotong ulang adegan)",
  "Remove the downloaded yt-dlp copy? suravidl goes back to the copy bundled with the app (from the next start).": "Hapus salinan yt-dlp yang diunduh? suravidl kembali ke salinan bawaan aplikasi (mulai start berikutnya).",
  "Remove “{name}” from the list?": "Hapus “{name}” dari daftar?",
  "Restart & Install": "Mulai ulang & pasang",
  "Resume": "Lanjutkan",
  "Retries": "Percobaan ulang",
  "Retry": "Coba lagi",
  "START commits a take": "MULAI mengunduh pilihanmu",
  "START · best": "MULAI · terbaik",
  "START · {label}": "MULAI · {label}",
  "Save": "Simpan",
  "Save preset": "Simpan preset",
  "Save the current settings as a preset ": "Simpan setelan saat ini sebagai preset ",
  "Save these options as a preset…": "Simpan opsi ini sebagai preset…",
  "Scheme": "Skema",
  "Scheme: {name}": "Skema: {name}",
  "Select it above": "Pilih teks di atas",
  "Sent from your browser — pick the quality, then take it": "Dikirim dari browsermu — pilih kualitasnya, lalu ambil",
  "Settings": "Pengaturan",
  "Settings holds the rest": "Sisanya ada di Pengaturan",
  "Settings saved": "Pengaturan tersimpan",
  "Settings sections": "Bagian pengaturan",
  "Settings → General checks for a new release and installs it — Check now, then Get it. The browser extension updates itself through Mozilla once the new version clears review.": "Pengaturan → Umum memeriksa rilis baru dan memasangnya — Cek sekarang, lalu Ambil. Ekstensi browser memperbarui dirinya lewat Mozilla setelah versi baru lolos tinjauan.",
  "Share": "Bagikan",
  "Show": "Tampilkan",
  "Show all": "Tampilkan semua",
  "Show details": "Lihat detail",
  "Show folder": "Tampilkan folder",
  "Sign in to YouTube in your browser and export a cookies.txt, or read the cookies straight from a browser (close it first). On Android, use Import. Instagram sessions expire in hours — re-export when a download asks for a sign-in. Impersonation is for sites that fingerprint the browser; the desktop builds include it.": "Masuk ke YouTube di browser lalu ekspor cookies.txt, atau baca cookie langsung dari browser (tutup dulu browsernya). Di Android, pakai Impor. Sesi Instagram kedaluwarsa dalam hitungan jam — ekspor ulang saat unduhan meminta masuk. Peniruan untuk situs yang mem-fingerprint browser; build desktop menyertakannya.",
  "Signed-in sites — private videos, member areas — only serve files to a signed-in session. The extension passes the session details for exactly the stream you picked, nothing else, and Settings → Authentication shows what is held and clears it on ask.": "Situs yang butuh login — video privat, area anggota — hanya melayani berkas ke sesi yang sudah login. Ekstensi mengirim detail sesi hanya untuk stream yang kamu pilih, tidak yang lain, dan Pengaturan → Autentikasi menunjukkan apa yang disimpan serta menghapusnya saat diminta.",
  "Skip this version": "Lewati versi ini",
  "Some pages cannot hand a plain link over. Play it in your browser for a second: the extension (on desktop) or the browser offer right here catches the stream, and you pick the quality here before anything downloads.": "Sebagian halaman tidak bisa menyerahkan tautan langsungnya. Putar sebentar di browser: ekstensi (di desktop) atau tawaran browser di sini menangkap stream-nya, dan kamu pilih kualitasnya di sini sebelum apa pun diunduh.",
  "Source": "Sumber",
  "Speed limit": "Batas kecepatan",
  "SponsorBlock categories to remove": "Kategori SponsorBlock yang dihapus",
  "Stop and delete": "Hentikan & hapus",
  "Stop skipping": "Jangan lewati lagi",
  "Stop “{name}” and delete the partial file?": "Hentikan “{name}” dan hapus berkas sebagiannya?",
  "Subfolders": "Subfolder",
  "Subtitle languages": "Bahasa subtitle",
  "Subtitles": "Subtitle",
  "Subtitles:": "Subtitle:",
  "Tags": "Tag",
  "Take": "Ambil",
  "Test cookies": "Uji cookie",
  "That is the site, not the app: some pages publish only up to a certain quality, or as separate video and audio streams — suravidl merges separate streams automatically.": "Itu situsnya, bukan aplikasinya: sebagian halaman hanya menyediakan sampai kualitas tertentu, atau video dan audio terpisah — suravidl otomatis menggabungkan stream terpisah.",
  "The armed take rides down here. START begins the download; Studio opens the extra options.": "Pilihan yang aktif ada di sini. MULAI memulai unduhan; Studio membuka opsi tambahan.",
  "The deck fills up here": "Isinya muncul di sini",
  "The extension finds nothing, or says the app isn't running.": "Ekstensi tidak menemukan apa pun, atau bilang aplikasinya tidak berjalan.",
  "The folder shown at the bottom of the screen — press Open folder next to it. On a phone, finished downloads get Open and Share buttons instead; files land in Gallery (video) or Music (audio) under suravidl.": "Folder yang terlihat di bagian bawah layar — tekan Buka folder di sebelahnya. Di ponsel, unduhan yang selesai punya tombol Buka dan Bagikan; berkasnya masuk ke Gallery (video) atau Music (audio) di dalam suravidl.",
  "The literal “every feature” switch. Once it is on, the arguments field in the ": "Sakelar “semua fitur” yang sesungguhnya. Setelah menyala, kolom argumen di ",
  "The phone app's browser serves a few known ad networks empty, and some pages notice. In its second row there is an 'ads blocked / ads allowed' switch — flip it and reload. The off-site jump and pop-up guard keeps working either way.": "Browser aplikasi ponsel mengosongkan beberapa jaringan iklan yang dikenal, dan sebagian halaman menyadarinya. Di baris keduanya ada sakelar 'ads blocked / ads allowed' — ubah dan muat ulang. Penjaga lompatan situs dan pop-up tetap bekerja.",
  "The phone app's built-in browser refuses off-site jumps and pop-ups while you hunt for a stream — the page, and the find list, stay put. If a refused hop was one you meant, tap the note on screen to follow it anyway.": "Browser bawaan aplikasi ponsel menolak lompatan ke situs lain dan pop-up saat kamu mencari stream — halamannya, dan daftar temuannya, tetap di tempat. Kalau lompatan yang ditolak itu memang kamu maksud, ketuk catatan di layar untuk tetap mengikutinya.",
  "The queue": "Antrean",
  "The real formats, quality, codecs and subtitles — what the site actually offers.": "Format asli, kualitas, codec, dan subtitle — yang benar-benar disediakan situsnya.",
  "Theme: {name}": "Tema: {name}",
  "These apply to the next download only; your saved settings stay as they are. Save what you set here as a preset above, or manage bundles in Settings → Presets.": "Ini hanya berlaku untuk unduhan berikutnya; setelan tersimpanmu tidak berubah. Simpan yang kamu atur di sini sebagai preset di atas, atau kelola bundel di Pengaturan → Preset.",
  "This cannot be undone.": "Ini tidak bisa dibatalkan.",
  "This download only ": "Hanya unduhan ini ",
  "This step needs ffmpeg. Use “keep original” for audio-only, or install ffmpeg.": "Langkah ini membutuhkan ffmpeg. Pilih “pertahankan asli” untuk audio saja, atau pasang ffmpeg.",
  "This window is reporting itself as not visible to the browser engine, which pauses animations — closing and reopening the app usually clears it.": "Jendela ini melaporkan dirinya tidak terlihat oleh mesin browser, sehingga animasi dijeda — menutup dan membuka ulang aplikasi biasanya mengatasinya.",
  "Try again": "Coba lagi",
  "Two routes: sign in to the site in “Find a video on a page” — that session goes with the download — or import a cookies.txt exported from a desktop browser (encrypted on this device). Instagram sessions expire in hours — re-import when a download asks for a sign-in.": "Dua jalan: masuk ke situsnya di “Find a video on a page” — sesi itu ikut ke unduhan — atau impor cookies.txt dari browser desktop (terenkripsi di perangkat ini). Sesi Instagram kedaluwarsa dalam hitungan jam — impor ulang saat unduhan meminta masuk.",
  "Update": "Perbarui",
  "Update both sides first, and pair them once: the token from Settings → Authentication goes into the extension's Options. They find each other along a short row of nearby ports, so a busy port is fine. If the popup was open while the app started, press Check again.": "Perbarui keduanya dulu, dan pasangkan sekali: token dari Pengaturan → Autentikasi dimasukkan ke Options ekstensi. Keduanya saling mencari lewat sederet port terdekat, jadi port yang sedang dipakai tidak masalah. Kalau popup-nya terbuka saat aplikasi mulai, tekan Cek lagi.",
  "A download failed — how do I see why?": "Unduhan gagal — bagaimana cara melihat alasannya?",
  "Turn Verbose log on in the yt-dlp tab, let the job run again, then press View log: the last lines yt-dlp said are there, ready to copy. The log lives in memory only — it dies with the app.": "Nyalakan Verbose log di tab yt-dlp, jalankan lagi unduhannya, lalu tekan Lihat log: baris-baris terakhir dari yt-dlp ada di sana, siap disalin. Log hanya hidup di memori — ikut mati bersama aplikasi.",
  "Update now": "Perbarui sekarang",
  "Update to {v}": "Perbarui ke {v}",
  "Update yt-dlp": "Perbarui yt-dlp",
  "Update yt-dlp? The newest release is fetched and verified — packaged builds apply it on the next start.": "Perbarui yt-dlp? Rilis terbaru diambil dan diverifikasi — versi terpaket menerapkannya saat start berikutnya.",
  "Update “{name}”": "Perbarui “{name}”",
  "Updates": "Pembaruan",
  "Updates the downloader itself: a pip setup upgrades in place, and packaged builds fetch the newest release from PyPI (verified) and apply it on the next start. It is what knows the sites — the engine around it rarely changes. New jobs may wait a moment while it runs.": "Memperbarui pengunduh itu sendiri: pemasangan pip diperbarui di tempat, dan build paket mengambil rilis terbaru dari PyPI (terverifikasi) lalu menerapkannya saat mulai berikutnya. Dialah yang mengenali situs — engine di sekitarnya jarang berubah. Unduhan baru mungkin menunggu sebentar saat ini berjalan.",
  "Use cookies from Brave": "Pakai cookie dari Brave",
  "Use cookies from Chrome": "Pakai cookie dari Chrome",
  "Use cookies from Chromium": "Pakai cookie dari Chromium",
  "Use cookies from Edge": "Pakai cookie dari Edge",
  "Use cookies from Firefox": "Pakai cookie dari Firefox",
  "Use cookies from Opera": "Pakai cookie dari Opera",
  "Use cookies from Safari": "Pakai cookie dari Safari",
  "Use cookies from Vivaldi": "Pakai cookie dari Vivaldi",
  "Verbosity": "Tingkat log",
  "Verifying…": "Memverifikasi…",
  "Video only — no sound": "Video saja — tanpa suara",
  "What's new": "Yang baru",
  "Where are the cookies kept?": "Cookie-nya disimpan di mana?",
  "Where do my downloads go?": "Ke mana unduhanku pergi?",
  "Why does it use my browser's cookies?": "Kenapa memakai cookie browserku?",
  "Workaround: IP version": "Solusi sementara: versi IP",
  "Workaround: pause between requests": "Solusi sementara: jeda antarpermintaan",
  "Your system asks for reduced motion, and suravidl follows it — turn off “Reduce motion” (macOS: System Settings → Accessibility → Motion) to see animations.": "Sistemmu meminta gerakan dikurangi, dan suravidl mengikutinya — matikan “Reduce motion” (macOS: System Settings → Accessibility → Motion) untuk melihat animasi.",
  "a copy from PyPI is staged — removing cancels it": "salinan dari PyPI sudah disiapkan — menghapus akan membatalkannya",
  "a newer copy from PyPI is staged — removing deletes the downloaded copy and cancels the stage": "salinan baru dari PyPI sudah disiapkan — menghapus akan menghapus salinan unduhan dan membatalkan persiapan",
  "about {size} — the site's advertised sizes, added the way this pick works": "sekitar {size} — ukuran yang dicantumkan situs, dijumlahkan sesuai cara pilihan ini bekerja",
  "active for this download: {keys}": "aktif untuk unduhan ini: {keys}",
  "added {name} — save to keep it": "{name} ditambahkan — simpan untuk menyimpannya",
  "all {total}": "semua {total}",
  "all {total} · first {shown} listed": "semua {total} · {shown} pertama terdaftar",
  "and its Gallery/Music copy": "dan salinan Gallery/Music-nya",
  "and their Gallery/Music copies": "dan salinan Gallery/Music-nya",
  "app cache · empty": "cache aplikasi · kosong",
  "app cache · {size}": "cache aplikasi · {size}",
  "arm the take at best up to {label} ({fmt})": "pilih kualitas terbaik sampai {label} ({fmt})",
  "audio only": "audio saja",
  "audio preset: {name}": "preset audio: {name}",
  "audio track language": "bahasa trek audio",
  "audio {codec}": "audio {codec}",
  "audio · {label}": "audio · {label}",
  "auto": "otomatis",
  "best available": "terbaik yang tersedia",
  "blank = all · e.g. 1-10,15": "kosong = semua · mis. 1-10,15",
  "built-in": "bawaan",
  "cache cleared ({size})": "cache dibersihkan ({size})",
  "cache was already empty": "cache sudah kosong",
  "can't verify server certificates in this build — get the newest suravidl once and checks work from there · {when}": "tidak bisa memverifikasi sertifikat server di versi ini — ambil suravidl terbaru sekali dan pemeriksaan akan berfungsi · {when}",
  "cancel failed: {msg}": "gagal membatalkan: {msg}",
  "cancelled": "dibatalkan",
  "cannot reach the engine ({why}) — retrying every couple of seconds.": "tidak bisa menghubungi engine ({why}) — mencoba lagi tiap beberapa detik.",
  "checked {when}": "diperiksa {when}",
  "checking…": "memeriksa…",
  "clear what is armed for the next download": "hapus yang disiapkan untuk unduhan berikutnya",
  "cleared — using your settings": "dibersihkan — memakai pengaturanmu",
  "click one to clip from here": "klik salah satu untuk memotong dari sini",
  "clip ends at {v}": "klip berakhir di {v}",
  "clip starts at {v}": "klip mulai di {v}",
  "clip {start}": "klip {start}",
  "clip {start} → {end}": "klip {start} → {end}",
  "clip: {name}": "klip: {name}",
  "completed": "selesai",
  "cookies import failed": "impor cookie gagal",
  "cookies imported": "cookie terimpor",
  "copy failed": "gagal menyalin",
  "copy path": "salin path",
  "copy the whole message": "salin seluruh pesan",
  "could not apply: {msg}": "tidak bisa diterapkan: {msg}",
  "could not check for updates": "gagal memeriksa pembaruan",
  "could not clear the cache: {msg}": "gagal membersihkan cache: {msg}",
  "could not delete: {msg}": "gagal menghapus: {msg}",
  "could not fetch what's new": "gagal mengambil catatan baru",
  "could not forget: {msg}": "gagal melupakan: {msg}",
  "could not launch the installer: {msg}": "gagal menjalankan pemasang: {msg}",
  "could not load options: {msg}": "gagal memuat opsi: {msg}",
  "could not load presets ({err}) —": "gagal memuat preset ({err}) —",
  "could not load settings: {msg}": "gagal memuat pengaturan: {msg}",
  "could not load the subtitles": "gagal memuat subtitle",
  "could not minimize: {msg}": "gagal mengecilkan: {msg}",
  "could not open browser: {msg}": "gagal membuka browser: {msg}",
  "could not open: {msg}": "gagal membuka: {msg}",
  "could not queue those links: {msg}": "gagal mengantrekan tautan itu: {msg}",
  "could not read the archive: {msg}": "gagal membaca arsip: {msg}",
  "could not read the folder: {msg}": "gagal membaca folder: {msg}",
  "could not remove: {msg}": "gagal menghapus: {msg}",
  "could not save: {msg}": "gagal menyimpan: {msg}",
  "could not share: {msg}": "gagal membagikan: {msg}",
  "could not start download: {msg}": "gagal memulai unduhan: {msg}",
  "could not start the installer": "gagal menjalankan pemasang",
  "could not start the installer: {msg}": "gagal menjalankan pemasang: {msg}",
  "could not start the update: {msg}": "gagal memulai pembaruan: {msg}",
  "could not update: {msg}": "gagal memperbarui: {msg}",
  "country code to check availability from": "kode negara untuk mengecek ketersediaan",
  "country code, e.g. ID (blank = auto)": "kode negara, mis. ID (kosong = otomatis)",
  "default preset cleared — downloads use just your settings": "preset bawaan dihapus — unduhan memakai pengaturanmu saja",
  "default preset: “{name}” rides every new download": "preset bawaan: “{name}” ikut di setiap unduhan baru",
  "deleted 1 file": "1 berkas dihapus",
  "deleted 1 file · freed {free}": "1 berkas dihapus · {free} dibebaskan",
  "deleted {n} files": "{n} berkas dihapus",
  "deleted {n} files · freed {free}": "{n} berkas dihapus · {free} dibebaskan",
  "deleting…": "menghapus…",
  "do not embed metadata": "jangan sematkan metadata",
  "do not embed thumbnail": "jangan sematkan thumbnail",
  "download": "unduhan",
  "download finished — the file is in your downloads": "unduhan selesai — berkasnya ada di unduhanmu",
  "download it again anyway": "tetap unduh lagi",
  "download-archive entry to forget": "entri arsip-unduhan untuk dilupakan",
  "downloaded copy removed — bundled yt-dlp from the next start": "salinan unduhan dihapus — yt-dlp bawaan sejak start berikutnya",
  "downloaded from PyPI — removing falls back to the bundled copy on the next start": "diunduh dari PyPI — menghapus akan kembali ke salinan bawaan saat mulai berikutnya",
  "downloading": "mengunduh",
  "downloading the update in the background — watch Settings → Updates": "mengunduh pembaruan di latar belakang — pantau Pengaturan → Pembaruan",
  "downloading… {detail}": "mengunduh… {detail}",
  "downloads": "unduhan",
  "downloads · 1 file": "unduhan · 1 berkas",
  "downloads · {n} files": "unduhan · {n} berkas",
  "e.g. 2M (blank = unlimited)": "mis. 2M (kosong = tanpa batas)",
  "e.g. subs-en + metadata": "mis. subs-en + metadata",
  "embed in the video": "sematkan ke video",
  "embed metadata": "sematkan metadata",
  "embed metadata for this download": "sematkan metadata untuk unduhan ini",
  "embed thumbnail": "sematkan thumbnail",
  "embed thumbnail for this download": "sematkan thumbnail untuk unduhan ini",
  "engine {engine} · yt-dlp {dlp}": "engine {engine} · yt-dlp {dlp}",
  "error": "gagal",
  "error copied": "pesan galat disalin",
  "extract / convert to M4A (AAC)": "ekstrak / konversi ke M4A (AAC)",
  "extract / convert to MP3 at 192 kbps": "ekstrak / konversi ke MP3 192 kbps",
  "feed the deck a link — the probe fills these": "beri tautan ke dek — Cek yang mengisi ini",
  "file picker unavailable: {msg}": "pemilih berkas tidak tersedia: {msg}",
  "filed takes": "unduhan selesai",
  "fix the range": "perbaiki rentangnya",
  "for playlists, courses and channels": "untuk daftar putar, kursus, dan kanal",
  "forget": "lupakan",
  "forgotten 1 entry": "1 entri dilupakan",
  "forgotten {n} entries": "{n} entri dilupakan",
  "forgotten — that video can be downloaded again": "dilupakan — video itu bisa diunduh lagi",
  "freed {size}": "{size} dibebaskan",
  "from the app's folder? The Gallery/Music copies stay.": "dari folder aplikasi? Salinan Gallery/Music tetap ada.",
  "give it a name first": "beri nama dulu",
  "glossy · heavier blur": "mengkilap · blur lebih berat",
  "include item {n}": "sertakan item {n}",
  "interrupted": "terputus",
  "just now": "baru saja",
  "keep original": "pertahankan asli",
  "keep the original stream — no conversion, no ffmpeg needed": "pertahankan stream asli — tanpa konversi, tanpa ffmpeg",
  "languages, e.g. en, id": "bahasa, mis. en, id",
  "less": "lebih sedikit",
  "let suravidl install updates, then tap Install again": "izinkan suravidl memasang pembaruan, lalu ketuk Pasang lagi",
  "live stream — the download keeps recording until you cancel it": "siaran langsung — unduhan terus merekam sampai kamu membatalkannya",
  "load this job's URL and options into the Download tab": "muat URL dan opsi unduhan ini ke tab Unduh",
  "loaded the failed settings — change what you like, then start it": "pengaturan yang gagal dimuat — ubah sesukamu, lalu mulai",
  "loading…": "memuat…",
  "mark as chapters": "tandai sebagai bab",
  "matte · cheapest": "matte · paling ringan",
  "merging": "menggabungkan",
  "mm:ss or hh:mm:ss — for a 30-second highlight out of a 3-hour stream": "mm:ss atau hh:mm:ss — untuk sorotan 30 detik dari stream 3 jam",
  "more audio formats": "format audio lainnya",
  "more formats…": "format lainnya…",
  "must contain %(ext)s · example: ": "harus memuat %(ext)s · contoh: ",
  "next download: {what}": "unduhan berikutnya: {what}",
  "no answer": "tidak ada jawaban",
  "no domains": "tidak ada domain",
  "no downloaded files": "tidak ada berkas unduhan",
  "no extractor knows this page — open it in the browser, press play, then Scan for the stream": "halaman ini tidak dikenali — buka di browser, tekan play, lalu pakai Scan untuk menangkap stream-nya",
  "no formats found": "format tidak ditemukan",
  "no readout — see the message above": "tidak ada hasil — lihat pesan di atas",
  "none picked": "belum ada yang dipilih",
  "none — use my settings": "tidak ada — pakai pengaturanku",
  "not checked yet": "belum diperiksa",
  "not set": "belum diatur",
  "nothing archived yet": "belum ada yang diarsipkan",
  "nothing freed": "tidak ada yang dibebaskan",
  "nothing matches that search": "tidak ada yang cocok dengan pencarian itu",
  "nothing new to show": "tidak ada yang baru",
  "nothing to delete": "tidak ada yang bisa dihapus",
  "nothing to remove": "tidak ada yang perlu dihapus",
  "off": "mati",
  "open folder": "buka folder",
  "open the per-download patch bay": "buka panel opsi per unduhan",
  "opens a browser with a sniffer — press play, then Scan": "membuka browser dengan sniffer — tekan putar, lalu Pindai",
  "packaged build: fetches the newest yt-dlp from PyPI, verified — applies on next start": "versi terpaket: mengambil yt-dlp terbaru dari PyPI, terverifikasi — berlaku saat mulai berikutnya",
  "pair takes with the {lang} audio track": "pasangkan unduhan dengan trek audio {lang}",
  "paste a video link first": "tempel tautan video dulu",
  "paste an archive entry first": "tempel dulu entri arsipnya",
  "paste an entry to forget it": "tempel entri untuk melupakannya",
  "path copied": "path disalin",
  "path to cookies.txt (Netscape format)": "path ke cookies.txt (format Netscape)",
  "pause failed: {msg}": "gagal menjeda: {msg}",
  "paused": "dijeda",
  "per-site tweaks as ": "penyesuaian per situs sebagai ",
  "pick at least one item first": "pilih minimal satu item dulu",
  "pick items first": "pilih item dulu",
  "pick items on the deck, then START": "pilih item, lalu tekan MULAI",
  "playlist": "daftar putar",
  "preparing the video your browser sent…": "menyiapkan video yang dikirim browsermu…",
  "preset deleted": "preset dihapus",
  "preset name": "nama preset",
  "preset {name}": "preset {name}",
  "preset “{name}”": "preset “{name}”",
  "preset “{name}” applied — {n} option(s) for the next download": "preset “{name}” diterapkan — {n} opsi untuk unduhan berikutnya",
  "presets could not be loaded, so there is nothing to diff against — retry from Settings → Presets.": "preset tidak bisa dimuat, jadi tidak ada pembanding — coba lagi dari Pengaturan → Preset.",
  "probe failed": "gagal memeriksa",
  "probe failed: {msg}": "gagal memeriksa: {msg}",
  "probing…": "memeriksa…",
  "quality": "kualitas",
  "queued": "dalam antrean",
  "reading the source…": "membaca sumber…",
  "removal is set — the bundled copy takes over on the next start": "penghapusan sudah diatur — salinan bawaan menggantikan saat mulai berikutnya",
  "removal is set — the downloaded copy goes at the next start": "penghapusan sudah diatur — salinan unduhan hilang saat start berikutnya",
  "remove the segments": "hapus segmennya",
  "removed from the list": "dihapus dari daftar",
  "restarting to install…": "memulai ulang untuk memasang…",
  "resume failed: {msg}": "gagal melanjutkan: {msg}",
  "retry": "coba lagi",
  "retry failed: {msg}": "gagal mencoba lagi: {msg}",
  "save failed: {msg}": "gagal menyimpan: {msg}",
  "saved": "disimpan",
  "saved in the app's folder — use Open or Share on a finished download": "tersimpan di folder aplikasi — pakai Buka atau Bagikan pada unduhan yang selesai",
  "saved where you can open it — Gallery → suravidl (audio: Music → suravidl)": "tersimpan di tempat yang bisa kamu buka — Gallery → suravidl (audio: Music → suravidl)",
  "saved “{name}” with {n} option(s): {keys}": "“{name}” tersimpan dengan {n} opsi: {keys}",
  "saved “{name}” — {n} option(s)": "“{name}” tersimpan — {n} opsi",
  "saving…": "menyimpan…",
  "search yt-dlp options": "cari opsi yt-dlp",
  "search — e.g. proxy, subtitle, metadata, sleep": "cari — mis. proxy, subtitle, metadata, sleep",
  "seconds (0–30) · gentler on sites that rate-limit": "detik (0–30) · lebih lembut ke situs pembatas",
  "selected — press Save": "terpilih — tekan Simpan",
  "send it as: Authorization: Bearer <token>": "kirim sebagai: Authorization: Bearer <token>",
  "sent from your browser — pick a take": "dikirim dari browser — pilih satu",
  "set an option first — a preset needs at least one": "atur satu opsi dulu — preset butuh minimal satu",
  "sets {sets}": "menyetel {sets}",
  "shared link ready — pick a format": "tautan terkirim siap — pilih formatnya",
  "show entries": "tampilkan entri",
  "show every file this playlist downloaded": "tampilkan semua berkas yang diunduh daftar putar ini",
  "showing the last {shown} of {n}": "menampilkan {shown} terakhir dari {n}",
  "single file": "berkas tunggal",
  "size": "ukuran",
  "size unavailable": "ukuran tidak tersedia",
  "skip": "lewati",
  "skipped": "dilewati",
  "source readout": "bacaan sumber",
  "staged copy removed": "salinan tersiapkan dihapus",
  "status unavailable": "status tidak tersedia",
  "stop after N downloads · 0 = the whole list": "berhenti setelah N unduhan · 0 = seluruh daftar",
  "stopping…": "menghentikan…",
  "stored cookies deleted": "cookie tersimpan dihapus",
  "subtitle languages, comma separated": "bahasa subtitle, dipisah koma",
  "subtitles in {lang} (auto-generated) — click again to unpick": "subtitle {lang} (otomatis) — klik lagi untuk membatalkan",
  "subtitles in {lang} — click again to unpick": "subtitle {lang} — klik lagi untuk membatalkan",
  "subtitles: none picked": "subtitle: belum ada yang dipilih",
  "subtitles: {list}": "subtitle: {list}",
  "subtitles: {list} — not on this video": "subtitle: {list} — tidak ada di video ini",
  "suravidl {v} is available": "suravidl {v} tersedia",
  "suravidl {v} is available — you have {cur}": "suravidl {v} tersedia — kamu punya {cur}",
  "take": "pilihan",
  "take ready — set the deck, press START": "pilihan siap — atur opsi, tekan MULAI",
  "tap to collapse": "ketuk untuk menutup",
  "tap to show the whole message": "ketuk untuk menampilkan seluruh pesan",
  "test failed: {msg}": "pengujian gagal: {msg}",
  "testing…": "menguji…",
  "the app cache is already empty": "cache aplikasi sudah kosong",
  "the app's folder (reachable by file managers on this Android): {path}": "folder aplikasi (bisa dibuka pengelola berkas di Android ini): {path}",
  "the app's own folder (not browsable): {path}": "folder milik aplikasi (tidak bisa dijelajahi): {path}",
  "the brand's voice": "suara brand-nya",
  "the browser sent a video, but reading it failed": "browser mengirim video, tapi gagal membacanya",
  "the download failed": "unduhan gagal",
  "the download failed: {why}": "unduhan gagal: {why}",
  "the engine did not answer": "engine tidak menjawab",
  "the folder is empty": "foldernya kosong",
  "the house lamp": "lampu rumah ini",
  "the last step needs ffmpeg — audio “keep original” avoids the conversion": "langkah terakhir butuh ffmpeg — pilih audio “pertahankan asli” untuk menghindari konversi",
  "the secure connection could not be verified — a TLS-inspecting proxy can cause this": "koneksi aman tidak bisa diverifikasi — proxy yang memeriksa TLS bisa jadi penyebabnya",
  "the site does not advertise a size for this stream — the real size shows once the download starts": "situs tidak mencantumkan ukuran untuk stream ini — ukuran asli muncul saat unduhan dimulai",
  "the site is rate-limiting this address (429) — wait a bit, then try once more": "situs sedang membatasi permintaan dari alamat ini (429) — tunggu sebentar, lalu coba sekali lagi",
  "the site never answered in time — check the connection and retry": "situs tidak menjawab tepat waktu — periksa koneksi lalu coba lagi",
  "the site refused the request (403) — sign-in cookies or the Impersonate setting often fix this": "situs menolak permintaan (403) — cookie login atau pengaturan Impersonate biasanya mengatasi ini",
  "the site says this link does not exist (404) — check it was copied whole": "situs bilang tautan ini tidak ada (404) — pastikan tersalin utuh",
  "the site wants a signed-in session — load cookies in Settings → Authentication": "situsnya butuh sesi login — muat cookie di Pengaturan → Autentikasi",
  "the site's own choice of audio track": "trek audio pilihan situs",
  "the update download failed: {why}": "unduhan pembaruan gagal: {why}",
  "the update is downloaded and verified": "pembaruan sudah diunduh dan diverifikasi",
  "this file": "berkas ini",
  "this page has a player yt-dlp cannot read — press play there, then Scan": "halaman ini punya pemutar yang tidak bisa dibaca yt-dlp — tekan putar di sana, lalu Pindai",
  "type a range like 1-5,8": "ketik rentang seperti 1-5,8",
  "unknown": "tidak diketahui",
  "unknown reason": "alasan tidak diketahui",
  "up to date": "terbaru",
  "update check failed: {msg}": "pemeriksaan pembaruan gagal: {msg}",
  "update failed: {msg}": "pembaruan gagal: {msg}",
  "updating…": "memperbarui…",
  "use my settings": "pakai setelanku",
  "verifying the download…": "memverifikasi unduhan…",
  "video + audio": "video + audio",
  "video only": "video saja",
  "video only — no sound": "video saja — tanpa suara",
  "video only — no sound available": "video saja — audio tidak tersedia",
  "video {codec}": "video {codec}",
  "video {i}/{n}": "video {i}/{n}",
  "what a video-only take pairs when it adds sound": "audio yang dipasangkan saat pilihan video-saja diberi suara",
  "what changed in this version": "apa yang berubah di versi ini",
  "what the browser extension sends": "yang dikirim ekstensi browser",
  "when unticked, a video download gets the site’s audio added automatically": "saat tidak dicentang, unduhan video otomatis ditambahi audio dari situsnya",
  "whole video": "video penuh",
  "with the archive on, a video that was already downloaded is skipped — forget its entry (or turn the archive off) to fetch it again": "saat arsip menyala, video yang sudah pernah diunduh dilewati — lupakan entrinya (atau matikan arsip) untuk mengunduhnya lagi",
  "won't ask about {v} again": "tidak akan menanya soal {v} lagi",
  "write .srt files": "tulis berkas .srt",
  "write the fields above into this preset": "tulis isian di atas ke preset ini",
  "write the player's clock into the clip end": "tulis jam pemutar ke akhir klip",
  "write the player's clock into the clip start": "tulis jam pemutar ke awal klip",
  "you have {v} · {when}": "kamu punya {v} · {when}",
  "you're on the latest version ({v})": "kamu di versi terbaru ({v})",
  "your pick for this site last time — click to arm it as the take": "pilihanmu untuk situs ini terakhir kali — klik untuk memilihnya",
  "your saved presets are not gone, they just could not be read": "preset tersimpanmu tidak hilang, hanya tidak bisa dibaca",
  "yt-dlp already latest ({v})": "yt-dlp sudah terbaru ({v})",
  "yt-dlp args: {args}": "argumen yt-dlp: {args}",
  "yt-dlp arguments for this download ": "Argumen yt-dlp untuk unduhan ini ",
  "yt-dlp itself": "yt-dlp itu sendiri",
  "yt-dlp tab →": "tab yt-dlp →",
  "yt-dlp updated → {v}": "yt-dlp diperbarui → {v}",
  "yt-dlp {v} is staged — restart to use it": "yt-dlp {v} sudah disiapkan — mulai ulang untuk memakainya",
  "{base} · downloaded and verified": "{base} · terunduh dan terverifikasi",
  "{count} picked": "{count} dipilih",
  "{count} picked of {total}": "{count} dipilih dari {total}",
  "{d} days ago": "{d} hari lalu",
  "{h} hours ago": "{h} jam lalu",
  "{i} of {n}": "{i} dari {n}",
  "{keys} — this download only": "{keys} — hanya unduhan ini",
  "{k} options set below": "{k} opsi disiapkan di bawah",
  "{label} · last used": "{label} · terakhir dipakai",
  "{lang} (auto)": "{lang} (otomatis)",
  "{links} pasted{skipped} — only 20 fit in one batch": "{links} ditempel{skipped} — hanya 20 muat dalam satu batch",
  "{m} minutes ago": "{m} menit lalu",
  "{name} preset": "preset {name}",
  "{n} files": "{n} berkas",
  "{n} items": "{n} item",
  "{n} jobs hidden by this filter": "{n} unduhan disembunyikan oleh filter ini",
  "{n} links": "{n} tautan",
  "{n} links queued": "{n} tautan masuk antrean",
  "{n} matches": "{n} cocok",
  "{n} min": "{n} menit",
  "{n} options": "{n} opsi",
  "{n} queued · {k} skipped: {err}": "{n} masuk antrean · {k} dilewati: {err}",
  "{n} skipped — not links": "{n} dilewati — bukan tautan",
  "{n} videos": "{n} video",
  "{pct}% of {size}": "{pct}% dari {size}",
  "· 1 entry": "· 1 entri",
  "· empty": "· kosong",
  "· {n} entries": "· {n} entri",
  "— age-restricted / private videos": "— video dengan batas usia / privat",
  "— apply a preset —": "— pakai preset —",
  "— fills these fields from a saved bundle": "— mengisi kolom ini dari bundel tersimpan",
  "— keeps the download options that differ from the defaults (subtitles, SponsorBlock, embeds, template, network…)": "— menyimpan opsi unduhan yang berbeda dari bawaan (subtitle, SponsorBlock, sematan, templat, jaringan…)",
  "— pick one on the Download tab → “This download only”": "— pilih satu di tab Unduh → “Hanya unduhan ini”",
  "— raw args are on in Settings → Advanced": "— argumen mentah menyala di Pengaturan → Lanjutan",
  "— rides every new download": "— ikut di setiap unduhan baru",
  "“{name}” (no longer exists)": "“{name}” (sudah tidak ada)",
  "“{name}” updated — {n} option(s)": "“{name}” diperbarui — {n} opsi",
  "… {n} more — tick the listed ones, or type a range like 501-600": "… {n} lagi — centang yang terdaftar, atau ketik rentang seperti 501-600",
  "…). Click an option below to add it.": "…). Klik opsi di bawah untuk menambahkannya.",
  "Concurrent downloads: {n}": "Unduhan bersamaan: {n}",
  "a preset needs a name": "preset perlu nama",
  "Delete the stored cookies from this device?": "Hapus cookie tersimpan dari perangkat ini?",
  "Forget archive entry {entry}": "Lupakan entri arsip {entry}",
  "Delete preset “{name}”": "Hapus preset “{name}”",
  "socks5://127.0.0.1:1080 (blank = direct)": "socks5://127.0.0.1:1080 (kosong = langsung)",
  "probe ready — the formats are below": "cek selesai — formatnya di bawah",
  "Clip start time": "Waktu mulai klip",
  "start 1:30": "mulai 1:30",
  "end 2:45": "akhir 2:45",
  "Retry failed ({n})": "Coba ulang yang gagal ({n})",
  "Clear filed ({n})": "Bersihkan yang selesai ({n})",
  "Delete the {n} filed downloads?": "Hapus {n} unduhan yang selesai?",
  "Their Gallery/Music copies go too.": "Salinan Gallery/Music-nya ikut terhapus.",
  "retrying {n}": "mencoba ulang {n}",
  "View log": "Lihat log",
  "yt-dlp log": "log yt-dlp",
  "Refresh": "Muat ulang",
  "nothing logged yet — turn on Verbose log for the deep one": "belum ada catatan — nyalakan Verbose log untuk versi detailnya",
  "could not read the log: {msg}": "tidak bisa membaca log: {msg}"
} };
/* i18n-dicts:end */
let LANG = CFG.language === "id" ? "id" : "en";

function t(s, vars) {
  const dict = STRINGS[LANG] || null;
  let out = (dict && dict[s] != null) ? dict[s] : s;
  if (vars) {
    for (const k in vars) out = out.split("{" + k + "}").join(String(vars[k]));
  }
  return out;
}

/** Everything static in the page: text (data-i18n), titles, aria-labels and
 *  placeholders. One pass over what the markup declares, run at boot and on
 *  every language switch. */
function applyStaticI18n(root) {
  const scope = root || document;
  scope.querySelectorAll("[data-i18n]").forEach((n) => {
    n.textContent = t(n.dataset.i18n);
  });
  scope.querySelectorAll("[data-i18n-title]").forEach((n) => {
    n.title = t(n.dataset.i18nTitle);
  });
  scope.querySelectorAll("[data-i18n-aria]").forEach((n) => {
    n.setAttribute("aria-label", t(n.dataset.i18nAria));
  });
  scope.querySelectorAll("[data-i18n-ph]").forEach((n) => {
    n.placeholder = t(n.dataset.i18nPh);
  });
}

/** The document-level facts a language switch moves: the lang attribute
 *  (screen readers, hyphenation) and the window title. */
function applyLanguageChrome() {
  document.documentElement.lang = LANG;
  document.title = t("🐴 suravidl");
}

const ACTIVE = new Set(["queued", "downloading", "merging"]);
// v0.40.2 "the sieve": the queue's view filter. Filed and failed are exact
// sets; ANY other state counts as active — a state the sieve has not met
// yet must never vanish silently from the view that promises "in play".
const QUEUE_BUCKETS = {
  filed: ["completed"],
  error: ["error", "interrupted"],
};
let QFILTER = "all";   // session-only: a filter that survives a reload is a trap
let DESKTOP = false;
let APP_INFO = null;   // /app/info payload (desktop capabilities)

/* ---------- drawn icons (the sprite lives in index.html) ---------- */
/** `ico("play")` → a span the CSS sizes; one stroke system, no emoji. */
function ico(name) {
  const s = document.createElement("span");
  s.className = "ico";
  s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-' +
    name + '"/></svg>';
  return s;
}

/* ---------- the human voice of an engine error ---------- */
/** yt-dlp explains failures in its own dialect ("ERROR: unable to download
 *  video data: HTTP Error 403: Forbidden"). The first line a person reads
 *  says what it MEANS; the raw text stays one tap away (v0.37.0).
 *
 *  The engine leads when it has a structured verdict: detail.unsupported
 *  means "this site needs the sniffer" and must never be re-guessed into
 *  some other story. (v0.38.6: a bare `age` alternative matched "page",
 *  so every unsupported-URL line read as a sign-in wall — the summary and
 *  the details disagreed, and the summary was wrong.) */
function humanErr(s, detail, url) {
  s = String(s == null ? "" : s);
  if (detail && detail.unsupported)
    return "no extractor knows this page — open it in the browser, press play, then Scan for the stream";
  if (/HTTP Error 404|not found|does not exist/i.test(s)) {
    // Reddit's /s/ "share" links resolve only inside a browser (a session
    // flow a downloader never gets); fetching one returns the 404 that
    // this arm used to misread as "you copied it wrong" (2026-10-10).
    if (/reddit\.com\/[^\s"']*\/s\//i.test(String(url || "") + " " + s))
      return "Reddit share links (“/s/” shortcuts) only open in a browser — open it once, copy the full address (it becomes /r/…/comments/…), and paste that";
    return "the site says this link does not exist (404) — check it was copied whole";
  }
  if (/HTTP Error 403|forbidden/i.test(s))
    return "the site refused the request (403) — sign-in cookies or the Impersonate setting often fix this";
  if (/HTTP Error 429|too many requests/i.test(s))
    return "the site is rate-limiting this address (429) — wait a bit, then try once more";
  if (/unsupported url|no (suitable )?extractor/i.test(s))
    return "no extractor knows this page — open it in the browser, press play, then Scan for the stream";
  if (/\bsign[ -]?in\b|\blog[ -]?in\b|login required|private video|\bage\b/i.test(s))
    return "the site wants a signed-in session — load cookies in Settings → Authentication";
  if (/encoder not found/i.test(s))
    return "the phone's ffmpeg can't convert subtitles for this container — set Subtitles to \u201csidecar\u201d in Settings or use the MKV container, then retry";
  if (/timed? ?out|timeout/i.test(s))
    return "the site never answered in time — check the connection and retry";
  if (/certificate|SSL/i.test(s))
    return "the secure connection could not be verified — a TLS-inspecting proxy can cause this";
  if (/ffmpeg/i.test(s))
    return "the last step needs ffmpeg — audio “keep original” avoids the conversion";
  const line = s.split("\n")[0];
  return line.length > 140 ? line.slice(0, 140) + "…" : (line || "the download failed");
}

/* ---------- the scope strip: instruments that read the source ---------- */
/** data-state drives the lamps and the reading colours (style.css). */
let SCOPE_LAST = null;   // the last call, replayable for a language switch
function setScopes(state, read) {
  const strip = $("scopeStrip");
  if (!strip) return;
  SCOPE_LAST = { state: state, read: read };
  strip.dataset.state = state;
  if (read) {
    if (read.src != null) $("scopeSrc").textContent = read.src;
    if (read.fmt != null) $("scopeFmt").textContent = read.fmt;
    if (read.size != null) $("scopeSize").textContent = read.size;
    // the say line is our own words (the rest is site data) — translated at
    // the one place it is painted, so a stored call re-translates on replay
    if (read.say != null) $("scopeSay").textContent = t(read.say);
  }
}

/** Per-site livery: the probe card takes a tint from the source (v0.37.0). */
function liveryOf(extractor) {
  const e = String(extractor || "").toLowerCase();
  for (const key of ["youtube", "twitter", "vimeo", "instagram", "tiktok"]) {
    if (e.indexOf(key) !== -1) return key;
  }
  return "";
}

/* ---------- the transport: arm a take, then commit it (v0.37.0) ---------- */
/** Choosing and downloading used to be the same click on eleven controls.
 *  The deck now works like a room: picks ARM a take (one at a time — the
 *  newest arm replaces the old), the START lamp commits it, and a commit
 *  spends the take (one-shot, like the patch bay below). */
let TAKE = { fmt: null, preset: null, label: "" };
// v0.40.1 — the audio dial: "" = the site's own pick, else a language code
let AUDIO_LANG = "";
// v0.40.4 — the marks: the media element the player modal holds, if any
let PLAY_NODE = null;
let QUALITY_EST = {};   // v0.40.5: per-probe sizes, keyed by quality chip
let LAST_PROBE = null;  // {url, info} — the on-deck readout, for relabelling
let LAST_FAIL = null;   // {msg, detail} — the last probe failure, same reason
let LAST_JOBS = [];     // the last queue snapshot (the bins rail replays it)

function armTake(pick, label, btn) {
  if (!pick) return;
  if (TAKE.fmt === pick || TAKE.preset === pick) {
    // tapping the armed pick again disarms it
    TAKE.fmt = null;
    TAKE.preset = null;
    TAKE.label = "";
  } else if (pick.indexOf("audio-") === 0) {
    TAKE.fmt = null;
    TAKE.preset = pick;
    TAKE.label = label || pick.replace(/^audio-/, "");
  } else {
    TAKE.preset = null;
    TAKE.fmt = pick;
    TAKE.label = label || pick;
  }
  renderTake();
}

function renderTake() {
  const say = $("takeSay");
  const lamp = $("bestBtn");
  if (!say || !lamp) return;
  const armed = TAKE.fmt || TAKE.preset;
  say.textContent = armed
    ? (TAKE.preset ? t("audio · {label}", { label: t(TAKE.label) })
                   : t(TAKE.label))
    : t("best available");
  say.classList.toggle("set", !!armed);
  lamp.textContent = armed
    ? t("START · {label}", { label: t(TAKE.label || "take") })
    : t("START · best");
  // the armed pick stays lit wherever it lives (chips, format rows, audio) —
  // and ONLY the armed one: a commit spends the take and every light goes out
  document.querySelectorAll("[data-pick]").forEach((b) => {
    b.classList.toggle("picked", b.dataset.pick === armed);
  });
}

async function commitTake(btn) {
  btn = btn || $("bestBtn");
  const url = $("url").value.trim();
  const ok = playlistMode()
    ? await startJob(url, null, TAKE.preset, true, btn)
    : await startJob(url, TAKE.fmt, TAKE.preset, false, btn);
  if (ok) {
    TAKE.fmt = null;
    TAKE.preset = null;
    TAKE.label = "";
    renderTake();
  }
}

/* ---------- toasts ---------- */
/** Keep the toast lane clear of the functional strips that are ACTUALLY
 *  docked at the bottom right now — the transport once it pins (it is
 *  sticky, so at the top of a page it is not down there), the settings
 *  Save strip once it docks. Nothing docked: the lane falls back — just
 *  above the tab bar on a phone, the corner on desktop. Measured at every
 *  width (v0.39.13: the desktop's fixed lifts — 86px, 150px on Settings —
 *  left the lane hovering "like it's floating"). */
function syncToastLane() {
  const host = $("toasts");
  if (!host) return;
  const vh = window.innerHeight;
  let top = Infinity;
  for (const el of document.querySelectorAll(".transport, #panel-settings .modal-foot")) {
    const r = el.getBoundingClientRect();
    if (r.height < 8 || r.top > vh || r.bottom < 0) continue;   // hidden or gone
    if (r.bottom < vh - 140) continue;                          // in the flow, not docked
    top = Math.min(top, r.top);
  }
  if (top === Infinity) host.style.removeProperty("--toast-lift");
  else host.style.setProperty("--toast-lift", Math.round(vh - (top - 8)) + "px");
}
window.addEventListener("resize", syncToastLane, { passive: true });
// capture: the phone panels can be their own scroll containers
// the audit: measuring the docked furniture on every scroll tick forces
// synchronous layout per frame — the lane wakes at most once per frame
let toastLaneRaf = 0;
window.addEventListener("scroll", () => {
  if (toastLaneRaf || !$("toasts").children.length) return;
  toastLaneRaf = requestAnimationFrame(() => {
    toastLaneRaf = 0;
    syncToastLane();
  });
}, { passive: true, capture: true });

/** msg, kind ("ok" | "bad" | "info"), and optionally:
 *  - sticky:  do not time out; it stays until dismissed (an update notice)
 *  - actions: [{label, prime, onClick}] — real choices on the toast itself.
 *  The buttons stop the click from bubbling, so tapping one runs it and
 *  dismisses the toast, while a plain toast still dismisses on any tap. */
function toast(msg, kind = "ok", opts) {
  const box = el("div", "toast " + kind);
  box.append(el("span", "dot"));
  box.append(el("span", "tmsg", msg));
  const actions = opts && opts.actions;
  if (actions && actions.length) {
    const row = el("div", "toactions");
    for (const a of actions) {
      const b = el("button", "ghost-sm" + (a.prime ? " prime" : ""), a.label);
      b.onclick = (ev) => {
        ev.stopPropagation();
        dismiss(box);
        try { if (a.onClick) a.onClick(); } catch (_) { /* a choice must not throw */ }
      };
      row.append(b);
    }
    box.append(row);
  } else {
    box.onclick = () => dismiss(box);
  }
  syncToastLane();
  $("toasts").append(box);
  if (!(opts && opts.sticky)) setTimeout(() => dismiss(box), 4200);
  return box;
}
/** The motion clock. Under prefers-reduced-motion the CSS snaps in 1ms, so
 *  a timer that exists only to cover a transition must not outlive it (the
 *  audit: invisible overlays kept intercepting pointer events after a
 *  "reduced" close). */
function motionMs(ms) {
  try {
    return window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : ms;
  } catch (e) { return ms; }
}
function dismiss(t) {
  if (!t.parentNode) return;
  t.classList.add("leaving");
  setTimeout(() => t.remove(), motionMs(260));
}

/* ---------- modal transitions ---------- */
/** Everything inside `m` that can hold focus, visible ones only. */
function modalFocusables(m) {
  return [...m.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
    .filter((el) => !el.disabled && el.offsetParent !== null);
}
function openModal(m) {
  clearTimeout(m._closeTimer);
  // a dialog is a room: focus moves in, Tab stays in, focus comes home when
  // it closes (v0.40.10 audit — aria-modal promised this and the code let
  // Tab wander into the page behind the overlay)
  m._returnFocus = document.activeElement;
  m.classList.remove("hidden", "closing");
  const first = modalFocusables(m)[0];
  if (first) first.focus();
  if (!m._trap) {
    m._trap = (e) => {
      if (e.key !== "Tab") return;
      const open = [...document.querySelectorAll(".overlay:not(.hidden)")];
      if (open[open.length - 1] !== m) return;   // only the top card traps
      const f = modalFocusables(m);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      } else if (!m.contains(document.activeElement)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", m._trap);
  }
}
function closeModal(m) {
  m.classList.add("closing");
  m._closeTimer = setTimeout(() => {
    m.classList.remove("closing");
    m.classList.add("hidden");
    if (m._trap) {
      document.removeEventListener("keydown", m._trap);
      m._trap = null;
    }
    const back = m._returnFocus;
    m._returnFocus = null;
    if (back && document.contains(back)) back.focus();
  }, motionMs(170));
}

/* ---------- clipboard ---------- */
/** Copy to the clipboard wherever the page runs.
 *
 *  navigator.clipboard wants a secure origin and a live user gesture, and
 *  some WebViews refuse it outright; a throwaway textarea + execCommand
 *  still works there. One helper, so every copy in the page behaves alike
 *  (the copy-path button and the Copy button on a failed row). */
async function copyText(t) {
  t = String(t == null ? "" : t);
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(t);
      return true;
    }
  } catch (_) { /* blocked: try the old way */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = t;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    ta.style.pointerEvents = "none";
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  } catch (_) {
    return false;
  }
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
function applyTheme(theme, glass, accent) {
  const r = document.documentElement;
  const changed = (theme && r.dataset.theme !== theme)
    || (glass && r.dataset.glass !== glass)
    || (accent && r.dataset.accent !== accent);
  if (theme) r.dataset.theme = theme;
  if (glass) r.dataset.glass = glass;
  if (accent) r.dataset.accent = accent;
  // A theme switch repaints every surface. Without this the big cards eased
  // their colours over 350ms while every button, pill and input inside them
  // snapped instantly — the UI looked torn for a third of a second (motion
  // review). Scoped to a class that lives only for the switch, so hover
  // feedback keeps its own much faster timing the rest of the time.
  if (changed) {
    clearTimeout(applyTheme._t);
    r.classList.add("theming");
    applyTheme._t = setTimeout(() => r.classList.remove("theming"),
                               motionMs(460));
  }
}
function markSwatches(values) {
  // the visual .on and the announced pressed state move together (v0.44.x
  // audit: screen readers heard three identical buttons, no selection)
  document.querySelectorAll("#themeSwatches .swatch").forEach((b) => {
    const on = b.dataset.theme === values.theme;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
  document.querySelectorAll("#glassSwatches .swatch").forEach((b) => {
    const on = b.dataset.glass === values.glass;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
  document.querySelectorAll("#schemeSwatches .swatch").forEach((b) => {
    const on = b.dataset.accent === values.accent;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

/* ---------- the motion note (v0.38.7) ----------
   Two system-level switches can hold every animation still in this page:
   the system asking for reduced motion (we follow it — that is the point),
   or WebKit pausing transitions because the page reports itself hidden.
   Name whichever one is in force right here, where appearance is chosen,
   instead of leaving a still app unexplained. */
function paintMotionNote() {
  const note = $("motionNote");
  if (!note) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduce.matches) {
    note.textContent = t("Your system asks for reduced motion, and suravidl follows it — turn off “Reduce motion” (macOS: System Settings → Accessibility → Motion) to see animations.");
    note.hidden = false;
  } else if (document.visibilityState === "hidden") {
    note.textContent = t("This window is reporting itself as not visible to the browser engine, which pauses animations — closing and reopening the app usually clears it.");
    note.hidden = false;
  } else {
    note.hidden = true;
  }
}
function wireMotionNote() {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduce.addEventListener) reduce.addEventListener("change", paintMotionNote);
  document.addEventListener("visibilitychange", paintMotionNote);
  paintMotionNote();
}

let CURRENT = { theme: CFG.theme || "dark", glass: CFG.glass || "frosted",
                accent: CFG.accent || "amber" };
let SETTINGS_SNAPSHOT = null;   // last /settings payload (used by the preset diff)
let wnVersion = null;   // the version the open what's-new card belongs to

async function setAppearance(patch, label) {
  try {
    const s = await api("/settings", { method: "POST", body: JSON.stringify(patch) });
    CURRENT = { theme: s.theme, glass: s.glass, accent: s.accent };
    applyTheme(s.theme, s.glass, s.accent);
    markSwatches(CURRENT);
    toast(label, "info");
  } catch (e) {
    toast(t("could not apply: {msg}", { msg: e.message }), "bad");
  }
}

/* ---------- language (v0.44.0) ----------
   The switch rides the appearance controls: it saves through /settings (so
   it persists exactly like theme/glass/accent), and it lands everywhere at
   once — static text through applyStaticI18n, every dynamic surface by
   re-reading its own state. */
async function setLanguage(lang) {
  try {
    const s = await api("/settings", { method: "POST",
                                       body: JSON.stringify({ language: lang }) });
    LANG = s.language === "id" ? "id" : "en";
    applyLanguageChrome();
    relabelUI();
    toast(t("Language: {name}",
            { name: s.language === "id" ? "Indonesia" : "English" }), "info");
  } catch (e) {
    toast(t("could not apply: {msg}", { msg: e.message }), "bad");
    const sel = $("setLang");
    if (sel) sel.value = LANG;
  }
}

/** Re-render every surface that carries state on screen. Zero-build i18n has
 *  no reactive layer; this is the honest equivalent — each surface re-reads
 *  its own state (stored at render time) and paints anew. */
function relabelUI() {
  applyStaticI18n();
  applyLanguageChrome();
  renderWhere(CFG.downloadDir);
  renderTake();
  renderBatchRow();
  renderPlaylistState();
  renderOvCount();
  renderOvPresetInfo();
  renderOvPresetActions();
  renderOvPresets();
  renderPresetList();
  renderUpdateRow();
  loadVersions();
  if (OPTIONS) renderOptions($("optionsSearch").value);
  if (LAST_PROBE) renderProbe(LAST_PROBE.url, LAST_PROBE.info);
  else if (LAST_FAIL) showProbeFailure(LAST_FAIL.msg, LAST_FAIL.detail,
                                       $("url").value.trim());
  else if (SCOPE_LAST) setScopes(SCOPE_LAST.state, SCOPE_LAST.read);
  renderBins(LAST_JOBS);
  forceQueueRepaint();
  const pd = $("probeDetails");
  if (pd && !pd.classList.contains("hidden")) {
    pd.textContent = $("probeMsg").classList.contains("hidden")
      ? t("Show details") : t("Hide details");
  }
  if (refreshStorageInfo) refreshStorageInfo();
  const fm = $("folderModal");
  if (fm && !fm.classList.contains("hidden")) openFolderSheet();
  if (TOUR_ON) tourShow();
  const fb = $("faqList");
  if (fb && fb.childElementCount) buildFaqList();
  paintMotionNote();
  wireToken();   // the token chip and its title ride the language too (audit)
  if ($("archiveCount") && $("archiveCount").textContent.trim()) loadArchive();
  if ($("logModal") && !$("logModal").classList.contains("hidden")) loadLog();
}

/** A rebuilt row is a repainted row: stamping every live row stale makes the
 *  next poll rebuild each one through jobRow() — the one place a row's text
 *  is decided (v0.40.2's sig compare is the trigger, no new mechanism). */
function forceQueueRepaint() {
  document.querySelectorAll("#jobs .job").forEach((row) => { row.dataset.sig = ""; });
  refreshJobs();
}



/* ---------- probe ---------- */
let PROBE_SEQ = 0;

async function doProbe() {
  const url = $("url").value.trim();
  if (!url) return;
  const seq = ++PROBE_SEQ;      // two probes in flight: the newest one wins
  // a previous failure's red clears before this probe starts speaking
  $("probeMsg").className = "msg muted";
  $("probeMsg").textContent = t("probing…");
  $("probeMsg").classList.remove("hidden");
  $("probeSay").classList.add("hidden");
  $("probeSay").textContent = "";
  if ($("probeLive")) $("probeLive").textContent = "";
  $("probeDetails").classList.add("hidden");
  setScopes("scan", { say: "reading the source…" });
  $("probeBtn").classList.add("busy");
  try {
    const info = await api("/probe", {
      method: "POST", body: JSON.stringify({ url }),
    });
    if (seq !== PROBE_SEQ) return;
    renderProbe(url, info);
    $("probeMsg").textContent = "";
    if ($("probeLive")) {
      // sighted users see the table; this is the audible half (v0.44.x audit)
      $("probeLive").textContent = t("probe ready — the formats are below");
    }
    $("browserOffer").classList.add("hidden");   // it probed fine: no browser needed
  } catch (e) {
    if (seq !== PROBE_SEQ) return;
    showProbeFailure(e.message, e.detail, url);
  } finally {
    if (seq === PROBE_SEQ) $("probeBtn").classList.remove("busy");
  }
}

/** A failed probe, said the one way — extracted so a language switch can say
 *  it again in the new language (raw text and human line both). */
function showProbeFailure(msg, detail, url) {
  LAST_FAIL = { msg: msg, detail: detail };
  LAST_PROBE = null;
  // the engine explains a failure (it owns the "sign-in wall" judgement and
  // says so in its own words) — the UI does not second-guess it
  $("probeMsg").textContent = t("probe failed: {msg}", { msg: msg });
  // an error is tally rose and machine text is mono; this line was the
  // one failure in the app that used to whisper in grey
  $("probeMsg").className = "msg bad mono";
  // the human line leads; the raw engine text sits behind "Show details"
  // (v0.37.0: yt-dlp's dialect was the FIRST thing a newcomer had to read)
  $("probeMsg").classList.add("hidden");
  $("probeSay").textContent = t(humanErr(msg, detail));
  $("probeSay").className = "msg bad";
  $("probeSay").classList.remove("hidden");
  $("probeDetails").textContent = t("Show details");
  $("probeDetails").classList.remove("hidden");
  setScopes("bad", { say: "no readout — see the message above" });
  offerBrowser({ message: msg, detail: detail }, url);
  $("probeCard").classList.add("hidden");
  // the onboarding line is for an EMPTY deck; reviving it under a failure
  // made the page argue with itself (v0.40.10 audit)
  $("dlEmpty").classList.add("hidden");
  // chips from the *previous* probe still carry its URL: leaving them armed
  // downloads a link the user has already replaced (v0.21.1 audit)
  $("qualityRow").classList.add("hidden");
  $("qualityBtns").replaceChildren();
  $("playlistRow").classList.add("hidden");
  PLAYLIST = null;
  PLAYLIST_NONE = false;
}

/* "No extractor for this page" is not a dead end on a host that has the in-app
   browser: the engine's structured answer carries `unsupported`, and that
   browser is exactly what it was built for (v0.24.2, M3). The offer is hidden
   again on the next probe — never left pointing at a URL the user replaced. */
function offerBrowser(err, url) {
  const row = $("browserOffer");
  if (!row) return;
  const detail = (err && err.detail) || {};
  const asked = detail.unsupported === true ||
    /unsupported url/i.test((err && err.message) || "");
  if (!asked || !window.AndroidHost || !window.AndroidHost.openBrowser) {
    row.classList.add("hidden");
    return;
  }
  row.classList.remove("hidden");
  $("browserOfferBtn").onclick = () => {
    try { window.AndroidHost.openBrowser(url); } catch (_) { }
  };
}

function fmtQuality(f) {
  if (f.height) return f.height + "p" + (f.fps && f.fps > 30 ? f.fps : "");
  if (f.abr) return f.abr + " kbps";
  return f.format_note || f.resolution || "";
}

/* ---------- format rows: read the codec soup, and never hand out silence --- */
const CODEC_NAMES = {
  avc1: "H.264", avc3: "H.264", hev1: "HEVC", hvc1: "HEVC", vp09: "VP9",
  vp9: "VP9", vp8: "VP8", av01: "AV1", mp4a: "AAC", opus: "Opus",
  vorbis: "Vorbis", ac3: "AC-3", ec3: "E-AC-3", flac: "FLAC",
};

const codecName = (c) => {
  if (!c || c === "none") return null;
  const base = String(c).split(".")[0].toLowerCase();
  return CODEC_NAMES[base] || c;
};

const hasVideo = (f) => !!f.vcodec && f.vcodec !== "none";
const hasAudio = (f) => !!f.acodec && f.acodec !== "none";

function fmtCodecs(f) {
  const parts = [f.ext];
  const v = codecName(f.vcodec), a = codecName(f.acodec);
  if (v) parts.push(t("video {codec}", { codec: v }));
  if (a) parts.push(t("audio {codec}", { codec: a }));
  return parts.join(" · ");
}

/** What the stream contains — the thing the old table made you guess.
 *
 *  A video-only row says what the download will DO with it: by default the
 *  app pairs the site's separate audio back in, or leaves the video silent
 *  when the "no sound" choice is ticked — and a site with no separate audio
 *  is said out loud instead of promising a sound track that does not exist.
 *  (2026-09-27 report: "'video only - sound added latter' is ambiguous for
 *  inexperienced user".) */
function fmtKind(f, hasSeparateAudio) {
  const v = hasVideo(f), a = hasAudio(f);
  if (v && a) return { label: t("video + audio"), cls: "k-both" };
  if (v) {
    if (!hasSeparateAudio) {
      return { label: t("video only — no sound available"), cls: "k-video" };
    }
    return { label: soundChoiceLabel(), cls: "k-video", sound: true };
  }
  if (a) return { label: t("audio only"), cls: "k-audio" };
  // a plain file (direct link): the site told us nothing about its tracks
  return { label: t("single file"), cls: "k-audio" };
}

/** The two states of a video-only row's label, read live from the checkbox
 *  so ticking it re-labels the whole table (refreshSoundLabels). The
 *  unticked state IS the default and stays unannotated: "video only — sound
 *  included" on every row read as noise (2026-09-27: "only show 'video
 *  only — no sound' if the checklist is checked"). */
function soundChoiceLabel() {
  const off = $("noSound") && $("noSound").checked;
  return off ? t("video only — no sound") : t("video only");
}

/** The "no sound" tick re-labels the rows it applies to, in place. Which
 *  rows those are is baked in at render time ([data-sound]): a row that
 *  never had separate audio says so and must not be re-labelled. */
function refreshSoundLabels() {
  for (const cell of document.querySelectorAll("#formats .fmt-kind[data-sound]")) {
    cell.textContent = soundChoiceLabel();
  }
}

/** v0.40.1 "the dial": multi-language sites publish one audio format per
 *  language (dubs). Collect the languages the probe actually found. */
function audioLangs(info) {
  const seen = new Map();
  for (const f of (info.formats || [])) {
    if (!f.format_id || hasVideo(f) || !hasAudio(f) || !f.language) continue;
    seen.set(String(f.language), true);
  }
  return [...seen.keys()].sort();
}

/** The chooser offers only real languages — "auto" (the site's own pick)
 *  first — and hides itself when there is nothing to choose. A pick the new
 *  video does not carry is dropped back to auto. */
function renderAudioLangRow(info) {
  const row = $("audioLangRow");
  const box = $("audioLangChips");
  if (!row || !box) return;
  const langs = audioLangs(info);
  if (langs.length < 2) {
    row.classList.add("hidden");
    box.innerHTML = "";
    AUDIO_LANG = "";
    return;
  }
  if (AUDIO_LANG && !langs.includes(AUDIO_LANG)) {
    AUDIO_LANG = "";             // gone from this video — back to auto
  }
  row.classList.remove("hidden");
  box.innerHTML = "";
  for (const val of ["", ...langs]) {
    const on = AUDIO_LANG === val;
    const btn = el("button", "btn sm" + (on ? " pick" : ""),
                   val === "" ? t("auto") : val);
    btn.type = "button";
    btn.setAttribute("aria-pressed", on ? "true" : "false");
    btn.title = val === ""
      ? t("the site's own choice of audio track")
      : t("pair takes with the {lang} audio track", { lang: val });
    btn.onclick = () => {
      AUDIO_LANG = val;
      renderAudioLangRow(info);
    };
    box.append(btn);
  }
}

/** Picking a video-only stream must not produce a silent file: pair it with
 *  the site's separate audio track when one exists (yt-dlp merges both with
 *  ffmpeg) — unless the user ticked "no sound", which is exactly the
 *  instruction not to (2026-09-27). Direct-link files have no separate
 *  audio, so they stay as-is. v0.40.1: with the audio dial set, the pair
 *  asks for that language first and keeps the plain pair as the second
 *  alternative, so a video whose dub list changed under us still lands. */
function fmtSpec(f, hasSeparateAudio) {
  if (!(hasSeparateAudio && hasVideo(f) && !hasAudio(f)
        && !$("noSound").checked)) {
    return f.format_id;
  }
  const lang = String(AUDIO_LANG || "").replace(/[^A-Za-z0-9-]/g, "");
  if (!lang) return `${f.format_id}+bestaudio/best`;
  return `${f.format_id}+bestaudio[language=${lang}]/${f.format_id}+bestaudio/best`;
}

function sizeCell(f) {
  const td = el("td", "fmt-s");
  const b = f.filesize || f.filesize_approx;
  if (b) {
    td.textContent = humanBytes(b);
  } else {
    td.textContent = t("unknown");
    td.classList.add("muted");
    const why = t("the site does not advertise a size for this stream — the real size shows once the download starts");
    td.title = why;                    // desktops hover
    td.onclick = () => toast(why);     // phones tap
  }
  return td;
}

/** Sites announce the same stream twice (DASH + HLS, one without a size).
 *  Keep one row per real choice, preferring the copy that knows its size.
 *  v0.40.1: a dub is a real choice — the language is part of the identity,
 *  or two languages would collapse into one row. */
function dedupeFormats(list) {
  const best = new Map();
  for (const f of list) {
    const key = [f.height || f.abr || 0, f.ext, f.vcodec, f.acodec,
                 f.fps || 0, f.format_note || "", f.language || ""].join("|");
    const prev = best.get(key);
    if (!prev) { best.set(key, f); continue; }
    const size = (x) => x.filesize || x.filesize_approx || 0;
    if (size(f) > 0 && size(prev) === 0) best.set(key, f);
  }
  return [...best.values()];
}

/** h:mm:ss (or m:ss) — the format the clip fields and yt-dlp both take. */
function clock(seconds) {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  const mm = String(m).padStart(2, "0"), ss = String(s % 60).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

/** Subtitle chips: the languages THIS site offers for THIS video — click to
 *  toggle one in or out of the wish list, and every picked one stays lit
 *  (2026-09-27: "use highlights for the chosen language; I can't unclick the
 *  one I accidentally click"). The list opens with the languages a person is
 *  actually after — the device's own, then English — and the rest is one tap
 *  away; fourteen chips used to be a wall with Abkhazian at the front. */
let SUBS_EXPANDED = false;

/** The languages picked so far, in the override field's own spelling. */
function pickedSubs() {
  const field = $("ovSubLangs");
  return field
    ? field.value.split(",").map((s) => s.trim()).filter(Boolean)
    : [];
}

function renderSubsChips(info) {
  const box = $("subsChips");
  if (!box) return;
  box.replaceChildren();
  const manual = Object.keys(info.subtitles || {});
  const auto = Object.keys(info.automatic_captions || {});
  const all = [...new Set([...manual, ...auto])];
  const device = String(navigator.language || "").split("-")[0].toLowerCase();
  const rank = (l) => {
    const k = String(l).toLowerCase();
    return k === device ? 0 : (k === "en" || k.startsWith("en-")) ? 1 : 2;
  };
  all.sort((a, b) => rank(a) - rank(b));   // stable: the site's order survives
  $("subsRow").classList.toggle("hidden", !all.length);
  if (!all.length) return;
  const CAP = 14;

  const sync = () => {
    const picked = pickedSubs();
    for (const chip of box.querySelectorAll("button.chip[data-lang]")) {
      const on = picked.includes(chip.dataset.lang);
      chip.classList.toggle("on", on);
      chip.setAttribute("aria-pressed", on);
    }
  };
  const toggle = (lang) => {
    const have = pickedSubs();
    const next = have.includes(lang)
      ? have.filter((x) => x !== lang)
      : [...have, lang];
    $("ovSubLangs").value = next.join(", ");
    if (next.length && !$("ovSubs").value) $("ovSubs").value = "sidecar";
    if (typeof renderOvCount === "function") renderOvCount();
    sync();
    toast(next.length ? t("subtitles: {list}", { list: next.join(", ") })
                       : t("subtitles: none picked"));
  };

  for (const lang of (SUBS_EXPANDED ? all : all.slice(0, CAP))) {
    const isAuto = !manual.includes(lang);
    const chip = el("button", "chip",
                    isAuto ? t("{lang} (auto)", { lang: lang }) : lang);
    chip.type = "button";
    chip.dataset.lang = lang;
    chip.title = isAuto
      ? t("subtitles in {lang} (auto-generated) — click again to unpick", { lang: lang })
      : t("subtitles in {lang} — click again to unpick", { lang: lang });
    chip.onclick = () => toggle(lang);
    box.append(chip);
  }
  if (all.length > CAP) {
    const more = el("button", "chip more",
      SUBS_EXPANDED ? t("less") : t("+{n} more", { n: all.length - CAP }));
    more.type = "button";
    more.onclick = () => { SUBS_EXPANDED = !SUBS_EXPANDED; renderSubsChips(info); };
    box.append(more);
  }
  sync();
}

/** The wish list is per-download and the site is per-video: a language picked
 *  on the last video must not ride into one that does not offer it — the
 *  leftover pick is how "the engine refuses when the language isn't
 *  available" happened (2026-09-27). Prune against THIS probe, and say what
 *  went. A site that reports no subtitles at all is not ours to clear. */
function syncSubLangsWithProbe(info) {
  const field = $("ovSubLangs");
  if (!field || !field.value.trim()) return;
  const available = [...Object.keys(info.subtitles || {}),
                     ...Object.keys(info.automatic_captions || {})];
  if (!available.length) return;
  const gone = pickedSubs().filter((l) => !available.includes(l));
  if (!gone.length) return;
  field.value = pickedSubs().filter((l) => available.includes(l)).join(", ");
  if (typeof renderOvCount === "function") renderOvCount();
  toast(t("subtitles: {list} — not on this video", { list: gone.join(", ") }));
}

/** Chapters: one click fills the clip start (and end) so a long video can be
 *  clipped at a chapter boundary instead of typing times from memory. */
function renderChapterChips(info) {
  const box = $("chapterChips");
  box.replaceChildren();
  const chapters = (info.chapters || []).slice(0, 20);
  $("chapterRow").classList.toggle("hidden", !chapters.length);
  for (const ch of chapters) {
    if (ch.start_time == null) continue;
    const start = clock(ch.start_time);
    const chip = el("button", "chip", ch.title || start);
    chip.type = "button";
    chip.title = ch.end_time != null
      ? t("clip {start} → {end}", { start: start, end: clock(ch.end_time) })
      : t("clip {start}", { start: start });
    chip.onclick = () => {
      $("ovClipStart").value = start;
      $("ovClipEnd").value = ch.end_time != null ? clock(ch.end_time) : "";
      if (typeof renderOvCount === "function") renderOvCount();
      toast(t("clip: {name}", { name: ch.title || start }));
    };
    box.append(chip);
  }
}

function renderProbe(url, info) {
  LAST_PROBE = { url: url, info: info };
  LAST_FAIL = null;
  $("probeCard").classList.remove("hidden");
  $("dlEmpty").classList.add("hidden");
  $("probeTitle").textContent = info.title || url;
  // "0 min" is not a duration: round() alone said a 40-second clip was zero
  // minutes long (polish pass)
  const dur = info.duration
    ? " · " + (info.duration < 60
               ? t("<1 min")
               : t("{n} min", { n: Math.round(info.duration / 60) })) : "";
  $("probeMeta").textContent = (info.extractor || "") + dur;
  // the probe lands on the scope strip — source, formats, largest (v0.37.0)
  $("probeCard").dataset.livery = liveryOf(info.extractor || "");
  const scopeFmts = (info.formats || []).filter((f) => f.ext && f.format_id);
  const biggest = Math.max(0, ...scopeFmts.map(
    (f) => f.filesize || f.filesize_approx || 0));
  setScopes("live", {
    src: String(info.extractor || (info.playlist ? "playlist" : "direct")).slice(0, 22),
    fmt: info.playlist ? t("{n} items", { n: info.count || 0 })
                       : String(scopeFmts.length),
    size: biggest ? humanBytes(biggest) : "—",
    say: "take ready — set the deck, press START",
  });

  // the probe has always carried these three; the UI now shows them
  const live = info.is_live === true || info.live_status === "is_live";
  $("liveRow").classList.toggle("hidden", !live);
  SUBS_EXPANDED = false;              // every probe starts folded
  renderSubsChips(info);
  syncSubLangsWithProbe(info);        // a pick this video lacks goes now
  renderChapterChips(info);

  const tb = $("formats").querySelector("tbody");
  tb.innerHTML = "";

  if (info.playlist) {
    $("playlistRow").classList.remove("hidden");
    $("qualityRow").classList.add("hidden");
    $("soundRow").classList.add("hidden");
    $("probeMeta").textContent =
      (info.count ? t("{n} videos", { n: info.count }) : t("playlist")) +
      (info.extractor ? " · " + info.extractor : "");
    const entries = info.entries || [];
    PLAYLIST = { count: info.count || entries.length, shown: entries.length };
    PLAYLIST_NONE = false;
    setScopes("live", {
      fmt: t("{n} items", { n: info.count || entries.length }),
      say: "pick items on the deck, then START",
    });
    for (const [i, e] of entries.entries()) {
      const tr = el("tr", "enter");
      // capped lower than a full stagger: a table that takes a quarter second
      // to finish arriving reads as slow
      if (motionMs(150) > 0) tr.style.animationDelay = Math.min(i * 30, 150) + "ms";
      const n = e.index || i + 1;
      const pick = el("td", "fmt-q");
      const box = el("input", "plpick");
      box.type = "checkbox";
      box.dataset.index = String(n);
      box.title = t("include item {n}", { n: n });
      box.onchange = () => syncPlaylistPicks();
      // the number half of the cell picks too: a phone should not have to
      // hit a 14px box (v0.40.10 audit)
      pick.onclick = (e) => {
        if (e.target === box) return;
        box.checked = !box.checked;
        box.onchange();
      };
      pick.append(el("span", "plnum", String(n)), box);
      tr.append(
        pick,
        el("td", "fmt-c", e.title || e.url || "—"),
        el("td", "fmt-s",
           e.duration ? t("{n} min", { n: Math.round(e.duration / 60) }) : "—"),
      );
      tb.append(tr);
    }
    if (info.count && entries.length < info.count) {
      const tr = el("tr");
      tr.append(el("td", "", ""),
                el("td", "muted",
                   t("… {n} more — tick the listed ones, or type a range like 501-600",
                     { n: info.count - entries.length })),
                el("td"));
      tb.append(tr);
    }
    renderAudioLangRow({});
    syncPlaylistPicks(false);
    return;
  }

  $("playlistRow").classList.add("hidden");
  PLAYLIST = null;
  PLAYLIST_NONE = false;
  QUALITY_EST = info.quality_estimates || {};
  renderQualityRow(url, info.site_quality);
  renderAudioLangRow(info);
  const usable = (info.formats || []).filter((f) => f.ext && f.format_id);
  // a video-only pick only makes sense to pair with audio when the site
  // actually publishes a separate audio stream (YouTube does, a plain .mp4 doesn't)
  const separateAudio = usable.some((f) => !hasVideo(f) && hasAudio(f));
  const fmts = dedupeFormats(usable)
    .sort((a, b) => (b.height || b.abr || 0) - (a.height || a.abr || 0));

  for (const [i, f] of fmts.entries()) {
    const tr = el("tr", "enter");
    // capped lower than a full stagger: a table that takes a quarter second
    // to finish arriving reads as slow
    if (motionMs(150) > 0) tr.style.animationDelay = Math.min(i * 30, 150) + "ms";
    const kind = fmtKind(f, separateAudio);
    const cell = el("td", "fmt-c");
    cell.append(el("div", "", fmtCodecs(f) || "—"));
    const kindEl = el("div", "fmt-kind " + kind.cls, kind.label);
    // the rows the "no sound" tick re-labels carry a mark; a row that never
    // had separate audio says so and must not be re-labelled
    if (kind.sound) kindEl.dataset.sound = "1";
    cell.append(kindEl);
    if (f.language) {
      // v0.40.1: with dubs listed separately, a row must say which one it is
      const langEl = el("div", "fmt-lang muted small", String(f.language));
      langEl.title = t("audio track language");
      cell.append(langEl);
    }
    tr.append(
      el("td", "fmt-q", fmtQuality(f) || "—"),
      cell,
      sizeCell(f),
    );
    const td = el("td");
    const btn = el("button", "get", t("Take"));
    btn.dataset.pick = fmtSpec(f, separateAudio);
    // v0.40.1: read the dial when the Take is clicked, not when the table
    // was drawn — a pick frozen at render time ignores a later language
    btn.onclick = () => armTake(fmtSpec(f, separateAudio),
                                fmtQuality(f) || "this file", btn);
    td.append(btn);
    tr.append(td);
    tb.append(tr);
  }
  // the "no sound" choice shows whenever there is a video row to explain
  // (the playlist branch above hid it again)
  const anyVideo = fmts.some(hasVideo);
  $("soundRow").classList.toggle("hidden", !anyVideo);
  if (!fmts.length) {
    const tr = el("tr");
    tr.append(el("td", "muted", t("no formats found")));
    tb.append(tr);
  }
}

/* ---------- jobs ---------- */
/** One-click quality picks for the probed video: the engine owns the format
 *  expressions (see QUALITY_PRESETS) so every shell offers the same list. */
function renderQualityRow(url, remembered) {
  const row = $("qualityRow");
  const box = $("qualityBtns");
  if (!row || !box) return;
  box.innerHTML = "";
  const list = OV.qualities || [];
  if (!list.length) {
    row.classList.add("hidden");
    return;
  }
  for (const q of list) {
    // what you picked for this site last time is marked, not applied: the
    // click is still yours (M20). No chip glows like the lamp before it is
    // armed — "best" included (v0.38.3 audit #4: an unclicked chip read as
    // a second START button).
    const last = remembered && q.key === remembered;
    const btn = el("button", "btn sm" + (last ? " pick" : ""),
      last ? t("{label} · last used", { label: q.label }) : q.label);
    const est = QUALITY_EST[q.key];
    if (est) {
      // v0.40.5: what this pick will weigh — the site's own advertised
      // sizes, added the way the pick works (engine-side, per probe)
      const size = el("span", "qsize", " ~" + humanBytes(est));
      size.title = t("about {size} — the site's advertised sizes, added the way this pick works",
                     { size: humanBytes(est) });
      btn.append(size);
    }
    btn.dataset.pick = q.fmt;
    btn.title = last
      ? t("your pick for this site last time — click to arm it as the take")
      : t("arm the take at best up to {label} ({fmt})",
          { label: q.label, fmt: q.fmt });
    btn.onclick = () => armTake(q.fmt, q.label, btn);
    box.append(btn);
  }
  row.classList.remove("hidden");
}

/** How many jobs are in flight — shown on the Queue tab. */
function renderQueueBadge(jobs) {
  const badge = $("queueCount");
  if (!badge) return;
  const active = (jobs || []).filter((j) =>
    ["queued", "downloading", "merging"].includes(j.status)).length;
  const was = !badge.classList.contains("hidden");
  badge.textContent = active > 9 ? "9+" : String(active);
  badge.classList.toggle("hidden", !active);
  if (active && !was) {
    // it appears: a quick scale-in, so a started download never just pops a
    // number into the corner (v0.42.1)
    badge.classList.remove("badge-in");
    void badge.offsetWidth;
    badge.classList.add("badge-in");
  }
}

function playlistMode() {
  return !$("playlistRow").classList.contains("hidden");
}

/* --- picking playlist items -------------------------------------------------
   The range field is what the engine is sent (blank = every item). The pick
   list edits the part of the playlist it shows; the field keeps anything the
   list cannot represent, so a typed range is never silently narrowed
   (v0.21.1 audit: "1-600" on a 500-entry probe became "1-500"). */

// what the playlist on screen really holds, and whether "None" was pressed
// (blank means *everything* to the engine, so "none" needs its own state)
let PLAYLIST = null;
let PLAYLIST_NONE = false;

/** "1-5,8" → {1,2,3,4,5,8}; null when it is not a range at all (blank = all). */
function parseItemRange(text) {
  const out = new Set();
  if (!text) return null;
  for (const part of text.split(",")) {
    const s = part.trim();
    if (!s) continue;
    const m = s.match(/^(\d+)\s*-\s*(\d+)$/);
    if (m) {
      const a = Number(m[1]);
      const b = Number(m[2]);
      if (a < 1 || b < a || b - a > 5000) return null;
      for (let i = a; i <= b; i++) out.add(i);
    } else if (/^\d+$/.test(s)) {
      if (Number(s) < 1) return null;
      out.add(Number(s));
    } else {
      return null;
    }
  }
  return out;
}

function pickedBoxes() {
  return Array.from(document.querySelectorAll("#formats .plpick"));
}

/** The picked items, in the syntax the field and the engine speak. */
function selectedPlaylistItems() {
  return pickedBoxes()
    .filter((b) => b.checked)
    .map((b) => Number(b.dataset.index))
    .sort((a, b) => a - b)
    .join(",");
}

function playlistFieldText() {
  return (($("playlistItems") || {}).value || "").trim();
}

/** One place decides what the pick label and the button say. */
function renderPlaylistState() {
  const label = $("plCount");
  const btn = $("playlistBtn");
  if (!btn) return;
  const boxes = pickedBoxes();
  const shown = boxes.length;
  const total = (PLAYLIST && PLAYLIST.count) || shown;
  const text = playlistFieldText();
  const want = text ? parseItemRange(text) : null;
  const junk = text && want === null;
  const none = PLAYLIST_NONE && !text;
  const count = want ? want.size : 0;
  if (boxes.some((b) => b.checked)) PLAYLIST_NONE = false;
  if (label) {
    label.textContent = junk ? t("type a range like 1-5,8")
      : none ? t("none picked")
      : text ? (count <= total
                ? t("{count} picked of {total}", { count: count, total: total })
                : t("{count} picked", { count: count }))
      : (shown < total
         ? t("all {total} · first {shown} listed", { total: total, shown: shown })
         : t("all {total}", { total: total }));
  }
  btn.disabled = Boolean(junk || none);
  btn.textContent = junk ? t("fix the range")
    : none ? t("pick items first")
    : text ? t("Download {count} picked", { count: count }) : t("Download playlist");
}

function syncPlaylistPicks(fromUser = true) {
  // A fresh probe lands here too — and "nothing ticked yet" is not the same
  // as "the user un-ticked everything": the first wants the whole playlist
  // (blank field, "Download playlist"), the second wants the refusal. Only a
  // human call may arm the trap (2026-10-02 report: fresh probes said
  // "none picked" with a dead start button).
  const boxes = pickedBoxes();
  const shown = new Set(boxes.map((b) => Number(b.dataset.index)));
  const text = playlistFieldText();
  const want = text ? parseItemRange(text) : null;
  // boxes -> field, but only for indices the list can show: a range reaching
  // past the listed entries stays exactly as typed
  const representable = text ? (want !== null &&
    [...want].every((i) => shown.has(i))) : true;
  if (representable) {
    const value = selectedPlaylistItems();
    if ($("playlistItems").value !== value) $("playlistItems").value = value;
    // unchecking the last box has to mean NOTHING, never "all": an empty
    // field is the engine's word for the whole playlist, so arm the same
    // refusal the None button uses (UI review — this was the trap v0.21.2
    // closed for None, still open on the manual path)
    if (fromUser && boxes.length > 0 && !boxes.some((b) => b.checked)) PLAYLIST_NONE = true;
  }
  renderPlaylistState();
}

/** A typed range ticks the matching boxes back; junk is shown, not hidden. */
function checkboxFromRange() {
  const text = playlistFieldText();
  const want = text ? parseItemRange(text) : null;
  if (text && want === null) { renderPlaylistState(); return; }
  PLAYLIST_NONE = false;
  for (const b of pickedBoxes()) {
    b.checked = want === null ? false : want.has(Number(b.dataset.index));
  }
  syncPlaylistPicks();
}

function pickAll(checked) {
  const boxes = pickedBoxes();
  for (const b of boxes) b.checked = checked;
  // "All" means the listed items; "None" means nothing at all — it must never
  // fall back to the blank field, which the engine reads as the whole playlist
  $("playlistItems").value = checked ? selectedPlaylistItems() : "";
  PLAYLIST_NONE = !checked && boxes.length > 0;
  renderPlaylistState();
}

async function startJob(url, fmt, preset, playlist, triggerBtn) {
  if (playlist && PLAYLIST_NONE && !playlistFieldText()) {
    toast(t("pick at least one item first"), "bad");
    return false;
  }
  if (!url) {
    toast(t("paste a video link first"), "bad");
    return false;
  }
  // A start can take most of a second (SQLite lock, a busy worker), and a
  // button that does not move invites a second and third tap — which queued
  // the same video twice (motion review). Disable it for the round-trip.
  if (triggerBtn) {
    triggerBtn.disabled = true;
    triggerBtn.classList.add("busy");
  }
  try {
    const body = { url };
    // a job off a browser handoff reuses the page's captured headers — they
    // live in the engine, keyed by the handoff, and never pass through here
    if (HANDOFF && url === HANDOFF.url) body.handoff_id = HANDOFF.id;
    if (fmt) body.fmt = fmt;
    // the audio intent only applies when no explicit format was picked
    // (yt-dlp refuses fmt + preset together)
    const audio = fmt ? null : (preset || OV.preset);
    if (audio) body.preset = audio;
    if (playlist) body.playlist_items = playlistFieldText();
    let ov = readOv();
    // the "no sound" tick rides every start from this card — a format chip,
    // "best quality", or the whole playlist: no_audio is the engine's key
    // for "do not pair this video with the site's audio" (2026-09-27)
    if ($("noSound").checked) ov = { ...(ov || {}), no_audio: true };
    if (ov) body.overrides = ov;
    // say what rode — and what a format pick silently replaced: jobs used to
    // report a bare "Added to downloads" either way (v0.35.0)
    const ovK = ov ? Object.keys(ov).length : 0;
    const note = (fmt && OV.preset)
      ? t(" — “{name}” skipped: your format pick replaces it",
          { name: OV.name || OV.preset })
      : (OV.name && (body.preset === OV.preset || ovK)
        ? t(" — with preset “{name}”", { name: OV.name })
        : (ovK ? (ovK === 1 ? t(" — with 1 option set below")
                            : t(" — with {n} options set below", { n: ovK }))
          : (TAKE.label ? t(" — {label}", { label: t(TAKE.label) }) : "")));
    await api("/jobs", { method: "POST", body: JSON.stringify(body) });
    // the block says "this download only" — so it is spent on this download
    // (v0.21.1 audit: it used to stick to every job for the rest of the session)
    clearOv();
    PLAYLIST_NONE = false;
    toast((playlist ? t("Playlist added to downloads")
                    : t("Added to downloads")) + note, "info");
    refreshJobs();
    return true;
  } catch (e) {
    toast(t("could not start download: {msg}", { msg: e.message }), "bad");
    return false;
  } finally {
    if (triggerBtn) {
      triggerBtn.disabled = false;
      triggerBtn.classList.remove("busy");
    }
  }
}

/* --- "This download only": a patch over the saved settings ---------------- */

// the audio intent of an applied preset (fmt and preset are exclusive in yt-dlp)
// plus its full patch: the block only shows a few of the options a preset may
// carry, so the rest must ride along instead of being lost on apply
// OV.name remembers WHICH preset is applied, so the block can show what it
// carries and offer to update it (v0.34.0)
const OV = { preset: null, name: null, patch: {}, defaults: null, perJobKeys: null };

/** The block's values as a patch — only what the user actually set.
 *  A field the user emptied or unticked *removes* the preset's value too:
 *  otherwise the form says "use my settings" while the download does not
 *  (v0.21.1 audit). */
function readOv() {
  const patch = { ...(OV.patch || {}) };
  const subs = $("ovSubs").value;
  if (subs) {
    patch.subtitles_mode = subs;
    const langs = $("ovSubLangs").value.trim();
    delete patch.subtitles_langs;          // no field, no claim
    if (langs) patch.subtitles_langs = langs;
  } else {
    delete patch.subtitles_mode;
    delete patch.subtitles_langs;
  }
  const sb = $("ovSb").value;
  if (sb) patch.sponsorblock_mode = sb; else delete patch.sponsorblock_mode;
  // three-state: "" = use my settings, "on"/"off" = a claim about this job.
  // A checkbox could only express "on", so switching a global embed off for
  // one download was impossible (v0.21.2 audit).
  const meta = $("ovMeta").value;
  if (meta === "on") patch.embed_metadata = true;
  else if (meta === "off") patch.embed_metadata = false;
  else delete patch.embed_metadata;
  const thumb = $("ovThumb").value;
  if (thumb === "on") patch.embed_thumbnail = true;
  else if (thumb === "off") patch.embed_thumbnail = false;
  else delete patch.embed_thumbnail;
  const raw = $("ovRaw").value.trim();
  if (raw) patch.raw_args = raw; else delete patch.raw_args;
  // clip: both times or none — half a range is not a range
  const clipStart = $("ovClipStart").value.trim();
  const clipEnd = $("ovClipEnd").value.trim();
  if (clipStart && clipEnd) patch.download_sections = `${clipStart}-${clipEnd}`;
  else delete patch.download_sections;
  const container = $("ovContainer").value;
  if (container) patch.video_container = container;
  else delete patch.video_container;
  if ($("ovArchive").value === "ignore") patch.archive_ignore = true;
  else delete patch.archive_ignore;
  return Object.keys(patch).length ? patch : null;
}

function clearOv() {
  OV.preset = null;
  OV.name = null;
  OV.patch = {};
  $("ovSubs").value = "";
  $("ovSubLangs").value = "";
  $("ovSb").value = "";
  $("ovMeta").value = "";
  $("ovThumb").value = "";
  $("ovRaw").value = "";
  $("ovClipStart").value = "";
  $("ovClipEnd").value = "";
  $("ovContainer").value = "";
  $("ovArchive").value = "";
  $("ovPreset").value = "";
  $("ovSaveRow").classList.add("hidden");
  $("ovSaveMsg").classList.add("hidden");
  $("ovSaveName").value = "";
  renderOvCount();
  renderOvPresetInfo();
  renderOvPresetActions();
}

/** 300+ rows must not become 300 tab stops: the catalogue owns ONE, and the
 *  arrow keys move inside it (the standard roving-tabindex pattern). Enter or
 *  Space picks, exactly as a click does. Without this the whole yt-dlp option
 *  browser was mouse-only (motion review). */
function makeOptionRowReachable(row, activate) {
  row.tabIndex = -1;
  row.setAttribute("role", "button");
  row.addEventListener("focus", () => {
    const list = row.closest(".optlist");
    if (!list) return;
    list.querySelectorAll('.optrow[tabindex="0"]')
      .forEach((r) => { r.tabIndex = -1; });
    row.tabIndex = 0;
  });
  row.addEventListener("keydown", (e) => {
    const list = row.closest(".optlist");
    if (!list) return;
    const rows = [...list.querySelectorAll(".optrow")];
    const i = rows.indexOf(row);
    if (e.key === "ArrowDown" && i >= 0 && i < rows.length - 1) {
      e.preventDefault();
      rows[i + 1].focus();
    } else if (e.key === "ArrowUp" && i > 0) {
      e.preventDefault();
      rows[i - 1].focus();
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      const target = e.key === "Home" ? rows[0] : rows[rows.length - 1];
      if (target) target.focus();
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      activate();
    }
  });
}

/** The single tab stop for the option list: focusing it lands on the first
 *  row, so Tab from the search box can reach the catalogue at all. */
function initOptionListKeyboard() {
  const list = $("optionsList");
  if (!list || list.tabIndex >= 0) return;
  list.tabIndex = 0;
  list.addEventListener("focus", () => {
    if (document.activeElement === list) {
      const first = list.querySelector(".optrow");
      if (first) first.focus();
    }
  });
}

/** The little "N options" chip on the collapsed summary. */
function renderOvCount() {
  const patch = readOv();
  const n = (patch ? Object.keys(patch).length : 0) + (OV.preset ? 1 : 0);
  // the same count, echoed on the card where the downloads actually start:
  // an armed preset used to be visible only in the collapsed block below the
  // formats table — nowhere near "Download best quality" (v0.35.0)
  const bar = $("armedBar");
  const txt = $("armedText");
  if (!n) {
    bar.classList.remove("armed-open");
    txt.textContent = "";
  } else {
    const entry = OV.name
      ? (PRESETS || []).find((p) => p.name === OV.name) : null;
    const k = patch ? Object.keys(patch).length : 0;
    const what = entry
      ? "“" + entry.name + "”" + (entry.description ? " — " + entry.description : "")
      : OV.name ? "“" + OV.name + "”"
        : (k === 1 ? t("1 option set below")
                   : t("{k} options set below", { k: k }));
    txt.textContent = t("next download: {what}", { what: what });
    bar.classList.add("armed-open");
  }
  const chip = $("ovCount");
  if (!n) {
    chip.classList.add("hidden");
    chip.textContent = "";
    chip.removeAttribute("title");
    return;
  }
  const parts = [];
  if (OV.preset) parts.push(OV.preset.replace(/^(audio|video)-/, ""));
  if (patch) parts.push(Object.keys(patch).length === 1
    ? t("1 option") : t("{n} options", { n: Object.keys(patch).length }));
  chip.textContent = parts.join(" · ");
  // name them on hover/for screen readers: the chip says how many, but the
  // question people actually have is WHICH — a leftover clip or subtitle
  // filter from a preset used to be invisible until the download was wrong
  // (motion review)
  const keys = patch ? Object.keys(patch) : [];
  chip.title = [OV.preset ? t("preset {name}", { name: OV.preset }) : "", ...keys]
    .filter(Boolean).join(", ");
  chip.setAttribute("aria-label", chip.title
    ? t("active for this download: {keys}", { keys: chip.title }) : "");
  chip.classList.remove("hidden");
}

/** Apply a preset's patch to the block (and remember its audio intent). */
function applyOvPreset() {
  const name = $("ovPreset").value;
  if (!name) return;
  const entry = (PRESETS || []).find((p) => p.name === name);
  if (!entry) return;
  clearOv();
  const patch = entry.patch || {};
  OV.preset = patch.preset || null;
  OV.name = name;
  // keep every option the preset carries, even the ones the block cannot show
  OV.patch = { ...patch };
  delete OV.patch.preset;
  if (patch.subtitles_mode) $("ovSubs").value = patch.subtitles_mode;
  if (patch.subtitles_langs) $("ovSubLangs").value = patch.subtitles_langs;
  if (patch.sponsorblock_mode) $("ovSb").value = patch.sponsorblock_mode;
  // a preset that says "off" must show as off: with a checkbox it looked
  // untouched, and the next read re-sent the preset without the claim
  $("ovMeta").value =
    patch.embed_metadata === true ? "on"
      : patch.embed_metadata === false ? "off" : "";
  $("ovThumb").value =
    patch.embed_thumbnail === true ? "on"
      : patch.embed_thumbnail === false ? "off" : "";
  if (patch.raw_args) $("ovRaw").value = patch.raw_args;
  if (patch.download_sections) {
    // the preset stores one string; the block shows two fields
    const [start, end] = String(patch.download_sections)
      .replace(/^\*/, "").split("-");
    $("ovClipStart").value = (start || "").trim();
    $("ovClipEnd").value = (end || "").trim();
  }
  if (patch.video_container) $("ovContainer").value = patch.video_container;
  if (patch.archive_ignore) $("ovArchive").value = "ignore";
  $("ovPreset").value = name;
  renderOvCount();
  renderOvPresetInfo();
  renderOvPresetActions();
  const n = Object.keys(readOv() || {}).length + (OV.preset ? 1 : 0);
  toast(t("preset “{name}” applied — {n} option(s) for the next download",
           { name: name, n: n }));
}

/** What the applied preset carries, spelled out — the block shows a few of
 *  these fields, but a preset may set options it has no field for, and those
 *  used to ride invisibly (v0.34.0). */
function renderOvPresetInfo() {
  const box = $("ovPresetInfo");
  const entry = OV.name
    ? (PRESETS || []).find((p) => p.name === OV.name) : null;
  if (!entry) {
    box.classList.add("hidden");
    box.textContent = "";
    return;
  }
  const patch = entry.patch || {};
  const sets = Object.keys(patch).map((k) => k + "=" + patch[k]).join(" · ");
  box.textContent = t("preset “{name}”", { name: entry.name })
    + (entry.builtin ? " " + t("(built-in)") : "")
    + (entry.description ? " — " + entry.description : "")
    + (sets ? " · " + t("sets {sets}", { sets: sets }) : "");
  box.classList.remove("hidden");
}

/** "Update “name”" exists only for the user's own presets: a built-in is
 *  code, and overwriting it is not a thing — save a copy instead. */
function renderOvPresetActions() {
  const upd = $("ovUpdate");
  const entry = OV.name
    ? (PRESETS || []).find((p) => p.name === OV.name) : null;
  if (entry && !entry.builtin) {
    upd.textContent = t("Update “{name}”", { name: entry.name });
    upd.title = t("write the fields above into this preset");
    upd.classList.remove("hidden");
  } else {
    upd.classList.add("hidden");
  }
}

/** The block's fields as a patch — exactly what a download would carry. */
function presetFromPanel() {
  const patch = { ...(readOv() || {}) };
  if (OV.preset) patch.preset = OV.preset;
  return patch;
}

function showOvSaveMsg(text, cls) {
  const msg = $("ovSaveMsg");
  msg.textContent = text;
  msg.className = "msg " + cls;
}

async function savePanelPreset() {
  const name = $("ovSaveName").value.trim();
  const patch = presetFromPanel();
  if (!Object.keys(patch).length) {
    showOvSaveMsg(t("set an option first — a preset needs at least one"), "warn");
    return;
  }
  if (!name) {
    showOvSaveMsg(t("give it a name first"), "warn");
    return;
  }
  try {
    await api("/presets", { method: "POST", body: JSON.stringify({ name, patch }) });
    $("ovSaveMsg").classList.add("hidden");
    $("ovSaveRow").classList.add("hidden");
    $("ovSaveName").value = "";
    OV.name = name;               // it is what the block now carries
    await loadPresets();          // dropdown (selects it), info line, Settings
    toast(t("saved “{name}” — {n} option(s)",
            { name: name, n: Object.keys(patch).length }));
  } catch (e) {
    showOvSaveMsg(t("could not save: {msg}", { msg: e.message }), "bad");
  }
}

async function updatePanelPreset() {
  const entry = OV.name
    ? (PRESETS || []).find((p) => p.name === OV.name) : null;
  if (!entry || entry.builtin) return;
  const patch = presetFromPanel();
  if (!Object.keys(patch).length) {
    toast(t("set an option first — a preset needs at least one"), "bad");
    return;
  }
  try {
    await api("/presets", { method: "POST",
                            body: JSON.stringify({ name: entry.name, patch }) });
    await loadPresets();
    toast(t("“{name}” updated — {n} option(s)",
            { name: entry.name, n: Object.keys(patch).length }));
  } catch (e) {
    toast(t("could not update: {msg}", { msg: e.message }), "bad");
  }
}

function renderOvPresets() {
  const sel = $("ovPreset");
  const keep = sel.value;
  sel.innerHTML = "";
  const blank = el("option", "", t("— apply a preset —"));
  blank.value = "";
  sel.append(blank);
  const groups = [[true, t("built-in")], [false, t("saved")]];
  for (const [builtin, label] of groups) {
    const items = (PRESETS || []).filter((p) => !!p.builtin === builtin);
    if (!items.length) continue;
    const group = document.createElement("optgroup");
    group.label = label;
    for (const p of items) {
      const o = el("option", "", p.name +
        (p.description ? " — " + p.description : ""));
      o.value = p.name;
      group.append(o);
    }
    sel.append(group);
  }
  // the select mirrors which preset is APPLIED (OV.name), not a stale pick:
  // a freshly saved preset only becomes selectable after this re-render
  sel.value = (OV.name && Array.from(sel.options).some((o) => o.value === OV.name))
    ? OV.name : keep;
}

function initOverrides() {
  $("ovApply").onclick = applyOvPreset;
  $("ovClear").onclick = () => { clearOv(); toast(t("cleared — using your settings")); };
  // the preset row grows the two actions it used to lack (v0.34.0): save
  // the block as a preset, and write the fields back into the applied one
  $("ovSaveLink").onclick = () => {
    $("ovSaveRow").classList.remove("hidden");
    $("ovSaveMsg").classList.add("hidden");
    $("ovSaveMsg").textContent = "";
    $("ovSaveName").focus();
  };
  $("ovSaveGo").onclick = savePanelPreset;
  $("ovSaveCancel").onclick = () => {
    $("ovSaveRow").classList.add("hidden");
    $("ovSaveMsg").classList.add("hidden");
    $("ovSaveMsg").textContent = "";
  };
  $("ovUpdate").onclick = updatePanelPreset;
  $("ovSaveName").addEventListener("keydown", (e) => {
    if (e.key === "Enter") savePanelPreset();
  });
  // the "whole video" button sat in the clip row since v0.22.0 with nothing
  // attached to it (UI review): pressing it did nothing at all
  $("ovClipClear").onclick = () => {
    $("ovClipStart").value = "";
    $("ovClipEnd").value = "";
    renderOvCount();
  };
  // the strip's clear button is the block's Clear; tapping its text brings
  // the block in — the card echoes the block, it does not duplicate it (v0.35.0)
  $("armedClear").onclick = () => {
    clearOv();
    toast(t("cleared — using your settings"));
  };
  $("armedText").tabIndex = 0;
  $("armedText").setAttribute("role", "button");
  $("armedText").onkeydown = (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    $("armedText").onclick();   // one behaviour, two doors (v0.38.3 audit #12)
  };
  $("armedText").onclick = () => {
    $("ovBlock").open = true;
    // instant, not smooth: a smooth scroll proved inert in the stripped-down
    // headless browser — and a tap that appears to do nothing is worse than
    // a jump (v0.35.0)
    $("ovBlock").scrollIntoView({ block: "start" });
  };
  for (const id of ["ovSubs", "ovSubLangs", "ovSb", "ovMeta", "ovThumb", "ovRaw",
                    "ovClipStart", "ovClipEnd", "ovContainer", "ovArchive"]) {
    $(id).addEventListener("input", renderOvCount);
    $(id).addEventListener("change", renderOvCount);
  }
}

function progressPct(j) {
  const total = j.progress && j.progress.total_bytes;
  return total ? Math.min(100, (j.progress.downloaded_bytes / total) * 100) : 0;
}

function jobSig(j) {
  return j.status + "|" + (j.filepath ? "p" : "") + "|" + (j.error ? "e" : "");
}

function metaParts(j) {
  const downloading = j.status === "downloading";
  const pct = Math.round(progressPct(j));
  const spd = j.progress && j.progress.speed ? humanBytes(j.progress.speed) + "/s" : "";
  const eta = j.progress && j.progress.eta != null
    ? t("ETA {n}s", { n: j.progress.eta }) : "";
  const pl = j.progress && j.progress.playlist_index && j.progress.playlist_count
    ? t("video {i}/{n}", { i: j.progress.playlist_index,
                          n: j.progress.playlist_count }) : "";
  const size = `${humanBytes(j.progress && j.progress.downloaded_bytes)} / ${humanBytes(j.progress && j.progress.total_bytes)}`;
  // A queued or merging job has no percentage worth printing ("0%" beside a
  // moving bar reads as a stall) and nothing has been fetched yet, so its
  // bytes read as "0 B / 0 B" — show only what is actually known.
  const known = j.progress && (j.progress.total_bytes || j.progress.downloaded_bytes);
  return [...(pl ? [pl] : []), ...(downloading ? [pct + "%"] : []),
          ...(spd ? [spd] : []), ...(eta ? [eta] : []), ...(known ? [size] : [])];
}

/** Stop a still-running job (cancel + wait for the worker), then delete it. */
async function settleThenDelete(job) {
  if (ACTIVE.has(job.status)) {
    await api(`/jobs/${job.id}/cancel`, { method: "POST" });
    for (let i = 0; i < 12; i++) {
      const { jobs } = await api("/jobs");
      const cur = jobs.find((x) => x.id === job.id);
      if (!cur || !ACTIVE.has(cur.status)) break;
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  return api(`/jobs/${job.id}/delete`, { method: "POST" });
}

/* ---------- queue bulk actions (v0.44.x audit) ----------
   The sieve made big queues readable; acting on them still meant one modal
   per row. Two counters do the bulk work — retry everything failed, clear
   everything filed — each behind its own single confirm. */
function renderQueueActions(jobs) {
  const box = $("queueActions");
  if (!box) return;
  const failed = (jobs || []).filter((j) => QUEUE_BUCKETS.error.includes(j.status)).length;
  const filed = (jobs || []).filter((j) => QUEUE_BUCKETS.filed.includes(j.status)).length;
  const rb = $("queueRetryFailed"), cb = $("queueClearFiled");
  rb.textContent = t("Retry failed ({n})", { n: failed });
  cb.textContent = t("Clear filed ({n})", { n: filed });
  rb.classList.toggle("hidden", !failed);
  cb.classList.toggle("hidden", !filed);
  box.classList.toggle("hidden", !failed && !filed);
}

async function retryFailedJobs() {
  const { jobs } = await api("/jobs").catch(() => ({ jobs: [] }));
  const failed = (jobs || []).filter((j) => QUEUE_BUCKETS.error.includes(j.status));
  if (!failed.length) return;
  let n = 0;
  for (const j of failed) {
    try { await api(`/jobs/${j.id}/retry`, { method: "POST" }); n += 1; }
    catch (_) { /* one refusal must not stop the rest */ }
  }
  toast(t("retrying {n}", { n }));
  refreshJobs();
}

async function clearFiledJobs() {
  const { jobs } = await api("/jobs").catch(() => ({ jobs: [] }));
  const filed = (jobs || []).filter((j) => QUEUE_BUCKETS.filed.includes(j.status));
  if (!filed.length) return;
  const msg = t("Delete the {n} filed downloads?", { n: filed.length })
    + (GALLERY() ? " " + t("Their Gallery/Music copies go too.") : "")
    + " " + t("This cannot be undone.");
  if (!(await askConfirm(msg, { okText: t("Delete") }))) return;
  let deleted = 0, freed = 0;
  for (const j of filed) {
    try {
      const r = await settleThenDelete(j);
      deleted += r.deleted || 0;
      freed += r.freed_bytes || 0;
      if (ANDROID() && window.AndroidHost.deleteMediaNamed) {
        const names = (j.files && j.files.length ? j.files : [j.filepath || ""])
          .map((p) => baseName(p)).filter(Boolean);
        for (const name of names) {
          try { window.AndroidHost.deleteMediaNamed(name); } catch (_) { }
        }
      }
    } catch (_) { /* report below; keep clearing the rest */ }
  }
  toast(deleted
    ? (deleted === 1
       ? t("deleted 1 file · freed {free}", { free: humanBytes(freed) })
       : t("deleted {n} files · freed {free}", { n: deleted, free: humanBytes(freed) }))
    : t("removed from the list"));
  refreshJobs();
  if (refreshStorageInfo) refreshStorageInfo();
}
$("queueRetryFailed").onclick = retryFailedJobs;
$("queueClearFiled").onclick = clearFiledJobs;

/* ---------- the yt-dlp log card (v0.44.x audit) ----------
   The verbose switch asked people to turn on a log they could never read.
   The engine keeps the last lines in memory (logcap); this card shows them. */
async function loadLog() {
  const box = $("logView");
  if (!box) return;
  try {
    const r = await api("/logs");
    const lines = r.lines || [];
    box.textContent = lines.length
      ? lines.join("\n")
      : t("nothing logged yet — turn on Verbose log for the deep one");
    box.scrollTop = box.scrollHeight;
  } catch (e) {
    box.textContent = t("could not read the log: {msg}", { msg: e.message });
  }
}
$("logOpen").onclick = async () => {
  $("logView").textContent = t("loading…");
  openModal($("logModal"));
  await loadLog();
};
$("logRefresh").onclick = loadLog;
$("logClose").onclick = () => closeModal($("logModal"));
$("logCopy").onclick = async () => {
  const ok = await copyText($("logView").textContent || "");
  toast(ok ? t("Copied") : t("copy failed"), ok ? "ok" : "bad");
};
{
  const modal = $("logModal");
  if (modal) {
    modal.onclick = (e) => { if (e.target === modal) closeModal(modal); };
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !modal.classList.contains("hidden")) closeModal(modal);
    });
  }
}

/** The trash button — one download gone, file and all, after a confirm. */
function deleteButton(j) {
  const running = ACTIVE.has(j.status);
  const b = el("button", "ghost-sm del", t("Delete"));
  b.prepend(ico("trash"));
  b.title = t("Delete this download — the file on disk goes with it");
  b.onclick = async () => {
    const name = j.filepath ? baseName(j.filepath)
      : String(j.title || j.url).slice(0, 60);
    const msg = (running ? t("Stop “{name}” and delete the partial file?", { name: name })
      : j.filepath ? t("Delete “{name}”?", { name: name })
        : t("Remove “{name}” from the list?", { name: name }))
      + (j.filepath && GALLERY() ? " " + t("Its Gallery/Music copy goes too.") : "")
      + " " + t("This cannot be undone.");
    if (!(await askConfirm(msg, { okText: running ? t("Stop and delete") : t("Delete") }))) {
      return;
    }
    // The settle can take up to three seconds (cancel → the worker returns →
    // the delete lands). The confirm dialog is gone by then, so without a mark
    // the row sat there looking untouched and people clicked Delete again
    // (motion review). `.pending` dims it and says what is happening.
    const row = $("jobs").querySelector(`.job[data-id="${j.id}"]`);
    if (row) {
      row.classList.add("pending");
      const pill = row.querySelector(".pill");
      if (pill) pill.textContent = running ? t("stopping…") : t("deleting…");
    }
    try {
      const r = await settleThenDelete(j);
      // Gallery cleanup: one name per file. A playlist row's filepath is the
      // download *folder*, so the old code asked the gallery to delete a
      // folder name that matched nothing (v0.21.2 audit).
      if (ANDROID() && window.AndroidHost.deleteMediaNamed) {
        const names = (j.files && j.files.length ? j.files : [j.filepath || ""])
          .map((p) => baseName(p)).filter(Boolean);
        for (const name of names) {
          try { window.AndroidHost.deleteMediaNamed(name); }
          catch (_) { /* the row is gone either way */ }
        }
      }
      toast(r.deleted
        ? (r.deleted === 1
           ? t("deleted 1 file · freed {free}", { free: humanBytes(r.freed_bytes) })
           : t("deleted {n} files · freed {free}",
               { n: r.deleted, free: humanBytes(r.freed_bytes) }))
        : t("removed from the list"));
      refreshJobs();
      // a delete empties part of the folder the Settings row reports on: keep
      // that row from reading stale (the "Delete 0 files (0 B)?" bug)
      if (refreshStorageInfo) refreshStorageInfo();
    } catch (e) {
      toast(t("could not delete: {msg}", { msg: e.message }), "bad");
      if (row) row.classList.remove("pending");   // the row is staying: undo it
    }
  };
  return b;
}

function jobRow(j) {
  const row = el("div", "job");
  row.setAttribute("role", "listitem");
  row.dataset.status = j.status;   // v0.40.2: what the queue sieve reads
  const top = el("div", "jobtop");
  const title = el("span", "jobtitle", j.title || j.url);
  title.title = j.url;
  // the title ellipsises on a phone and nothing hover-reveals it there: a
  // tap unfolds the whole line (2026-10-01 report). v0.38.3: it is a real
  // button to the keyboard too — focus, Enter/Space, and the expanded state
  // announced.
  //
  // v0.45.8: the fold hung off the title text alone, so the rest of the
  // card — the pills, the stamp, the empty middle, the path row — did
  // nothing, and on a phone the one live spot was a word at the top left
  // (2026-10-06 report). The whole card flips it now; anything with its own
  // job — buttons, links, fields, the error text with its own tap — is
  // skipped by the guard.
  title.tabIndex = 0;
  title.setAttribute("role", "button");
  title.setAttribute("aria-expanded", "false");
  const flip = () => {
    title.classList.toggle("open");
    // the row carries the state too (v0.39.12): the fold hung off :has(),
    // which older engines drop whole — the receipt could never expand there
    row.classList.toggle("open", title.classList.contains("open"));
    title.setAttribute("aria-expanded",
      title.classList.contains("open") ? "true" : "false");
  };
  row.onclick = (e) => {
    if (e.target.closest("button, a, input, select, textarea, .jerr")) return;
    flip();
  };
  title.onkeydown = (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    e.preventDefault();
    flip();
  };
  top.append(title, el("span", "pill " + j.status, t(j.status)));
  // a finished take gets the stamp (v0.37.0: completion used to be a pill
  // you never saw flip in a tab you were not on)
  if (j.status === "completed") {
    const stamp = el("span", "stamp", t("FILED"));
    stamp.title = t("download finished — the file is in your downloads");
    top.append(stamp);
  }
  // what this job actually carries (preset / per-download overrides)
  const extra = j.overrides ? Object.keys(j.overrides).length : 0;
  if (j.preset) {
    const chip = el("span", "chip tag",
      t("{name} preset", { name: j.preset.replace("audio-", "") }));
    chip.title = t("audio preset: {name}", { name: j.preset });
    top.append(chip);
  }
  if (extra) {
    const chip = el("span", "chip tag",
      extra === 1 ? t("1 option") : t("{n} options", { n: extra }));
    chip.title = t("{keys} — this download only",
                   { keys: Object.keys(j.overrides).join(", ") });
    top.append(chip);
  }
  row.append(top);

  let trashHost = null;   // the button row the trash belongs to

  if (ACTIVE.has(j.status)) {
    // Every active state gets a bar: "downloading" carries real progress, and
    // queued/merging get an indeterminate track. A 15–45s ffmpeg mux with no
    // motion anywhere reads as a hung engine (motion review).
    const downloading = j.status === "downloading";
    const bar = el("div", "bar");
    bar.setAttribute("role", "progressbar");
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    if (downloading) bar.setAttribute("aria-valuenow", progressPct(j).toFixed(0));
    const fill = el("div", "fill active" + (downloading ? "" : " indet"));
    fill.style.width = downloading ? progressPct(j).toFixed(1) + "%" : "100%";
    bar.append(fill);
    row.append(bar);
    const meta = el("div", "jmeta");
    meta.append(...metaParts(j).map((s) => el("span", "", s)));
    row.append(meta);
  } else if (j.status === "error" || j.status === "interrupted") {
    // the human consequence leads; the engine's own dialect goes below,
    // behind the toggle (v0.37.0 — it used to be the first thing you read)
    row.append(el("div", "jerrsay", t(humanErr(j.error || "", undefined, j.url))));
    // The whole message. A 160-char slice in a single ellipsised line cut
    // yt-dlp's explanation down to "ERROR: Unable to down…" — the part that
    // says what to do next was exactly the part that was hidden. Long text
    // starts clamped to two lines; a tap unfolds it (2026-09-27 report).
    // v0.37.1: it reads at its own full width — it used to share one flex
    // line with the buttons and wrapped to about one word per line on a
    // phone (2026-09-30 photo).
    const errText = j.error || "";
    const errEl = el("div", "jerr", errText);
    errEl.id = "jerr-" + j.id;   // the details toggle names its region
    if (errText.length > 90) {
      errEl.classList.add("clamp");
      errEl.title = t("tap to show the whole message");
      errEl.onclick = () => {
        const open = errEl.classList.toggle("open");
        errEl.title = open ? t("tap to collapse") : t("tap to show the whole message");
      };
    }
    row.append(errEl);
    const r = el("div", "jrow");
    if (errEl.classList.contains("clamp")) {
      // a visible affordance, not just a hidden cursor (v0.37.0)
      const more = el("button", "linkbtn jrr-toggle", t("Show details"));
      more.setAttribute("aria-expanded", "false");
      more.setAttribute("aria-controls", errEl.id || "");
      more.onclick = () => {
        const open = errEl.classList.toggle("open");
        errEl.title = open ? t("tap to collapse") : t("tap to show the whole message");
        more.textContent = open ? t("Hide details") : t("Show details");
        more.setAttribute("aria-expanded", open ? "true" : "false");
      };
      r.append(more);
    }
    const copy = el("button", "ghost-sm", t("Copy"));
    copy.title = t("copy the whole message");
    copy.onclick = async () => {
      const ok = await copyText(errText);
      toast(ok ? t("error copied") : t("copy failed"), ok ? "ok" : "bad");
    };
    const retry = el("button", "ghost-sm", t("Retry"));
    retry.onclick = () => api(`/jobs/${j.id}/retry`, { method: "POST" })
      .then(refreshJobs)
      .catch((e) => toast(t("retry failed: {msg}", { msg: e.message }), "bad"));
    r.append(copy, retry);
    trashHost = r;
    row.append(r);
    if (j.error && /ffmpeg/i.test(j.error) &&
        /not found|not installed|No such file/i.test(j.error)) {
      row.append(el("div", "jobhint",
        t("This step needs ffmpeg. Use “keep original” for audio-only, or install ffmpeg.")));
    }
  } else if (j.filepath) {
    const r = el("div", "jrow");
    r.append(el("span", "path", j.filepath));
    if (DESKTOP) {
      const open = el("button", "ghost-sm", t("Open folder"));
      open.onclick = () => api(`/jobs/${j.id}/reveal`, { method: "POST" })
        .catch((e) => toast(t("could not open: {msg}", { msg: e.message }), "bad"));
      r.append(open);
    }
    // A playlist row's filepath is the download folder, so the row-level
    // hand-offs would ask a player (or another app) to open a directory.
    // The row still owns real files — `files` — so it offers them, each
    // with the same Open / Share / Play a single-file row has (2026-09-27
    // report: "There's no open and share button for the playlist").
    //
    // A merged single-file download is NOT a playlist: its `files` also
    // lists the video/audio fragments it muxed (master.f200.mp4, …), but
    // its own filepath is among them — a folder is never (2026-09-27,
    // caught live: a merged row offered "Files (3)" instead of Play).
    const playlistRow = !!(j.files && j.files.length
    && j.files[0] !== j.filepath && !j.files.includes(j.filepath));
    if (playlistRow) {
      const count = j.files.length;
      const toggle = el("button", "ghost-sm", t("Files ({n})", { n: count }));
      toggle.title = t("show every file this playlist downloaded");
      const listHost = el("div", "jobfiles hidden");
      toggle.onclick = () => {
        const hidden = listHost.classList.toggle("hidden");
        toggle.textContent = hidden
          ? t("Files ({n})", { n: count })
          : t("Hide files ({n})", { n: count });
      };
      for (const file of j.files) listHost.append(jobFileItem(j, file));
      r.append(toggle);
      row.append(listHost);
    } else {
      // Hand off a *file*: Android/data is off-limits to file managers, so
      // hand the file itself to another app (a provider grant).
      if (ANDROID() && j.filepath) {
        const open = el("button", "ghost-sm", t("Open"));
        open.onclick = () => {
          try { window.AndroidHost.openFile(j.filepath); }
          catch (e) { toast(t("could not open: {msg}", { msg: e.message }), "bad"); }
        };
        const share = el("button", "ghost-sm", t("Share"));
        share.onclick = () => {
          try { window.AndroidHost.shareFile(j.filepath); }
          catch (e) { toast(t("could not share: {msg}", { msg: e.message }), "bad"); }
        };
        r.append(open, share);
      }
      // Play it right here (v0.22.0). Works on every platform: the engine
      // answers Range requests, so the player can seek.
      if (j.status === "completed" && j.filepath) {
        const play = el("button", "ghost-sm", t("Play"));
        play.onclick = () => openPlayer(j);
        r.append(play);
      }
    }
    trashHost = r;
    row.append(r);
    // the unfolded card reads like a receipt (v0.38.2: "other than name show
    // us the file size and the location too — it's expanding for a reason").
    // Collapsed rows keep the compact strip; the title tap unfolds both.
    const details = el("div", "jdetails");
    details.id = "jd-" + j.id;   // the title button names what it controls
    const grid = el("div", "jdgrid");   // the shrinkable row the fold animates
    grid.append(
      el("span", "jdlbl", t("size")),
      el("span", "jdval", j.size_bytes != null ? humanBytes(j.size_bytes) : "—"),
      el("span", "jdlbl", t("saved")),
      el("span", "jdpath", j.filepath || "—"),
    );
    details.append(grid);
    title.setAttribute("aria-controls", details.id);
    row.append(details);
    if (j.note) row.append(el("div", "jobhint", j.note));
  }

  if (j.raw_args) {
    row.append(el("div", "jobhint",
                  t("yt-dlp args: {args}", { args: j.raw_args })));
  }

  const actions = el("div", "jrow");
  if (ACTIVE.has(j.status)) {
    // pause keeps the bytes already fetched; cancel throws them away
    // (v0.22.0 review #6)
    const pause = el("button", "ghost-sm", t("Pause"));
    pause.onclick = () => api(`/jobs/${j.id}/pause`, { method: "POST" })
      .then(refreshJobs)
      .catch((e) => toast(t("pause failed: {msg}", { msg: e.message }), "bad"));
    const c = el("button", "ghost-sm", t("Cancel"));
    c.onclick = () => api(`/jobs/${j.id}/cancel`, { method: "POST" })
      .then(refreshJobs)
      .catch((e) => toast(t("cancel failed: {msg}", { msg: e.message }), "bad"));
    actions.append(pause, c);
  } else if (j.status === "paused") {
    const res = el("button", "ghost-sm", t("Resume"));
    res.onclick = () => api(`/jobs/${j.id}/resume`, { method: "POST" })
      .then(refreshJobs)
      .catch((e) => toast(t("resume failed: {msg}", { msg: e.message }), "bad"));
    actions.append(res);
  } else if (j.status === "cancelled") {
    // a cancelled job shows no error line of its own, so its retry lives here
    const r = el("button", "ghost-sm", t("Retry"));
    r.onclick = () => api(`/jobs/${j.id}/retry`, { method: "POST" })
      .then(refreshJobs)
      .catch((e) => toast(t("retry failed: {msg}", { msg: e.message }), "bad"));
    actions.append(r);
  } else if (j.status === "error" || j.status === "interrupted") {
    // only "Edit & retry": the plain Retry already sits beside the error
    // message above, and two buttons doing one thing made failed rows look
    // broken (UI review)
    const edit = el("button", "ghost-sm", t("Edit & retry"));
    edit.title = t("load this job's URL and options into the Download tab");
    edit.onclick = () => editAndRetry(j);
    actions.append(edit);
  }
  // every row can be deleted (a running one is stopped first, after a confirm)
  if (!trashHost) trashHost = actions;
  trashHost.append(deleteButton(j));
  if (actions.children.length) row.append(actions);
  row.dataset.sig = jobSig(j);
  return row;
}

/** One entry of a playlist's file list: the same hand-offs a single-file
 *  row has, applied to the entry itself (2026-09-27). */
function jobFileItem(j, file) {
  const item = el("div", "jitem");
  const name = baseName(file);
  const label = el("span", "jname", name);
  label.title = file;
  item.append(label);
  if (ANDROID() && window.AndroidHost) {
    const open = el("button", "ghost-sm", t("Open"));
    open.onclick = () => {
      try { window.AndroidHost.openFile(file); }
      catch (e) { toast(t("could not open: {msg}", { msg: e.message }), "bad"); }
    };
    const share = el("button", "ghost-sm", t("Share"));
    share.onclick = () => {
      try { window.AndroidHost.shareFile(file); }
      catch (e) { toast(t("could not share: {msg}", { msg: e.message }), "bad"); }
    };
    item.append(open, share);
  }
  if (j.status === "completed") {
    const play = el("button", "ghost-sm", t("Play"));
    play.onclick = () => openPlayer(j, file);
    item.append(play);
  }
  return item;
}

/** Patch an existing row in place (smooth progress); rebuild on status change. */
function updateJobRow(row, j) {
  row.dataset.status = j.status;   // v0.40.2: what the queue sieve reads
  if (row.dataset.sig !== jobSig(j)) {
    const fresh = jobRow(j);
    fresh.dataset.id = j.id;
    // the receipt's fold survives a poll-driven rebuild (the audit): a row
    // rebuilt while its details were open used to slam shut, unanimated
    if (row.querySelector(".jobtitle.open")) {
      fresh.classList.add("open");
      const ftitle = fresh.querySelector(".jobtitle");
      if (ftitle) {
        ftitle.classList.add("open");
        ftitle.setAttribute("aria-expanded", "true");
      }
    }
    fresh.classList.add("swap");
    row.replaceWith(fresh);
    return fresh;
  }
  const title = row.querySelector(".jobtitle");
  const text = j.title || j.url;
  if (title && title.textContent !== text) title.textContent = text;
  const fill = row.querySelector(".fill");
  if (fill && !fill.classList.contains("indet")) {
    fill.style.width = progressPct(j).toFixed(1) + "%";
    const bar = row.querySelector(".bar");
    if (bar) bar.setAttribute("aria-valuenow", progressPct(j).toFixed(0));
  }
  const meta = row.querySelector(".jmeta");
  if (meta) meta.replaceChildren(...metaParts(j).map((s) => el("span", "", s)));
  return row;
}

/** Which view a job belongs to (v0.40.2). Unknown states count as active:
 *  a state the sieve has not met yet should never vanish silently. */
function queueBucket(status) {
  if (QUEUE_BUCKETS.filed.includes(status)) return "filed";
  if (QUEUE_BUCKETS.error.includes(status)) return "error";
  return "active";
}

/** Apply QFILTER to the rows on screen right now and say what got hidden,
 *  so a filtered view never reads as an empty queue. */
function applyQueueFilter() {
  const box = $("jobs");
  if (!box) return;
  let hidden = 0;
  for (const row of box.querySelectorAll(".job")) {
    const show = QFILTER === "all" ||
                 queueBucket(row.dataset.status || "") === QFILTER;
    if (show) {
      // a filter flipped mid-flight reverses cleanly: clear whatever the
      // previous pass on this row started (v0.42.1)
      if (row._hideT) { clearTimeout(row._hideT); row._hideT = 0; }
      if (row.classList.contains("hidden") || row.classList.contains("leaving")) {
        row.classList.remove("hidden");
        row.classList.remove("leaving");
        row.classList.add("swap");   // it returns: soft, like a rebuilt row
      }
    } else if (!row.classList.contains("hidden") && !row.classList.contains("leaving")) {
      // rows glide out, then hide — the sieve used to jump (v0.42.1 motion
      // audit): same exit as a dismissed job, with the reverse handled above
      row.classList.add("leaving");
      const settle = () => {
        if (row._hideT) { clearTimeout(row._hideT); row._hideT = 0; }
        const matches = QFILTER === "all" ||
          queueBucket(row.dataset.status || "") === QFILTER;
        if (matches) { row.classList.remove("leaving"); return; }
        row.classList.add("hidden");
        row.classList.remove("leaving");
      };
      const h = (ev) => {
        if (ev.target !== row) return;
        row.removeEventListener("animationend", h);
        settle();
      };
      row.addEventListener("animationend", h);
      row._hideT = setTimeout(() => {
        row.removeEventListener("animationend", h);
        settle();
      }, motionMs(280));
      hidden += 1;
    } else {
      hidden += 1;   // already hidden, or on its way: it still counts
    }
  }
  const empty = $("filterEmpty");
  if (empty) {
    empty.classList.toggle("hidden", hidden === 0);
    const say = empty.querySelector(".say");
    if (say) {
      say.textContent = hidden === 1
        ? t("1 job hidden by this filter")
        : t("{n} jobs hidden by this filter", { n: hidden });
    }
  }
}

/** The chips row: one pick at a time, announced; "Show all" is the way back
 *  from the counted line. */
function wireQueueFilters() {
  const row = $("queueFilters");
  if (!row) return;
  row.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-qfilter]");
    if (!btn) return;
    QFILTER = btn.dataset.qfilter;
    for (const b of row.querySelectorAll("[data-qfilter]")) {
      const on = b === btn;
      b.classList.toggle("pick", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
    }
    applyQueueFilter();
  });
  const all = $("filterAll");
  if (all) all.onclick = () => row.querySelector('[data-qfilter="all"]').click();
}

let JOBS_SEQ = 0;
let JOBS_BUSY = false;
let JOBS_FAILS = 0;

/** A poll that keeps failing has to say so: a silently empty queue reads as
 *  "nothing downloaded" when the truth is "could not ask" (v0.21.1 audit). */
function showQueueTrouble(e) {
  const box = $("jobs");
  if (!box || box.querySelector(".trouble")) return;
  box.prepend(el("div", "empty trouble",
    t("cannot reach the engine ({why}) — retrying every couple of seconds.",
      { why: (e && e.message) || t("no answer") })));
}

/** Take a queue row (or the empty-state box) off screen with an exit.
 *
 *  Deleting used to `remove()` the node between two frames — a glitch next to
 *  toasts, which slide away properly — and it also meant the row was gone
 *  before anyone could see WHICH row left. Transform/opacity only: animating
 *  height would put layout on the main thread on every tick, which is exactly
 *  what the WebView cannot afford. The node is dropped when the animation
 *  ends, with a timer as a backstop for a hidden tab (where animations do not
 *  run and `animationend` never arrives), and the guard keeps a second poll
 *  from restarting an exit already in flight. */
function leaveRow(node, keepView) {
  if (!node || node.classList.contains("leaving")) return;
  node.classList.add("leaving");
  let gone = false;
  const drop = () => {
    if (gone) return;
    gone = true;
    // v0.45.13: the reader's spot must survive the drop. Remember the
    // topmost row still visible, take the height away, put the view back
    // where it was — Chromium's native anchoring can pick the DYING row
    // as its anchor and then land the viewport anywhere (the 2026-10-07
    // report: deleting a failed job scrolled the screen to the page's
    // end). Only rows the ENGINE's list drops pass keepView; a chip
    // filter hiding a row is the user's own doing and keeps the plain exit.
    let anchor = null;
    if (keepView) {
      const vh = window.innerHeight;
      for (const r of node.parentElement.children) {
        if (r === node || !r.classList.contains("job")
            || r.classList.contains("leaving")) continue;
        const b = r.getBoundingClientRect();
        if (b.bottom > 0 && b.top < vh) { anchor = { el: r, y: b.top }; break; }
      }
    }
    node.remove();
    if (anchor && document.contains(anchor.el)) {
      const sc = document.scrollingElement || document.documentElement;
      const dy = anchor.el.getBoundingClientRect().top - anchor.y;
      if (Math.abs(dy) > 4) sc.scrollTop = Math.max(0, sc.scrollTop + dy);
    }
  };
  node.addEventListener("animationend", (e) => {
    if (e.target === node) drop();
  });
  setTimeout(drop, motionMs(400));
}

/* ---------- a finish that speaks (v0.37.0) ---------- */
/** The queue used to turn a pill green in a tab you were not on. The first
 *  poll that sees a job BECOME `completed` fires one toast with the real
 *  choices — play it, or open the folder it was filed in. */
let JOB_STATE = new Map();

function onFiled(j) {
  const name = j.filepath ? baseName(j.filepath)
    : (j.title || j.url);
  const actions = [];
  if (j.filepath) {
    actions.push({ label: t("Play"), prime: true,
                   onClick: () => openPlayer(j) });
  }
  actions.push({
    label: t("Show folder"),
    onClick: () => { const b = $("openDir"); if (b) b.click(); },
  });
  toast(t("Filed — {name}", { name: name }), "ok", { actions: actions });
}

/** The bins rail: the last few finished takes, newest first (v0.37.0). */
function renderBins(list) {
  const box = $("binsList");
  if (!box) return;
  const filed = (list || []).filter((j) => j.status === "completed");
  const count = $("binsCount");
  if (count) count.textContent = filed.length ? String(filed.length) : "";
  box.replaceChildren();
  if (!filed.length) {
    box.append(el("div", "bins-empty muted small",
      t("Nothing filed yet — a finished download lands here.")));
    return;
  }
  for (const j of filed.slice(0, 8)) {
    const b = el("button", "bin");
    b.type = "button";
    b.title = j.filepath || j.url;
    b.append(el("span", "bin-title", j.title || j.url));
    const file = j.filepath ? baseName(j.filepath) : "";
    if (file) b.append(el("span", "bin-meta mono", file));
    b.onclick = () => { if (j.filepath) openPlayer(j); };
    box.append(b);
  }
}

async function refreshJobs() {
  if (document.hidden) return;   // a hidden page keeps its last snapshot;
  // the visibilitychange below re-syncs the moment it is looked at again
  if (JOBS_BUSY) return;      // one poll at a time: a slow, older snapshot
  JOBS_BUSY = true;           // must never repaint newer state
  const seq = ++JOBS_SEQ;
  try {
    const { jobs } = await api("/jobs");
    if (seq !== JOBS_SEQ) return;
    JOBS_FAILS = 0;
    renderQueueBadge(jobs);
    renderQueueActions(jobs);
    const box = $("jobs");
    // a banner raised by an outage has to die with the outage: it was only
    // ever removed on the non-empty path, so it stayed on screen forever over
    // an empty queue, claiming the engine was unreachable while everything
    // worked (UI review)
    const stale = box.querySelector(".trouble");
    if (stale) stale.remove();
    // v0.40.2: the sieve's chips follow the queue's real emptiness
    $("queueFilters").classList.toggle("hidden", !jobs.length);
    // the static boot line ("Checking the queue…") yields to real content
    const boot = box.querySelector("#jobsInitial");
    if (boot) boot.remove();
    const list = jobs.sort(
      (a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    // a finish that speaks: the FIRST poll that sees a job become completed
    // says so — once (v0.37.0)
    const seen = new Set();
    for (const j of list) {
      seen.add(j.id);
      const prev = JOB_STATE.get(j.id);
      if (j.status === "completed" && prev && prev !== "completed") onFiled(j);
      JOB_STATE.set(j.id, j.status);
    }
    for (const id of [...JOB_STATE.keys()]) if (!seen.has(id)) JOB_STATE.delete(id);
    renderBins(list);
    if (!list.length) {
      // rows that are gone should leave, not blink out: the same exit the
      // delete path uses, then the empty state fades in behind them
      box.querySelectorAll(".job").forEach(leaveRow);
      if (!box.querySelector(".empty")) {
        box.append(el("div", "empty",
          t("Nothing in the queue. Downloads you start land here — finished ones stay put so you can open, share or delete them.")));
      }
      const fe = $("filterEmpty");
      if (fe) fe.classList.add("hidden");
      return;
    }
    const empty = box.querySelector(".empty");
    if (empty) leaveRow(empty);

    const keep = new Set(list.map((j) => j.id));
    // v0.45.13: mark the dying rows BEFORE the placement loop. The loop
    // used to run first, so its anchor chain walked onto the just-deleted
    // row while it still looked ordinary — every other row was inserted
    // IN FRONT of it and the deleted row visibly sailed to the end of the
    // list while fading ("the screen scrolls to the bottom", 2026-10-07;
    // it was content motion, not scrolling). Marking first lets the
    // anchors skip the dying rows and everyone keeps their place.
    box.querySelectorAll(".job").forEach((r) => {
      if (!keep.has(r.dataset.id)) leaveRow(r, true);   // the reader's spot stays
    });
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
      let anchor = prev ? prev.nextElementSibling : box.firstElementChild;
      // v0.45.13: skip PAST dying rows when anchoring the order — the old
      // chain could land on a `.leaving` sibling, so the deleted row's
      // neighbours were inserted BEFORE it and the dying row visibly
      // sailed to the end of the list (the 2026-10-07 "screen scrolls to
      // the bottom" report — it was content motion, not scrolling).
      // The dying row keeps its exact place while it fades; everyone
      // else keeps theirs.
      while (anchor && anchor.classList.contains("leaving")) {
        anchor = anchor.nextElementSibling;
      }
      if (row !== anchor) box.insertBefore(row, anchor);
      prev = row;
    }
    applyQueueFilter();          // v0.40.2: a repaint keeps the view
  } catch (e) {
    if (seq !== JOBS_SEQ) return;
    JOBS_FAILS += 1;
    if (JOBS_FAILS === 3) showQueueTrouble(e);   // then keep retrying quietly
  } finally {
    JOBS_BUSY = false;
  }
}

/* ---------- header ---------- */
async function loadVersions() {
  try {
    const v = await api("/version");
    $("versions").textContent =
      t("engine {engine} · yt-dlp {dlp}", { engine: v.engine, dlp: v.yt_dlp });
    // the yt-dlp tab shows it beside its own update button
    const yv = $("ytdlpVer");
    if (yv) yv.textContent = v.yt_dlp;
    // a staged copy (v0.43.0) waits for the next start — say so until live
    const st = $("ytdlpStaged");
    if (st) {
      st.hidden = !v.staged;
      st.textContent = v.staged
        ? t("yt-dlp {v} is staged — restart to use it", { v: v.staged }) : "";
    }
    // where the running copy comes from (v0.43.1) — and the undo lives here
    const src = $("ytdlpSrc");
    if (src) src.textContent =
      v.source === "downloaded" ? t("(downloaded)")
        : v.source === "bundled" ? t("(bundled)") : "";
    const row = $("ytdlpRemoveRow"), hint = $("ytdlpRemoveHint");
    if (row) {
      row.hidden = !(v.source === "downloaded" || v.staged);
      const btn = $("removeBtn");
      if (btn) btn.hidden = !!v.remove_pending;   // nothing left to remove
      if (hint) hint.textContent = v.remove_pending
        ? t("removal is set — the bundled copy takes over on the next start")
        : v.staged
        ? (v.source === "downloaded"
          ? t("a newer copy from PyPI is staged — removing deletes the downloaded copy and cancels the stage")
          : t("a copy from PyPI is staged — removing cancels it"))
        : t("downloaded from PyPI — removing falls back to the bundled copy on the next start");
    }
  } catch (_) { $("versions").textContent = ""; }
}

/* ---------- app updates --------------------------------------------------- *
 * One check feeds two places: the Settings → General row (always visible, with
 * a way to ask again) and one persistent toast that carries the actual
 * choices. Skip and snooze are per-device, so they live in localStorage —
 * Android loads this UI from a fixed origin (127.0.0.1:8787), so they survive
 * a restart; on desktop the engine port can vary, in which case the notice may
 * ask once more. Nothing here installs anything: "Get it" only opens the
 * release page, because no build of this app can replace itself in place. */
const UPD = {
  skipped: "suravidl.upd.skipped",   // the version the user said no to
  snooze: "suravidl.upd.snooze",     // epoch ms until which to stay quiet
  last: "suravidl.upd.last",         // {at, latest, available, error}
  SNOOZE_MS: 24 * 60 * 60 * 1000,
};
const updStore = {
  get(k, dflt = "") {
    try { const v = localStorage.getItem(k); return v === null ? dflt : v; }
    catch (_) { return dflt; }
  },
  set(k, v) { try { localStorage.setItem(k, v); } catch (_) { /* private mode */ } },
};
const RELEASES_LATEST = "https://github.com/LoLyeah/suravidl/releases/latest";
let UPD_STATE = null;   // the last /update-check answer

function humanSince(ts) {
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 90) return t("just now");
  const m = Math.round(s / 60);
  if (m < 90) return m === 1 ? t("1 minute ago") : t("{m} minutes ago", { m: m });
  const h = Math.round(m / 60);
  if (h < 36) return h === 1 ? t("1 hour ago") : t("{h} hours ago", { h: h });
  const d = Math.round(h / 24);
  return d === 1 ? t("1 day ago") : t("{d} days ago", { d: d });
}

/** Settings → General → Updates: state, the versions, and what to do. */
function renderUpdateRow() {
  const state = $("updState"), meta = $("updMeta");
  if (!state) return;
  const get = $("updGet"), skip = $("updSkip"), man = $("updManual");
  const chk = $("updCheck");
  const u = UPD_STATE;
  let last = null;
  try { last = JSON.parse(updStore.get(UPD.last, "") || "null"); } catch (_) { last = null; }
  const when = last && last.at
    ? t("checked {when}", { when: humanSince(last.at) }) : t("not checked yet");
  const err = (u && u.error) || (last && last.error) || null;
  meta.classList.remove("bad");
  // an available update makes "Check now" redundant; the row is crowded
  // enough at 360px without it (v0.41.x audit)
  if (chk) chk.classList.toggle("hidden", !!(u && u.update_available));
  if (err) {
    // One error class the user can act on: a build that can't verify the
    // server's certificate (packaged Mac apps before v0.38.8 carried no CA
    // store). It gets plain words and the one door that fixes it; everything
    // else stays raw — it's information, not noise.
    const cert = /CERTIFICATE_VERIFY_FAILED|certificate verify failed/i.test(String(err));
    state.textContent = t("could not check for updates");
    meta.textContent = cert
      ? t("can't verify server certificates in this build — get the newest suravidl once and checks work from there · {when}", { when: when })
      : `${err} · ${when}`;
    if (cert) {
      get.textContent = t("Open the releases page");
      get.classList.remove("hidden");
      get.onclick = () => openExternal(RELEASES_LATEST);
    } else {
      get.classList.add("hidden");
    }
    skip.classList.add("hidden");
    man.classList.add("hidden");
    return;
  }
  if (!u) {                       // no answer yet: say so, offer the button
    state.textContent = t("not checked yet");
    meta.textContent = when;
    get.classList.add("hidden");
    skip.classList.add("hidden");
    man.classList.add("hidden");
    return;
  }
  const skipped = !!u.latest && updStore.get(UPD.skipped, "") === u.latest;
  // The courier (v0.41.0): when this build can fetch and install its own
  // update, the row becomes the whole flow — stage it, watch it, restart
  // into it. Builds that cannot keep the plain release-page door below.
  if (u.update_available && u.can_apply) {
    renderCourierRow(u, { state, meta, get, skip, man }, when, skipped);
    return;
  }
  if (u.update_available && u.url) {
    state.textContent = t("suravidl {v} is available", { v: u.latest });
    meta.textContent = t("you have {v} · {when}", { v: u.current, when: when })
      + (skipped ? " · " + t("skipped") : "");
    man.classList.add("hidden");
    get.textContent = t("Get {v}", { v: u.latest });
    get.classList.remove("hidden");
    get.onclick = () => openExternal(u.url);
    skip.textContent = skipped ? t("Stop skipping") : t("Skip this version");
    skip.classList.remove("hidden");
    skip.onclick = () => {
      updStore.set(UPD.skipped, skipped ? "" : u.latest);
      renderUpdateRow();
    };
  } else {
    state.textContent = t("up to date");
    meta.textContent = t("you have {v} · {when}", { v: u.current, when: when });
    get.classList.add("hidden");
    skip.classList.add("hidden");
    man.classList.add("hidden");
  }
}

/** The one persistent notice: a toast that waits, with the three answers. */
function showUpdateBanner(u) {
  if (document.querySelector(".toast.update")) return;   // one notice, not a stack
  // The courier (v0.41.0): a build that can install its own update gets the
  // one-tap door; every other build keeps the release page.
  const prime = u.can_apply
    ? { label: t("Update now"), prime: true, onClick: () => startUpdateDownload() }
    : { label: t("Get {v}", { v: u.latest }), prime: true,
        onClick: () => openExternal(u.url) };
  toast(t("suravidl {v} is available — you have {cur}",
          { v: u.latest, cur: u.current }), "info update", {
    sticky: true,
    actions: [
      prime,
      { label: t("Later"), onClick: () => {
        updStore.set(UPD.snooze, String(Date.now() + UPD.SNOOZE_MS));
        toast(t("I'll remind you tomorrow"));
      } },
      { label: t("Skip this version"), onClick: () => {
        updStore.set(UPD.skipped, u.latest);
        toast(t("won't ask about {v} again", { v: u.latest }));
        renderUpdateRow();
      } },
    ],
  });
}

/** The courier (v0.41.0): stage the release in-app, then install it.
 *
 * The engine downloads this platform's asset from the release manifest,
 * verifies sha256, and stages it; this side watches and offers the one door
 * that fits the shell — desktop rides the installer, Android hands the APK
 * to the system installer (the one confirmation Android insists on), and any
 * refusal falls back to the release page. */
let UPD_DL = null;     // the last /update/status answer
let UPD_POLL = 0;      // one poller at a time
let UPD_PERM_WAIT = false;   // sent to Android's settings; greet on return

function updPct(st) {
  if (!st || !st.total) return null;
  return Math.min(100, Math.round((st.bytes / st.total) * 100));
}

async function startUpdateDownload() {
  try {
    UPD_DL = await api("/update/download", { method: "POST" });
  } catch (e) {
    toast(t("could not start the update: {msg}", { msg: e.message }), "bad");
    return;
  }
  toast(t("downloading the update in the background — watch Settings → Updates"));
  renderUpdateRow();
  pollUpdateStatus();
}

function pollUpdateStatus() {
  clearTimeout(UPD_POLL);
  UPD_POLL = setTimeout(async () => {
    try { UPD_DL = await api("/update/status"); } catch (_) { /* hold the last truth */ }
    renderUpdateRow();
    if (UPD_DL && (UPD_DL.status === "downloading" || UPD_DL.status === "verifying")) {
      pollUpdateStatus();
    } else if (UPD_DL && UPD_DL.status === "ready") {
      announceUpdateReady();
    } else if (UPD_DL && UPD_DL.status === "failed") {
      // a failure buried in a hidden Settings tab reads as "nothing
      // happened" (v0.41.x audit) — it gets a voice wherever the user is
      toast(t("the update download failed: {why}",
              { why: humanErr(UPD_DL.error || "") || UPD_DL.error || t("unknown reason") }),
            "bad");
    }
  }, 900);
}

/** The ready door as a notice: sticky, one tap, and it names the real
 *  action per shell — restarting the app alone installs nothing. */
function announceUpdateReady() {
  if (document.querySelector(".toast.update-ready")) return;
  toast(t("the update is downloaded and verified"), "info update-ready", {
    sticky: true,
    actions: [{ label: ANDROID() ? t("Install now") : t("Restart & Install"),
                prime: true, onClick: installStagedUpdate }],
  });
}

/** Abort a staged download the user no longer wants: the worker stops
 *  between chunks, leaves nothing behind, and the row resets to idle. */
async function cancelUpdateDownload() {
  try { UPD_DL = await api("/update/cancel", { method: "POST" }); } catch (_) {}
  renderUpdateRow();
  pollUpdateStatus();     // settles in idle on its own and stops
}

/** Back from Android's settings detour: if the permission is granted
 *  now, put the door back in front of the user (v0.41.x audit). */
function checkUpdatePermResume() {
  if (!UPD_PERM_WAIT || !ANDROID()) return;
  if (!UPD_DL || UPD_DL.status !== "ready") { UPD_PERM_WAIT = false; return; }
  if (window.AndroidHost && window.AndroidHost.canInstallPackages &&
      window.AndroidHost.canInstallPackages()) {
    UPD_PERM_WAIT = false;
    announceUpdateReady();
  }
}

/** The ready-state door: installer here, system installer on Android,
 *  release page everywhere else. */
async function installStagedUpdate() {
  const st = UPD_DL || {};
  if (ANDROID() && window.AndroidHost && window.AndroidHost.installApk) {
    try {
      if (window.AndroidHost.canInstallPackages &&
          !window.AndroidHost.canInstallPackages()) {
        // the OS settings detour used to end in a dead-end: remember that
        // we sent the user away, and greet them on the way back (audit)
        UPD_PERM_WAIT = true;
        toast(t("let suravidl install updates, then tap Install again"));
        if (window.AndroidHost.openInstallPermissionSettings)
          window.AndroidHost.openInstallPermissionSettings();
        return;
      }
      window.AndroidHost.installApk(st.name);
      return;
    } catch (e) {
      // never silently eject to a browser: say what failed first (audit)
      toast(t("could not launch the installer: {msg}",
              { msg: (e && e.message) || t("unknown reason") }), "bad");
      return;
    }
  }
  // the desktop shells hand the staged file to /update/apply; each shell
  // installs its own way (Windows: the silent setup; macOS: the bundle
  // swap) — one list, so a third shell cannot be forgotten
  const DESKTOP_APPLY_KINDS = ["windows_installer", "macos_app_zip"];
  if (!ANDROID() && UPD_STATE &&
      DESKTOP_APPLY_KINDS.indexOf(UPD_STATE.apply_kind) !== -1) {
    try {
      const r = await api("/update/apply", { method: "POST" });
      if (r.ok) { toast(t("restarting to install…")); return; }
      toast(r.reason || t("could not start the installer"), "bad");
    } catch (e) {
      toast(t("could not start the installer: {msg}", { msg: e.message }), "bad");
    }
    return;
  }
  openExternal((UPD_STATE && UPD_STATE.url) || RELEASES_LATEST);
}

/* a real state change in the courier row refreshes with the house fade;
   poll ticks (same state, new numbers) stay crisp (v0.42.1) */
function _restartSwap(node) {
  if (!node) return;
  node.classList.remove("swap");
  void node.offsetWidth;
  node.classList.add("swap");
}
let UPD_LAST_BUCKET = null;

/** Settings → Updates, courier edition: one row walks the whole flow. */
function renderCourierRow(u, els, when, skipped) {
  const { state, meta, get, skip, man } = els;
  const st = UPD_DL || { status: "idle" };
  if (UPD_LAST_BUCKET !== null && st.status !== UPD_LAST_BUCKET) {
    // idle → downloading → ready: one house fade over the row and its meta
    // (v0.42.1 — buttons used to hard-swap mid-poll)
    _restartSwap(state.parentElement);
    _restartSwap(meta);
  }
  UPD_LAST_BUCKET = st.status;
  state.textContent = t("suravidl {v} is available", { v: u.latest });
  const base = t("you have {v} · {when}", { v: u.current, when: when })
    + (skipped ? " · " + t("skipped") : "");
  // the skip toggle stays reachable in every resting state; the manual
  // release-page door is a button of its own now — it used to squat on
  // skip, so "Skip this version" (and its undo) became unreachable in
  // Settings (v0.41.x audit)
  const skipToggle = () => {
    skip.textContent = skipped ? t("Stop skipping") : t("Skip this version");
    skip.classList.remove("hidden");
    skip.onclick = () => {
      updStore.set(UPD.skipped, skipped ? "" : u.latest);
      renderUpdateRow();
    };
  };
  if (st.status === "downloading" || st.status === "verifying") {
    if (st.status === "downloading") {
      const pct = updPct(st);
      meta.textContent = t("downloading… {detail}", {
        detail: pct == null ? humanBytes(st.bytes || 0)
          : t("{pct}% of {size}", { pct: pct, size: humanBytes(st.total) }),
      });
      get.textContent = t("Downloading…");
    } else {
      meta.textContent = t("verifying the download…");
      get.textContent = t("Verifying…");
    }
    get.disabled = true;
    get.classList.remove("hidden");
    get.onclick = null;
    // the one way out of a download the user regrets: the engine aborts
    // between chunks and leaves nothing behind (v0.41.x audit)
    skip.textContent = t("Cancel download");
    skip.classList.remove("hidden");
    skip.onclick = cancelUpdateDownload;
    man.classList.add("hidden");
  } else if (st.status === "ready") {
    meta.textContent = t("{base} · downloaded and verified", { base: base });
    get.textContent = ANDROID() ? t("Install update") : t("Restart & Install");
    get.disabled = false;
    get.classList.remove("hidden");
    get.onclick = installStagedUpdate;
    skip.classList.add("hidden");
    man.classList.add("hidden");
  } else if (st.status === "failed") {
    // same words as every other refusal, same rose (v0.41.x audit)
    meta.classList.add("bad");
    meta.textContent = t("the download failed: {why}",
        { why: humanErr(st.error || "") || st.error || t("unknown reason") })
      + " · " + base;
    get.textContent = t("Try again");
    get.disabled = false;
    get.classList.remove("hidden");
    get.onclick = startUpdateDownload;
    skipToggle();
    man.classList.remove("hidden");
    man.onclick = () => openExternal(u.url);
  } else {
    meta.textContent = base;
    get.textContent = t("Update to {v}", { v: u.latest });
    get.disabled = false;
    get.classList.remove("hidden");
    get.onclick = startUpdateDownload;
    skipToggle();
    man.classList.remove("hidden");
    man.onclick = () => openExternal(u.url);
  }
}

/** Resume the row's truth after a reload: the engine remembers the stage. */
async function syncStagedUpdate() {
  try {
    const st = await api("/update/status");
    if (st && st.status !== "idle") {
      UPD_DL = st;
      renderUpdateRow();
      if (st.status === "downloading" || st.status === "verifying") pollUpdateStatus();
      // a reload while the update is ready keeps the door in front of the
      // user instead of hiding it in a Settings row (v0.41.x audit)
      else if (st.status === "ready") announceUpdateReady();
    }
  } catch (_) { /* the row keeps its last truth */ }
}

/** force = the user pressed Check now: show the notice even if skipped/snoozed. */
async function checkAppUpdate(force) {
  try {
    const u = await api("/update-check");
    UPD_STATE = u;
    // a frozen/Android build bundles yt-dlp and has no pip — the update
    // button must say where updates come from instead of failing (v0.40.10)
    if (u.bundled && $("updateBtn")) {
      // v0.43.0: packaged builds fetch the newest release from PyPI
      // (sha256-verified) and it applies from the next start — nothing
      // to disable any more, the tooltip just says where it comes from
      $("updateBtn").title = t(
        "packaged build: fetches the newest yt-dlp from PyPI, verified — applies on next start");
    }
    updStore.set(UPD.last, JSON.stringify({
      at: Date.now(), latest: u.latest || null,
      available: !!u.update_available, error: u.error || null,
    }));
    renderUpdateRow();
    if (!u.update_available || !u.url || u.error) return;
    const skipped = updStore.get(UPD.skipped, "") === u.latest;
    const until = Number(updStore.get(UPD.snooze, "0")) || 0;
    if (force || (!skipped && Date.now() >= until)) showUpdateBanner(u);
  } catch (e) {
    updStore.set(UPD.last, JSON.stringify({
      at: Date.now(), latest: null, available: false,
      error: t("the engine did not answer"),
    }));
    renderUpdateRow();
  }
}

function wireUpdateRow() {
  const b = $("updCheck");
  if (!b) return;
  b.onclick = async () => {
    const old = b.textContent;
    b.disabled = true;
    b.textContent = t("checking…");
    await checkAppUpdate(true);
    b.disabled = false;
    b.textContent = old;
    if (UPD_STATE && UPD_STATE.error)
      toast(t("update check failed: {msg}", { msg: UPD_STATE.error }), "bad");
    else if (UPD_STATE && !UPD_STATE.update_available)
      toast(t("you're on the latest version ({v})", { v: UPD_STATE.current }));
  };
  renderUpdateRow();
  syncStagedUpdate();   // a staged download survives a page reload
}

/** Open a link outside the app shell: host bridge -> desktop opener -> browser. */
function openExternal(url) {
  if (!url) return;
  if (window.AndroidHost && window.AndroidHost.openUrl) {
    try { window.AndroidHost.openUrl(url); return; } catch (_) { /* fall through */ }
  }
  if (APP_INFO && APP_INFO.can_open_url) {
    api("/app/open-url", { method: "POST", body: JSON.stringify({ url }) })
      .catch((e) => toast(t("could not open browser: {msg}", { msg: e.message }), "bad"));
    return;
  }
  window.open(url, "_blank", "noopener");
}

$("removeBtn").onclick = async () => {
  const ok = await askConfirm(
    t("Remove the downloaded yt-dlp copy? suravidl goes back to the copy bundled with the app (from the next start)."),
    { okText: t("Remove"), danger: true });
  if (!ok) return;
  $("removeBtn").disabled = true;
  try {
    const r = await api("/ytdlp/remove", { method: "POST" });
    loadVersions();
    if (r.pending)
      toast(t("removal is set — the downloaded copy goes at the next start"));
    else if (r.was_active)
      toast(t("downloaded copy removed — bundled yt-dlp from the next start"));
    else if (r.removed) toast(t("staged copy removed"));
    else toast(t("nothing to remove"));
  } catch (e) {
    toast(t("could not remove: {msg}", { msg: e.message }), "bad");
  } finally {
    $("removeBtn").disabled = false;
  }
};

$("updateBtn").onclick = async () => {
  const ok = await askConfirm(
    t("Update yt-dlp? The newest release is fetched and verified — packaged builds apply it on the next start."),
    { okText: t("Update"), danger: false });
  if (!ok) return;
  $("updateBtn").disabled = true;
  const old = $("updateBtn").textContent;
  $("updateBtn").textContent = t("updating…");
  try {
    const r = await api("/update", { method: "POST" });
    loadVersions();          // the tab shows the version next to this button
    if (r.updated && r.restart)
      toast(t("yt-dlp {v} is staged — restart to use it", { v: r.after }));
    else if (r.updated) toast(t("yt-dlp updated → {v}", { v: r.after }));
    else if (r.ok === false)
      toast(t("update failed: {msg}", { msg: r.detail || t("unknown") }), "bad");
    else toast(t("yt-dlp already latest ({v})", { v: r.after }));
  } catch (e) {
    toast(t("update failed: {msg}", { msg: e.message }), "bad");
  }
  $("updateBtn").textContent = old;
  $("updateBtn").disabled = false;
};

/* ---------- what's new ----------------------------------------------------- *
 * One card per DEVICE after an update: the engine answers with its version and
 * the notes for recent releases, and the UI shows the entries newer than the
 * last version this device has seen (localStorage — the same per-device
 * durability as the update skip/snooze; the Android WebView origin is fixed,
 * so it survives there). A device that has never seen a card gets the CURRENT
 * release's notes — the very first one; after that it is strictly what is new
 * to it. The card waits for "Got it": until then, the next launch asks again. */
const WN = {
  seen: "suravidl.whatsnew.seen", // the engine version this device has seen
  MAX: 3,                         // entries shown for one update, newest first
};

/** "0.32.0" -> [0, 32, 0]; junk floors at 0 so it only ever ranks below real versions. */
function versionTuple(v) {
  return String(v || "").split(".").map((x) => {
    const n = parseInt(x, 10);
    return Number.isFinite(n) ? n : 0;
  });
}

/** a > b ? 1 : a < b ? -1 : 0 — element by element, missing parts are 0. */
function versionCmp(a, b) {
  const A = versionTuple(a), B = versionTuple(b);
  for (let i = 0; i < Math.max(A.length, B.length); i++) {
    const d = (A[i] || 0) - (B[i] || 0);
    if (d) return d > 0 ? 1 : -1;
  }
  return 0;
}

/** The entries this device has not seen yet, newest first, capped. */
function whatsNewFor(seen, entries) {
  const pick = [];
  for (const e of entries || []) {
    if (!e || !e.version) continue;
    if (versionCmp(e.version, seen) <= 0) continue;
    pick.push(e);
    if (pick.length >= WN.MAX) break;
  }
  return pick;
}

function showWhatsNew(entries, version) {
  const box = $("whatsNewList");
  box.innerHTML = "";
  for (const e of entries) {
    const sec = document.createElement("div");
    sec.className = "wnentry";
    const head = document.createElement("div");
    head.className = "wntitle";
    head.textContent = e.title ? `${e.version} — ${e.title}` : e.version;
    sec.appendChild(head);
    const ul = document.createElement("ul");
    for (const item of e.items || []) {
      const li = document.createElement("li");
      li.textContent = item;
      ul.appendChild(li);
    }
    sec.appendChild(ul);
    box.appendChild(sec);
  }
  $("whatsNewDone").onclick = () => dismissWhatsNew(version);
  $("whatsNewClose").onclick = () => dismissWhatsNew(version);
  // Escape and the backdrop close it like every other dialog (v0.38.3
  // audit #2 — it used to toggle `hidden` directly, with no exit transition
  // and no keyboard way out)
  wnVersion = version;
  const modal = $("whatsNewModal");
  modal.onclick = (e) => { if (e.target === modal) dismissWhatsNew(version); };
  openModal(modal);
  $("whatsNewDone").focus({ preventScroll: true });
}

/** Record on dismiss: until "Got it" is pressed, the next launch asks again. */
function dismissWhatsNew(version) {
  wnVersion = null;
  if (version) updStore.set(WN.seen, version);
  closeModal($("whatsNewModal"));
}

async function maybeShowWhatsNew() {
  let data;
  try { data = await api("/whats-new"); } catch (_) { return; }
  const seen = updStore.get(WN.seen, "");
  if (seen === data.version) return;
  // never seen a card: the current release introduces itself; afterwards it
  // is strictly the entries newer than what this device last ran
  const pick = seen ? whatsNewFor(seen, data.entries)
                    : (data.entries || []).slice(0, 1);
  if (!pick.length) { updStore.set(WN.seen, data.version); return; }
  showWhatsNew(pick, data.version);
}

async function openWhatsNew() {
  let data;
  try { data = await api("/whats-new"); }
  catch (_) { toast(t("could not fetch what's new"), "bad"); return; }
  const pick = (data.entries || []).filter((e) => e && e.version === data.version);
  if (!pick.length) { toast(t("nothing new to show")); return; }
  showWhatsNew(pick, data.version);
}

function wireWhatsNewRow() {
  const b = $("wnOpen");
  if (b) b.onclick = openWhatsNew;
}

/* ---------- window controls (desktop app) / host controls (android app) ---------- */
function wireQuitButton() {
  const quit = $("quitBtn");
  quit.classList.remove("hidden");
  quit.onclick = async () => {
    const ok = await askConfirm(
      t("Quit suravidl? Active downloads will be interrupted."),
      { okText: t("Quit") });
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

/** Does this host give finished downloads a Gallery/Music copy?
 *
 *  The host answers, because only it knows: below Android 10 (API 29) there is
 *  no scoped storage, the app's own folder is already browsable, and the import
 *  is skipped — so promising "Gallery → suravidl" there sends the user looking
 *  for something that was never written. */
function GALLERY() {
  if (!ANDROID()) return false;
  try { return !!window.AndroidHost.galleryExport(); } catch (_) { return false; }
}

/** Android's app folder lives under Android/data/, which no file manager will
 *  open on Android 11+ — so say where the user can actually find their files
 *  (the gallery/music copies the app adds), and keep the raw path one tap away. */
/* ---------- the welcome mat: FAQ + tour (v0.39.4) --------------------------
   Two quiet doors in the footer row: answers to the questions this app keeps
   receiving, and a short walk over the parts of the room. The copy is plain
   on purpose — nothing in here should need a manual. */
const FAQ = [
  ["Where do my downloads go?",
   "The folder shown at the bottom of the screen — press Open folder next to it. On a phone, finished downloads get Open and Share buttons instead; files land in Gallery (video) or Music (audio) under suravidl."],
  ["A link says 'unsupported URL'. What now?",
   "Some pages cannot hand a plain link over. Play it in your browser for a second: the extension (on desktop) or the browser offer right here catches the stream, and you pick the quality here before anything downloads."],
  ["A page keeps bouncing me at ads.",
   "The phone app's built-in browser refuses off-site jumps and pop-ups while you hunt for a stream — the page, and the find list, stay put. If a refused hop was one you meant, tap the note on screen to follow it anyway."],
  ["A site asks me to turn off my ad blocker.",
   "The phone app's browser serves a few known ad networks empty, and some pages notice. In its second row there is an 'ads blocked / ads allowed' switch — flip it and reload. The off-site jump and pop-up guard keeps working either way."],
  ["Why does it use my browser's cookies?",
   "Signed-in sites — private videos, member areas — only serve files to a signed-in session. The extension passes the session details for exactly the stream you picked, nothing else, and Settings → Authentication shows what is held and clears it on ask."],
  ["Where are the cookies kept?",
   "On this machine alone, in the app's own data folder, readable only by your user account. They never leave your devices."],
  ["The extension finds nothing, or says the app isn't running.",
   "Update both sides first, and pair them once: the token from Settings → Authentication goes into the extension's Options. They find each other along a short row of nearby ports, so a busy port is fine. If the popup was open while the app started, press Check again."],
  ["A site won't offer 1080p or 4K.",
   "That is the site, not the app: some pages publish only up to a certain quality, or as separate video and audio streams — suravidl merges separate streams automatically."],
  ["A link or a direct stream — which one do I paste?",
   "Links go through the full lookup (playlists, subtitles, chapters and all). A direct mp4/m3u8 address skips the lookup, for anything already playing in front of you."],
  ["A download failed — how do I see why?",
   "Turn Verbose log on in the yt-dlp tab, let the job run again, then press View log: the last lines yt-dlp said are there, ready to copy. The log lives in memory only — it dies with the app."],
  ["How do I update?",
   "Settings → General checks for a new release and installs it — Check now, then Get it. The browser extension updates itself through Mozilla once the new version clears review."],
];

function buildFaqList() {
  const box = $("faqList");
  if (!box) return;
  // one painter for the list: boot builds it lazily, a language switch asks
  // it to repaint (relabelUI), so the two can never drift
  box.replaceChildren();
  for (const [q, a] of FAQ) {
    const it = document.createElement("details");
    it.className = "faq-item";
    const s = document.createElement("summary");
    s.textContent = t(q);
    const wrap = document.createElement("div");
    wrap.className = "faq-body";   // the FAQ folds like the deck's bay door
    wrap.append(el("p", "muted", t(a)));
    it.append(s, wrap);
    box.append(it);
  }
  box.querySelectorAll(".faq-item").forEach((it) =>
    wireBayDoor(it, it.querySelector(".faq-body")));
}

function openFaq() {
  const box = $("faqList");
  if (box && !box.childElementCount) buildFaqList();
  openModal($("faqModal"));
}

/* The tour points at the places a first run actually shows, so every step
   lands even before anything has been probed. A target this device does not
   show (the rail on a phone) is skipped silently, never pointed at thin air. */
const TOUR = [
  { tab: "download", sel: "#url", title: "Paste any video link",
    body: "Any site yt-dlp knows, or a direct mp4/m3u8 stream — then press Probe." },
  { sel: "#probeBtn", title: "Probe reads the page",
    body: "The real formats, quality, codecs and subtitles — what the site actually offers." },
  { sel: "#dlEmpty", title: "The deck fills up here",
    body: "After a probe this area lists the real formats: take one, or arm a take for the transport below." },
  { sel: "#transport", title: "START commits a take",
    body: "The armed take rides down here. START begins the download; Studio opens the extra options." },
  { tab: "queue", sel: "#jobs", title: "The queue",
    body: "Progress, speed and a live receipt for everything you start." },
  { sel: "#binsRail", title: "Filed takes",
    body: "Finished downloads land in this rail — click one to play it." },
  { tab: "settings", sel: "#settingsTabs", title: "Settings holds the rest",
    body: "Cookies, tools, updates, appearance — and the yt-dlp tab lists every option the engine takes." },
  { tab: "download", sel: ".footrow", title: "Questions live down here",
    body: "FAQ has the common answers; this tour replays from the same row whenever you like." },
];
let TOUR_ON = false;
let TOUR_STEP = 0;

function tourPlace() {
  const step = TOUR[TOUR_STEP];
  if (!step || !TOUR_ON) return;
  const target = document.querySelector(step.sel);
  const r = target && target.getBoundingClientRect ? target.getBoundingClientRect() : null;
  if (!r || r.width < 2 || r.height < 2) {
    // a target this device does not show: move on, never point at nothing
    TOUR_STEP += 1;
    return TOUR_STEP >= TOUR.length ? tourEnd() : tourShow();
  }
  const ring = $("tourRing");
  const card = $("tourCard");
  const pad = 8;
  ring.style.left = Math.round(r.left - pad) + "px";
  ring.style.top = Math.round(r.top - pad) + "px";
  ring.style.width = Math.round(r.width + pad * 2) + "px";
  ring.style.height = Math.round(r.height + pad * 2) + "px";
  const cw = Math.min(380, window.innerWidth - 24);
  card.style.width = cw + "px";
  card.style.left = Math.round(Math.min(Math.max(12, r.left), window.innerWidth - cw - 12)) + "px";
  let y = r.bottom + 14;
  if (y + 190 > window.innerHeight) y = Math.max(12, r.top - 200);
  card.style.top = Math.round(y) + "px";
}

function tourShow() {
  const step = TOUR[TOUR_STEP];
  if (!step || !TOUR_ON) return;
  if (step.tab) showTab(step.tab);
  $("tourTitle").textContent = t(step.title);
  $("tourBody").textContent = t(step.body);
  $("tourCount").textContent = t("{i} of {n}", { i: TOUR_STEP + 1, n: TOUR.length });
  $("tourNext").textContent = TOUR_STEP === TOUR.length - 1 ? t("Done") : t("Next");
  // every step lands with the primary button focused: the walk is
  // keyboard-complete, not just keyboard-startable (v0.41.x audit)
  try { $("tourNext").focus({ preventScroll: true }); } catch (_) {}
  const target = document.querySelector(step.sel);
  if (target && target.scrollIntoView) target.scrollIntoView({ block: "center" });
  requestAnimationFrame(tourPlace);
}

function tourNext() {
  if (TOUR_STEP >= TOUR.length - 1) return tourEnd();
  TOUR_STEP += 1;
  tourShow();
}

function tourBack() {
  if (TOUR_STEP <= 0) return;
  TOUR_STEP -= 1;
  tourShow();
}

function tourEnd() {
  TOUR_ON = false;
  $("tourShade").classList.add("hidden");
  window.removeEventListener("resize", tourPlace);
  window.removeEventListener("scroll", tourPlace, true);
}

function startTour() {
  TOUR_ON = true;
  TOUR_STEP = 0;
  $("tourShade").classList.remove("hidden");
  window.addEventListener("resize", tourPlace);
  window.addEventListener("scroll", tourPlace, true);
  tourShow();
}

function wireWelcome() {
  const on = (id, fn) => { const b = $(id); if (b) b.onclick = fn; };
  on("faqBtn", openFaq);
  on("tourBtn", startTour);
  on("faqClose", () => closeModal($("faqModal")));
  on("faqDone", () => closeModal($("faqModal")));
  on("tourSkip", tourEnd);
  on("tourBack", tourBack);
  on("tourNext", tourNext);
}

// the tour declares itself a modal dialog, so it must behave like one:
// Escape closes it and Tab cycles inside the card (v0.41.x audit — focus
// used to wander into the page behind the shade)
document.addEventListener("keydown", (e) => {
  if (!TOUR_ON) return;
  if (e.key === "Escape") { e.preventDefault(); tourEnd(); return; }
  if (e.key !== "Tab") return;
  const f = $("tourCard") ? $("tourCard").querySelectorAll("button") : [];
  if (!f.length) return;
  const first = f[0], last = f[f.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault(); last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault(); first.focus();
  }
}, true);

function renderWhere(dir) {
  const d = dir || "";
  $("dlDir").textContent = d;
  if (ANDROID()) {
    const gallery = GALLERY();
    $("dlWhere").textContent = gallery
      ? t("saved where you can open it — Gallery → suravidl (audio: Music → suravidl)")
      : t("saved in the app's folder — use Open or Share on a finished download");
    $("dlDir").title = gallery
      ? t("the app's own folder (not browsable): {path}", { path: d })
      : t("the app's folder (reachable by file managers on this Android): {path}", { path: d });
  } else {
    $("dlWhere").textContent = t("downloads");
  }
}

function wireCopyPath() {
  const b = $("copyDir");
  if (!b) return;
  b.onclick = async () => {
    const ok = await copyText($("dlDir").textContent || "");
    toast(ok ? t("path copied") : t("copy failed"), ok ? "ok" : "bad");
  };
}

async function initAppControls() {
  if (window.AndroidHost) {
    // inside the Android app: quit + battery settings, no minimize
    // (re-applied here too: the bridge may only appear after first paint)
    document.documentElement.dataset.host = "android";
    wireQuitButton();
    $("androidSection").classList.remove("hidden");
    $("tabDevice").classList.remove("hidden");
    $("batteryBtn").onclick = () => window.AndroidHost.openBatterySettings();
    $("quitAppBtn").onclick = () => $("quitBtn").onclick();
    // browser cookie DBs aren't readable on Android — offer file import instead
    $("browserRow").classList.add("hidden");
    $("impersonateRow").classList.add("hidden");   // no curl_cffi on the phone
    // the phone's two routes, said in its own terms: the app browser's session,
    // or a cookies.txt exported from a desktop browser (the encrypted import)
    const authHintEl = $("authHint");
    if (authHintEl) {
      authHintEl.textContent = t("Two routes: sign in to the site in “Find a video on a page” — that session goes with the download — or import a cookies.txt exported from a desktop browser (encrypted on this device). Instagram sessions expire in hours — re-import when a download asks for a sign-in.");
    }
    const imp = $("importCookies");
    imp.classList.remove("hidden");
    imp.onclick = () => window.AndroidHost.pickCookiesFile();
    // a page yt-dlp has no extractor for still has a player: this opens our own
    // browser with a sniffer attached (Android has no extensions — the browser
    // *is* the extension). Hidden on any host that cannot do it.
    if (window.AndroidHost.openBrowser) {
      $("sniffRow").classList.remove("hidden");
      $("sniffBtn").onclick = () => {
        try { window.AndroidHost.openBrowser(($("url").value || "").trim()); } catch (_) { }
      };
    }
    initVaultSection();
    initStorageSection();
    return;
  }
  try {
    const info = await api("/app/info");
    APP_INFO = info;
    if (!info.desktop) return;
    DESKTOP = true;
    const revealField = $("revealField");
    if (revealField) revealField.classList.remove("hidden");   // desktop-only row
    if (info.can_minimize) {
      const min = $("minBtn");
      min.classList.remove("hidden");
      min.onclick = () => api("/app/minimize", { method: "POST" })
        .catch((e) => toast(t("could not minimize: {msg}", { msg: e.message }), "bad"));
    }
    if (info.can_pick_file) {
      const browse = $("browseCookies");
      browse.classList.remove("hidden");
      browse.onclick = async () => {
        try {
          const { path } = await api("/app/pick-file", { method: "POST" });
          if (path) {
            $("setCookies").value = path;
            toast(t("selected — press Save"));
          }
        } catch (e) {
          toast(t("file picker unavailable: {msg}", { msg: e.message }), "bad");
        }
      };
    }
    if (info.can_pick_folder) {
      const browse = $("browseDir");
      browse.classList.remove("hidden");
      browse.onclick = async () => {
        try {
          const { path } = await api("/app/pick-folder", { method: "POST" });
          if (path) {
            $("setDir").value = path;
            toast(t("selected — press Save"));
          }
        } catch (e) {
          toast(t("file picker unavailable: {msg}", { msg: e.message }), "bad");
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
    catch (_) { $("vaultStatus").textContent = t("status unavailable"); }
  };
  show();
  $("deleteCookiesBtn").onclick = async () => {
    // the wipe is irreversible — same ask as every other delete (v0.44.x audit)
    if (!(await askConfirm(t("Delete the stored cookies from this device?"),
                           { okText: t("Delete") }))) return;
    try { window.AndroidHost.deleteCookies(); } catch (_) { }
    $("setCookies").value = "";
    api("/settings", { method: "POST", body: JSON.stringify({ cookies_file: "" }) })
      .catch(() => { });
    toast(t("stored cookies deleted"));
    show();
  };
}

/** Android: storage row in Settings → Device — how much is downloaded, and a
 *  way to delete it, because the folder (Android/data/…) is unreachable. */
let refreshStorageInfo = null;   // set below; re-read on tab open and deletes

async function initStorageSection() {
  const sec = $("storageSection");
  if (!sec) return;
  sec.classList.remove("hidden");
  const show = async () => {
    try {
      const s = await api("/files/summary");
      $("storageInfo").textContent = s.files
        ? (s.files === 1 ? t("1 file") : t("{n} files", { n: s.files }))
          + " · " + humanBytes(s.bytes)
        : t("no downloaded files");
      // the app cache (yt-dlp's player/signature data): counted apart from
      // the downloads, with its own button since v0.29.0
      const cache = typeof s.cache_bytes === "number" ? s.cache_bytes : 0;
      $("storageCache").textContent = cache
        ? t("app cache · {size}", { size: humanBytes(cache) })
        : t("app cache · empty");
    } catch (_) {
      $("storageInfo").textContent = t("size unavailable");
      $("storageCache").textContent = "";
    }
  };
  await show();
  refreshStorageInfo = show;
  // Two deletes, one flow (the 2026-09-26 ask): the app's own folder can be
  // emptied while the Gallery/Music copy — the one the user can actually
  // open — stays. That copy is removed by a separate host call, so the
  // app-copies path simply never makes it. Since v0.29.0 these only touch
  // files: the cache has its own button below.
  const clearFiles = async (keepGallery) => {
    const s = await api("/files/summary").catch(() => null);
    const known = s && typeof s.files === "number";
    // Nothing to delete: do not offer it. The row above could have read
    // "2 files · 73.2 MB" a minute ago (it is only re-read on tab open)
    // while a delete elsewhere emptied the folder — and "Delete 0 files
    // (0 B)?" against a row that says 2 is the consistency bug this fixes.
    if (known && s.files === 0) {
      toast(t("nothing to delete"));
      show();
      return;
    }
    const one = known && s.files === 1;
    const counted = known
      ? (one ? t("Delete 1 file ({size})", { size: humanBytes(s.bytes) })
             : t("Delete {n} files ({size})",
                 { n: s.files, size: humanBytes(s.bytes) }))
      : t("Delete every downloaded file");
    let msg;
    if (keepGallery) {
      msg = counted + " " + t("from the app's folder? The Gallery/Music copies stay.");
    } else if (known) {
      msg = counted +
        (GALLERY() ? " " + (one ? t("and its Gallery/Music copy")
                                : t("and their Gallery/Music copies")) : "") +
        t("? This cannot be undone.");
    } else {
      msg = counted + t("? (its size could not be read) This cannot be undone.");
    }
    const ok = await askConfirm(msg, { okText: t("Delete") });
    if (!ok) return;
    try {
      const r = await api("/files/clear", { method: "POST", body: JSON.stringify({ confirm: "delete" }) });
      if (!keepGallery && ANDROID() && window.AndroidHost.deleteMediaCopies) {
        try { window.AndroidHost.deleteMediaCopies(); } catch (_) { }
      }
      const parts = [];
      if (r.deleted > 0) {
        parts.push(r.deleted === 1 ? t("deleted 1 file")
                                   : t("deleted {n} files", { n: r.deleted }),
                   t("freed {size}", { size: humanBytes(r.freed_bytes) }));
      }
      if (keepGallery && GALLERY()) parts.push(t("Gallery/Music copies kept"));
      toast(parts.length ? parts.join(" · ") : t("nothing freed"));
      refreshJobs();
      show();
    } catch (e) {
      toast(t("could not delete: {msg}", { msg: e.message }), "bad");
    }
  };
  $("clearDownloadsBtn").onclick = () => clearFiles(false);
  $("clearAppCopiesBtn").onclick = () => clearFiles(true);
  // The distinction — and therefore this button — exists only where the host
  // actually writes gallery copies (Android 10+; the browser build has none).
  if (GALLERY()) $("clearAppCopiesBtn").classList.remove("hidden");
  // v0.29.0: the cache frees through its own endpoint, and it never touches
  // a download — the file deletes above no longer touch the cache either.
  $("clearCacheBtn").onclick = async () => {
    const s = await api("/files/summary").catch(() => null);
    const cacheBytes = s && typeof s.cache_bytes === "number" ? s.cache_bytes : 0;
    if (s && cacheBytes === 0) {
      toast(t("the app cache is already empty"));
      show();
      return;
    }
    const what = s && cacheBytes ? " (" + humanBytes(cacheBytes) + ")" : "";
    const ok = await askConfirm(
      t("Clear the app cache{what}? Player data yt-dlp simply fetches again — nothing downloaded is touched.",
        { what: what }), { okText: t("Clear") });
    if (!ok) return;
    try {
      const r = await api("/cache/clear", { method: "POST", body: JSON.stringify({ confirm: "delete" }) });
      toast(r.freed_bytes > 0
        ? t("cache cleared ({size})", { size: humanBytes(r.freed_bytes) })
        : t("cache was already empty"));
      show();
    } catch (e) {
      toast(t("could not clear the cache: {msg}", { msg: e.message }), "bad");
    }
  };
}

/* called back by the Android host after the cookies file is imported */
window.onCookiesPicked = (path) => {
  if (!path) {
    toast(t("cookies import failed"), "bad");
    return;
  }
  $("setCookies").value = path;
  saveSettings().then(() => toast(t("cookies imported"))).catch((e) =>
    toast(t("could not save: {msg}", { msg: e.message }), "bad"));
};

/* ---------- settings ---------- */
// a tab switch reloads Settings from the server (showTab); that must not wipe
// what the user typed but has not saved yet (v0.21.1 audit)
let SETTINGS_DIRTY = false;

/** A dot on the Settings tab while the form holds edits the engine has not
 *  been told about. The tab is a primary destination: someone who changes the
 *  template and walks away had no way to know the next download would still
 *  use the OLD values (motion review). */
function markSettingsDirty(on) {
  SETTINGS_DIRTY = on;
  const tab = document.querySelector('#tabs .tab[data-tab="settings"]');
  if (tab) tab.classList.toggle("has-dirty", on);
}

async function loadSettings() {
  try {
    const s = await api("/settings");
    SETTINGS_SNAPSHOT = s;
    CURRENT = { theme: s.theme, glass: s.glass, accent: s.accent };
    $("setDir").value = s.download_dir || "";
    $("setConc").value = s.max_concurrent;
    $("setReveal").checked = !!s.open_dir_on_complete;
    $("setResume").checked = !!s.auto_resume;
    $("setCookies").value = s.cookies_file || "";
    $("setCookiesBrowser").value = s.cookies_from_browser || "";
    $("setImpersonate").value = s.impersonate || "";
    $("setTemplate").value = s.filename_template || "";
    $("setSubfolders").value = s.subfolders || "off";
    $("setContainer").value = s.video_container || "auto";
    $("setLiveFromStart").checked = !!s.live_from_start;
    $("setSubSrt").checked = !!s.subtitles_to_srt;
    $("setEmbMeta").checked = !!s.embed_metadata;
    $("setEmbThumb").checked = !!s.embed_thumbnail;
    $("setSubMode").value = s.subtitles_mode || "off";
    $("setSubLangs").value = s.subtitles_langs || "";
    $("setSubAuto").checked = !!s.subtitles_auto;
    $("setSbMode").value = s.sponsorblock_mode || "off";
    $("setSbCats").value = s.sponsorblock_categories || "";
    $("setArchive").checked = !!s.archive;
    $("setFragments").value = s.fragments != null ? s.fragments : 1;
    $("setRetries").value = s.retries != null ? s.retries : 10;
    $("setMaxDownloads").value = s.max_downloads != null ? s.max_downloads : 0;
    $("setRateLimit").value = s.rate_limit || "";
    $("setProxy").value = s.proxy || "";
    $("setRawEnabled").checked = !!s.raw_args_enabled;
    $("setRawArgs").value = s.raw_args || "";
    renderRawAccess(!!s.raw_args_enabled);
    // curated groups (yt-dlp tab)
    $("setVerbose").checked = !!s.verbose;
    $("setIpVersion").value = s.ip_version || "auto";
    $("setNoCheckCerts").checked = !!s.no_check_certificates;
    $("setSleepRequests").value = Number(s.sleep_requests || 0);
    $("setGeoBypass").checked = !!s.geo_bypass;
    $("setGeoCountry").value = s.geo_bypass_country || "";
    $("setExtractorArgs").value = s.extractor_args || "";
    $("setLang").value = s.language === "id" ? "id" : "en";
    renderWhere(s.download_dir);
    renderDefaultPreset();
    markSwatches(CURRENT);
    markSettingsDirty(false);   // the form now mirrors the server
  } catch (e) {
    toast(t("could not load settings: {msg}", { msg: e.message }), "bad");
  }
}

/* ---------- settings sub-tabs ---------- */
function showSettingsTab(name) {
  const incoming = $("spanel-" + name);
  const cur = document.querySelector("#settingsTabs .stab.active");
  const wasOn = !!cur && cur.dataset.stab === name;
  document.querySelectorAll("#settingsTabs .stab").forEach((b) => {
    const on = b.dataset.stab === name;
    b.classList.toggle("active", on);
    b.setAttribute("aria-selected", on ? "true" : "false");
    b.tabIndex = on ? 0 : -1;   // one tab stop; arrows move (v0.44.x audit)
    // only a row that actually scrolls is worth centering — on a wrapped
    // phone row the old call nudged the page for nothing (v0.44.x audit)
    if (on && b.scrollIntoView) {
      const row = b.parentElement;
      try {
        if (row && row.scrollWidth > row.clientWidth + 4) {
          b.scrollIntoView({ inline: "center", block: "nearest" });
        }
      } catch (_) { /* older WebView */ }
    }
  });
  document.querySelectorAll(".spanel").forEach((p) =>
    p.classList.toggle("hidden", p.id !== "spanel-" + name));
  const ps = $("panel-settings");
  if (ps) ps.dataset.stab = name;   // the Save strip retires on the Device tab
  // v0.37.1: the swap dresses itself — the sub-tabs were the only navigation
  // in the app with no transition at all (2026-09-30); a re-tap doesn't re-run
  if (incoming && !wasOn) {
    incoming.classList.remove("spanel-in");
    void incoming.offsetWidth;   // restart the fade on a rapid re-switch
    incoming.classList.add("spanel-in");
  }
}
/* The sub-tabs follow the same APG pattern as the main deck (v0.44.x audit:
   they carried aria-selected only — one tab stop and arrow moves were
   missing, while the main tabs' comment claimed they already had them). */
function syncStabTabs() {
  const cur = document.querySelector("#settingsTabs .stab.active");
  const name = cur ? cur.dataset.stab : "general";
  document.querySelectorAll("#settingsTabs .stab").forEach((b) => {
    b.tabIndex = b.dataset.stab === name ? 0 : -1;
  });
  const ps = $("panel-settings");
  if (ps) ps.dataset.stab = name;
}
document.querySelectorAll("#settingsTabs .stab").forEach((b) => {
  b.onclick = () => showSettingsTab(b.dataset.stab);
  b.addEventListener("keydown", (e) => {
    const tabs = [...document.querySelectorAll("#settingsTabs .stab")]
      .filter((t) => !t.classList.contains("hidden"));
    const i = tabs.indexOf(b);
    let t = null;
    if (e.key === "ArrowRight") t = tabs[(i + 1) % tabs.length];
    if (e.key === "ArrowLeft") t = tabs[(i - 1 + tabs.length) % tabs.length];
    if (e.key === "Home") t = tabs[0];
    if (e.key === "End") t = tabs[tabs.length - 1];
    if (!t) return;
    e.preventDefault();
    showSettingsTab(t.dataset.stab);
    t.focus();
  });
});
syncStabTabs();

/* ---------- the shell: four tabs, hash-routed ---------- */
const TABS = ("download queue settings ytdlp").split(" ");

function showTab(name, opts) {
  const target = TABS.includes(name) ? name : "download";
  const current = document.body.dataset.tab;
  // the active tab on the body, so CSS can react to it (the mobile toast lane
  // needs to clear the Settings tab's pinned Save bar — theme review)
  document.body.dataset.tab = target;
  const panels = TABS.map((tab) => $("panel-" + tab)).filter(Boolean);
  const incoming = $("panel-" + target);
  // v0.37.1: the swap is immediate. It used to wait out the old screen's exit
  // fade and then wash the new one in over .4s — on a phone the next tab only
  // STARTED arriving after the previous one had finished leaving (2026-09-30
  // report). The arrival fade dresses the switch; it never delays it. Never on
  // first paint, and never when the target is already visible: the per-tab
  // refreshes at the end of this function call back into here and must not
  // restart the fade.
  const switching = !!(incoming && current && current !== target &&
    !panels.filter((p) => !p.classList.contains("hidden")).includes(incoming));
  panels.forEach((p) => p.classList.toggle("hidden", p !== incoming));
  if (switching) {
    incoming.classList.remove("tab-in");
    void incoming.offsetWidth;   // restart the fade on a rapid re-switch
    incoming.classList.add("tab-in");
  }
  TABS.forEach((tab) => {
    document.querySelectorAll(`#tabs .tab[data-tab="${tab}"]`).forEach((b) => {
      b.classList.toggle("active", tab === target);
      b.setAttribute("aria-selected", tab === target ? "true" : "false");
    });
  });
  if (location.hash.slice(1) !== target) {
    history.replaceState(null, "", "#" + target);
  }
  if (target === "settings" && !SETTINGS_DIRTY) loadSettings();
  // the storage row counts what is on disk — downloads land and deletes happen
  // while other tabs are up, so re-read it whenever Settings comes into view
  if (target === "settings" && refreshStorageInfo) refreshStorageInfo();
  if (target === "ytdlp") loadOptions(false);
  if (target === "queue") refreshJobs();
  if (!(opts && opts.keepScroll)) scrollTo({ top: 0, behavior: "instant" });
  syncTabA11y();
  syncToastLane();
}

/* The main deck's tabs follow the same APG pattern the Settings tabs already
   use (v0.40.10 audit): one tab stop, arrows move between tabs, aria-selected
   and tabindex follow the active panel. */
function syncTabA11y() {
  const active = document.body.dataset.tab || "download";
  document.querySelectorAll("#tabs .tab").forEach((b) => {
    const on = b.dataset.tab === active;
    b.setAttribute("aria-selected", on ? "true" : "false");
    b.tabIndex = on ? 0 : -1;
  });
}
document.querySelectorAll("#tabs .tab").forEach((b) => {
  b.onclick = () => showTab(b.dataset.tab);
  b.addEventListener("keydown", (e) => {
    const tabs = [...document.querySelectorAll("#tabs .tab")];
    const i = tabs.indexOf(b);
    let t = null;
    if (e.key === "ArrowRight") t = tabs[(i + 1) % tabs.length];
    if (e.key === "ArrowLeft") t = tabs[(i - 1 + tabs.length) % tabs.length];
    if (e.key === "Home") t = tabs[0];
    if (e.key === "End") t = tabs[tabs.length - 1];
    if (!t) return;
    e.preventDefault();
    t.focus();
    showTab(t.dataset.tab);
  });
});
syncTabA11y();

/* The forecourt rule: an empty URL box means START is not a live control
   (v0.40.10 audit — a scold toast was doing a disabled state's job). The
   start-without-probe path stays a feature: only emptiness disables it. */
function syncStartState() {
  const empty = !$("url").value.trim();
  $("bestBtn").disabled = empty;
}
$("url").addEventListener("input", syncStartState);
syncStartState();
// moved off initFolderSheet (v0.44.x audit): a download-deck control must not
// ride an Android folder-sheet initializer
$("noSound").addEventListener("change", refreshSoundLabels);

/* ---------- yt-dlp tab: curated groups + option browser ---------- */
let OPTIONS = null;

async function loadOptions(force) {
  if (OPTIONS && !force) { renderOptions($("optionsSearch").value); return; }
  $("optionsList").textContent = t("loading…");
  try {
    const r = await api("/options");
    OPTIONS = r.options || [];
    $("optionsCount").textContent = t("{n} options", { n: r.count });
  } catch (e) {
    $("optionsList").textContent = t("could not load options: {msg}", { msg: e.message });
    return;
  }
  renderOptions($("optionsSearch").value);
}

async function openOptionsBrowser() {
  showTab("ytdlp");
  await loadOptions(false);
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
    const add = () => {
      const ta = $("setRawArgs");
      ta.value = (ta.value.trim() + " " +
        (o.takes_value ? `${o.name} ${o.metavar || "VALUE"}` : o.name)).trim();
      $("setRawEnabled").checked = true;
      renderRawAccess(true);
      toast(t("added {name} — save to keep it", { name: o.name }));
    };
    row.onclick = add;
    makeOptionRowReachable(row, add);
    box.append(row);
  }
  if (!list.length) box.append(el("div", "muted small", t("nothing matches that search")));
  $("optionsCount").textContent = q
    ? (list.length === 1 ? t("1 match") : t("{n} matches", { n: list.length }))
    : t("{n} options", { n: (OPTIONS || []).length });
}

/** Raw arguments only matter once enabled in Settings → Advanced. */
function renderRawAccess(enabled) {
  $("rawEditor").classList.toggle("hidden", !enabled);
  $("rawOffHint").classList.toggle("hidden", !!enabled);
  $("ovRawRow").classList.toggle("hidden", !enabled);
}

/* --- presets: named bundles the user saves and reuses --------------------- */

let PRESETS = [];          // [{name, patch, builtin, description}]

let PRESETS_ERROR = null;   // set when /presets could not be read: a server
                            // failure must not look like "you have no presets"
async function loadPresets() {
  try {
    const data = await api("/presets");
    PRESETS = data.presets || [];
    OV.defaults = data.defaults || {};
    OV.perJobKeys = data.per_job_keys || [];
    OV.qualities = data.qualities || [];
    PRESETS_ERROR = null;
  } catch (e) {
    PRESETS = [];
    PRESETS_ERROR = (e && e.message) || "no answer";
  }
  renderOvPresets();
  renderPresetList();
  renderOvPresetInfo();
  renderOvPresetActions();
}

/** The default-preset select (Settings → Presets): the permanent answer to
 *  "I always want this". It rides every NEW download; anything the download
 *  itself says — its own preset, a quality pick, per-download fields — still
 *  wins, the engine layers it that way (v0.36.0). */
function renderDefaultPreset() {
  const sel = $("defaultPreset");
  if (!sel) return;
  const stored = (SETTINGS_SNAPSHOT && SETTINGS_SNAPSHOT.default_preset) || "";
  const keep = sel.value || stored;
  sel.innerHTML = "";
  const none = el("option", "", t("none — use my settings"));
  none.value = "";
  sel.append(none);
  const groups = [[true, t("built-in")], [false, t("saved")]];
  for (const [builtin, label] of groups) {
    const items = (PRESETS || []).filter((p) => !!p.builtin === builtin);
    if (!items.length) continue;
    const group = document.createElement("optgroup");
    group.label = label;
    for (const p of items) {
      const o = el("option", "", p.name +
        (p.description ? " — " + p.description : ""));
      o.value = p.name;
      group.append(o);
    }
    sel.append(group);
  }
  if (keep && !Array.from(sel.options).some((o) => o.value === keep)) {
    // the setting outlived its preset (deleted later) — say so instead of
    // silently falling back to none
    const gone = el("option", "", t("“{name}” (no longer exists)", { name: keep }));
    gone.value = keep;
    sel.append(gone);
  }
  sel.value = keep;
  sel.onchange = async () => {
    const name = sel.value;
    try {
      const s = await api("/settings", {
        method: "POST", body: JSON.stringify({ default_preset: name }) });
      if (SETTINGS_SNAPSHOT) SETTINGS_SNAPSHOT.default_preset = s.default_preset;
      toast(name
        ? t("default preset: “{name}” rides every new download", { name: name })
        : t("default preset cleared — downloads use just your settings"));
    } catch (e) {
      toast(t("could not save: {msg}", { msg: e.message }), "bad");
      sel.value = stored;       // the control goes back to what is stored
    }
  };
}

function renderPresetList() {
  renderDefaultPreset();        // the select keeps step with the list — save,
                                // delete and load all land here (v0.36.0)
  const box = $("presetList");
  if (!box) return;
  box.innerHTML = "";
  if (!PRESETS.length) {
    if (PRESETS_ERROR) {
      box.append(el("div", "empty",
        t("could not load presets ({err}) —", { err: PRESETS_ERROR })));
      const again = el("button", "btn sm ghost-sm", t("retry"));
      again.onclick = () => loadPresets();
      box.append(again);
      box.append(el("div", "muted",
        t("your saved presets are not gone, they just could not be read")));
    } else {
      box.append(el("div", "empty", t("No presets yet — save one from your settings above, or from the download panel.")));
    }
    return;
  }
  for (const p of PRESETS) {
    const row = el("div", "optrow");
    const left = el("div", "col");
    left.append(el("span", "optname",
                   p.name + (p.builtin ? " " + t("(built-in)") : "")));
    const keys = Object.keys(p.patch || {});
    left.append(el("span", "optsum small muted",
      (p.description || keys.map((k) => `${k}=${p.patch[k]}`).join(" · ")).slice(0, 140)));
    row.append(left);
    if (!p.builtin) {
      const del = el("button", "ghost-sm del", t("Delete"));
      del.setAttribute("aria-label",
        t("Delete preset “{name}”", { name: p.name }));
      del.prepend(ico("trash"));
      del.onclick = async () => {
        if (!(await askConfirm(
          t("Delete the preset “{name}”? Downloads already started keep their options.",
            { name: p.name }), { okText: t("Delete") }))) return;
        try {
          await api(`/presets/${encodeURIComponent(p.name)}`, { method: "DELETE" });
          toast(t("preset deleted"));
          loadPresets();
        } catch (e) {
          toast(t("could not delete: {msg}", { msg: e.message }), "bad");
        }
      };
      row.append(del);
    }
    box.append(row);
  }
}

/** The patch "save my current settings" should store: what differs from the
 *  defaults, limited to the keys a single download may override. It reads
 *  the live form, not the disk (v0.44.x audit: fresh edits were missed). */
function presetPatchFromSettings() {
  const patch = {};
  const keys = OV.perJobKeys || [];
  const defaults = OV.defaults || {};
  const form = settingsFormPayload();
  for (const k of keys) {
    const v = form[k];
    if (v === undefined || v === null) continue;
    const d = defaults[k];
    const isDefault = Array.isArray(v) || typeof v === "object"
      ? JSON.stringify(v) === JSON.stringify(d)
      : v === d;
    if (!isDefault && v !== "") patch[k] = v;
  }
  return patch;
}

async function saveCurrentAsPreset() {
  const name = $("presetName").value.trim();
  const msg = $("presetMsg");
  const patch = presetPatchFromSettings();
  if (!Object.keys(patch).length) {
    msg.textContent = OV.perJobKeys
      ? t("Nothing to save yet — change a download option first (Settings → Media / Network).")
      : t("presets could not be loaded, so there is nothing to diff against — retry from Settings → Presets.");
    msg.className = OV.perJobKeys ? "msg warn" : "msg bad";
    return;
  }
  if (!name) {
    // the server refuses this too — say it here, without the round trip
    msg.textContent = t("a preset needs a name");
    msg.className = "msg warn";
    return;
  }
  try {
    await api("/presets", { method: "POST", body: JSON.stringify({ name, patch }) });
    msg.textContent = t("saved “{name}” with {n} option(s): {keys}",
      { name: name, n: Object.keys(patch).length,
        keys: Object.keys(patch).join(", ") });
    msg.className = "msg ok";
    $("presetName").value = "";
    loadPresets();
  } catch (e) {
    msg.textContent = t("could not save: {msg}", { msg: e.message });
    msg.className = "msg bad";
  }
}

$("optionsBtn").onclick = openOptionsBrowser;
$("optionsSearch").oninput = (e) => renderOptions(e.target.value);

/** Escape is the keyboard way out of Settings (the tab bar is the visible one). */
function closeSettings() {
  showTab("download");
}

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("confirmModal").classList.contains("hidden")) {
    return;   // the confirm dialog handles its own Escape
  }
  // the player and the folder sheet close themselves on Escape; without
  // these the same press ALSO ran closeSettings() below and yanked a
  // Settings user straight to the Download tab (v0.40.10 audit)
  if (!$("playModal").classList.contains("hidden")) return;
  if (!$("folderModal").classList.contains("hidden")) return;
  // a running tour: Escape leaves it (v0.39.4)
  if (TOUR_ON) { tourEnd(); return; }
  // the FAQ card answers on Escape like every dialog (v0.39.4)
  if (!$("faqModal").classList.contains("hidden")) { closeModal($("faqModal")); return; }
  // the what's-new card: a real dialog, so Escape is its way out (v0.38.3)
  if (wnVersion) { dismissWhatsNew(wnVersion); return; }
  // only when Settings is really open: this used to close it from any tab and
  // yank the user back to Download (v0.21.1 audit)
  const panel = $("panel-settings");
  if (panel && !panel.classList.contains("hidden")) closeSettings();
});

// the hash is a real address (reload lands on the same tab); when something
// else changes it — a link, a host gesture — follow it instead of disagreeing
window.addEventListener("hashchange", () => {
  const name = location.hash.slice(1);
  if (TABS.includes(name)) showTab(name);
});

document.querySelectorAll("#themeSwatches .swatch").forEach((b) => {
  b.onclick = () => setAppearance({ theme: b.dataset.theme },
    t("Theme: {name}", { name: b.querySelector(".sw-label").textContent }));
});
document.querySelectorAll("#glassSwatches .swatch").forEach((b) => {
  b.onclick = () => setAppearance({ glass: b.dataset.glass },
    t("Glass: {name}", { name: b.querySelector(".sw-label").textContent }));
});
document.querySelectorAll("#schemeSwatches .swatch").forEach((b) => {
  b.onclick = () => setAppearance({ accent: b.dataset.accent },
    t("Scheme: {name}", { name: b.querySelector(".sw-label").textContent }));
});
const langSel = $("setLang");
if (langSel) langSel.onchange = () => setLanguage(langSel.value);
wireMotionNote();

/** The settings form as an API payload — ONE builder, two readers: Save
 *  posts it, and the preset diff reads it, so "the current settings" means
 *  the form in front of the user, not the last disk write (v0.44.x audit:
 *  a preset saved after fresh edits recorded the stale snapshot). */
function settingsFormPayload() {
  return {
      download_dir: $("setDir").value.trim(),
      max_concurrent: Number($("setConc").value),
      open_dir_on_complete: $("setReveal").checked,
      auto_resume: $("setResume").checked,
      cookies_file: $("setCookies").value.trim(),
      cookies_from_browser: $("setCookiesBrowser").value,
      impersonate: $("setImpersonate").value,
      filename_template: $("setTemplate").value.trim(),
      subfolders: $("setSubfolders").value,
      video_container: $("setContainer").value,
      live_from_start: $("setLiveFromStart").checked,
      embed_metadata: $("setEmbMeta").checked,
      embed_thumbnail: $("setEmbThumb").checked,
      subtitles_mode: $("setSubMode").value,
      subtitles_langs: $("setSubLangs").value.trim(),
      subtitles_auto: $("setSubAuto").checked,
      subtitles_to_srt: $("setSubSrt").checked,
      sponsorblock_mode: $("setSbMode").value,
      sponsorblock_categories: $("setSbCats").value.trim(),
      archive: $("setArchive").checked,
      fragments: Number($("setFragments").value),
      retries: Number($("setRetries").value),
      max_downloads: Number($("setMaxDownloads").value),
      rate_limit: $("setRateLimit").value.trim(),
      proxy: $("setProxy").value.trim(),
      raw_args_enabled: $("setRawEnabled").checked,
      raw_args: $("setRawArgs").value.trim(),
      // curated groups (yt-dlp tab)
      verbose: $("setVerbose").checked,
      ip_version: $("setIpVersion").value,
      no_check_certificates: $("setNoCheckCerts").checked,
      sleep_requests: Number($("setSleepRequests").value || 0),
      geo_bypass: $("setGeoBypass").checked,
      geo_bypass_country: $("setGeoCountry").value.trim().toUpperCase(),
      extractor_args: $("setExtractorArgs").value.trim(),
  };
}

function saveSettings() {
  return api("/settings", {
    method: "POST",
    body: JSON.stringify(settingsFormPayload()),
  }).then((s) => {
    SETTINGS_SNAPSHOT = s;   // the preset diff reads this
    markSettingsDirty(false);  // the form was accepted as-is
    renderWhere(s.download_dir);
    // the engine clamps (0 -> 1, junk refused): show what it actually stored
    $("setConc").value = s.max_concurrent;
    $("setFragments").value = s.fragments;
    $("setRetries").value = s.retries;
    $("setMaxDownloads").value = s.max_downloads;
    renderRawAccess(!!s.raw_args_enabled);
    return s;
  });
}

async function saveAndToast(msgEl) {
  msgEl.textContent = t("saving…");
  try {
    await saveSettings();
    msgEl.textContent = "";
    $("setMsg").textContent = "";
    $("ytdlpMsg").textContent = "";
    toast(t("Settings saved"));
  } catch (e) {
    msgEl.textContent = t("save failed: {msg}", { msg: e.message });
  }
}

$("setSave").onclick = () => saveAndToast($("setMsg"));
$("ytdlpSave").onclick = () => saveAndToast($("ytdlpMsg"));
$("setRawEnabled").onchange = (e) => renderRawAccess(e.target.checked);

// anything the user edits in Settings marks the form dirty, so a tab switch
// does not silently reload it from the server (v0.21.1 audit). Controls that
// persist themselves — or scratch boxes that were never settings — must not
// light the dot (v0.44.x audit: it stayed lit after a language or default-
// preset change, and typing in the preset-name box claimed unsaved work)
{
  const panel = $("panel-settings");
  if (panel) {
    const DIRTY_IGNORE = new Set(["setLang", "defaultPreset", "setConc",
                                  "presetName", "archiveEntry"]);
    for (const ev of ["input", "change"]) {
      panel.addEventListener(ev, (e) => {
        const id = e.target && e.target.id;
        if (id && DIRTY_IGNORE.has(id)) return;
        markSettingsDirty(true);
      });
    }
  }
}

/* "applied live" is a promise the field now keeps (v0.44.x audit): a change
   posts just this key, so the queue's capacity moves without a Save — the
   rest of the form keeps its unsaved edits untouched */
$("setConc").onchange = async () => {
  const n = Math.min(4, Math.max(1, Math.round(Number($("setConc").value) || 1)));
  $("setConc").value = n;
  try {
    const s = await api("/settings", { method: "POST",
                                       body: JSON.stringify({ max_concurrent: n }) });
    if (SETTINGS_SNAPSHOT) SETTINGS_SNAPSHOT.max_concurrent = s.max_concurrent;
    toast(t("Concurrent downloads: {n}", { n: s.max_concurrent }));
  } catch (e) {
    toast(t("could not apply: {msg}", { msg: e.message }), "bad");
  }
};

/* ---------- test cookies: the button that answers "did it work?" ---------- */
async function testCookies() {
  const msg = $("cookiesMsg");
  const btn = $("testCookies");
  btn.disabled = true;
  msg.textContent = t("testing…");
  msg.classList.remove("good", "bad");
  try {
    // the test must check what is on screen — the cookie fields ride as
    // transient overrides, so testing never commits the form (v0.44.x audit:
    // it used to silently save every dirty panel). The URL box stays the
    // subject when the user just pasted something.
    const url = ($("url").value || "").trim();
    const r = await api("/auth/check", {
      method: "POST",
      body: JSON.stringify({
        url: url || null,
        cookies_file: $("setCookies").value.trim(),
        cookies_from_browser: $("setCookiesBrowser").value,
      }),
    });
    msg.textContent = r.message;
    msg.classList.toggle("good", !!r.ok);
    msg.classList.toggle("bad", !r.ok);
    if (r.detail) msg.title = r.detail;
    if (r.cookies) {
      msg.textContent += " " + t("({domains})",
        { domains: r.cookies.domains.join(", ") || t("no domains") });
    }
  } catch (e) {
    msg.textContent = t("test failed: {msg}", { msg: e.message });
    msg.classList.add("bad");
  } finally {
    btn.disabled = false;
  }
}
$("testCookies").onclick = testCookies;

/* ---------- share target (Android): a link from another app --------------- */
/** MainActivity hands a shared link here once the UI is on screen: prefill the
 *  box and probe it. The format stays the user's choice, exactly like a paste. */
window.suravidlShared = (url) => {
  if (!url || typeof url !== "string") return;
  showTab("download");
  $("url").value = url.trim();
  doProbe();
  toast(t("shared link ready — pick a format"));
};

/* the bay's door: summary clicks are intercepted (preventDefault) so
   <details> never snaps its content in or out; the .bay-body wrapper
   transitions max-height + opacity instead and the [open] attribute flips
   only when the door finishes moving. prefers-reduced-motion clamps the
   transition to .001s, so nothing waits there either. Programmatic opens
   (Studio, the armed strip) skip the door on purpose — they are
   "bring me there" actions. */
function wireBayDoor(d, bodyEl) {
  // one door, two houses: the deck's format bay and the FAQ's answers
  // (v0.42.1 — the FAQ snapped where the bay glided)
  const body = bodyEl || d.querySelector(".bay-body");
  if (!body) return;
  const seal = () => { body.style.maxHeight = ""; body.style.opacity = ""; d.open = false; };
  // one close in flight, one listener, one fallback (the audit): the old
  // per-click guard let a second click mid-close re-run the close AND the
  // first listener then sealed on the new transition — a slamming door
  let closing = false;
  let fallback = null;
  const disarm = () => {
    closing = false;
    if (fallback) { clearTimeout(fallback); fallback = null; }
    if (body._doorEnd) {
      body.removeEventListener("transitionend", body._doorEnd);
      body._doorEnd = null;
    }
  };
  const onEnd = (fn) => {                          // never two live listeners
    const h = (ev) => {
      if (ev.propertyName !== "max-height") return;
      body.removeEventListener("transitionend", h);
      if (body._doorEnd === h) body._doorEnd = null;
      fn();
    };
    body._doorEnd = h;
    body.addEventListener("transitionend", h);
  };
  d.addEventListener("toggle", () => {
    // the Studio button sits outside the fold — its state follows the door
    if (d.id === "ovBlock") {
      const b = $("studioBtn");
      if (b) b.setAttribute("aria-expanded", d.open ? "true" : "false");
    }
  });
  d.querySelector("summary").addEventListener("click", (e) => {
    e.preventDefault();                            // <details> must not snap
    const wantsOpen = !d.open || closing;          // a mid-close click reverses
    disarm();
    if (wantsOpen) {
      if (!d.open) {                               // from shut: start at zero
        body.style.maxHeight = "0px";
        void body.offsetHeight;
      }
      d.open = true;
      body.style.maxHeight = body.scrollHeight + "px";
      body.style.opacity = "1";
      onEnd(() => { if (d.open && !closing) body.style.maxHeight = "none"; });
      return;
    }
    closing = true;                                // close: play the door, then flip
    body.style.maxHeight = body.scrollHeight + "px";
    void body.offsetHeight;
    body.style.maxHeight = "0px";
    body.style.opacity = "0";
    onEnd(() => { if (closing) { closing = false; seal(); } });
    fallback = setTimeout(() => {                  // a door that can never jam
      if (closing) { closing = false; seal(); }
    }, motionMs(500));
  });
}
wireBayDoor($("ovBlock"));

/* ---------- boot ---------- */
$("probeBtn").onclick = doProbe;
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") doProbe(); });
// the transport: picks arm a take; the START lamp commits it (v0.37.0)
$("bestBtn").onclick = () => commitTake($("bestBtn"));
$("studioBtn").onclick = () => {
  $("ovBlock").open = true;
  $("ovBlock").scrollIntoView({ block: "start" });
};
$("probeDetails").setAttribute("aria-expanded", "false");
$("probeDetails").setAttribute("aria-controls", "probeMsg");
$("probeDetails").onclick = () => {
  const hidden = $("probeMsg").classList.toggle("hidden");
  $("probeDetails").textContent = hidden ? t("Show details") : t("Hide details");
  $("probeDetails").setAttribute("aria-expanded", hidden ? "false" : "true");
};
$("audioNativeBtn").dataset.pick = "audio-native";
$("audioM4aBtn").dataset.pick = "audio-m4a";
$("audioMp3Btn").dataset.pick = "audio-mp3";
$("audioNativeBtn").onclick = () => armTake("audio-native", "keep original", $("audioNativeBtn"));
$("audioM4aBtn").onclick = () => armTake("audio-m4a", "m4a", $("audioM4aBtn"));
$("audioMp3Btn").onclick = () => armTake("audio-mp3", "mp3", $("audioMp3Btn"));
// the formats people kept asking for (review #9) — a picker beats raw args
$("audioMore").onchange = () => {
  const preset = $("audioMore").value;
  $("audioMore").value = "";
  if (!preset) return;
  armTake(preset, preset.replace(/^audio-/, ""), $("audioMore"));
};
renderTake();
$("playlistBtn").onclick = () => startJob($("url").value.trim(), null, null, true, $("playlistBtn"));
$("plAll").onclick = () => pickAll(true);
$("plNone").onclick = () => pickAll(false);
$("playlistItems").addEventListener("input", checkboxFromRange);   // typing reacts at once
$("playlistItems").addEventListener("change", checkboxFromRange);

/** Keep the field being typed into above the sticky save bar. Tapping an
 *  input on a phone raises the keyboard, which shrinks the visual viewport —
 *  the field ended up underneath the pinned footer exactly when the user was
 *  looking at it (motion review). Only scrolls when the field is actually
 *  obscured, so desktop focus never moves the page. */
document.addEventListener("focusin", (e) => {
  const field = e.target;
  if (!field || !/^(INPUT|SELECT|TEXTAREA)$/.test(field.tagName || "")) return;
  const r = field.getBoundingClientRect();
  const pad = 90;   // the sticky header and footer own this much of each edge
  if (r.top >= pad && r.bottom <= window.innerHeight - pad) return;   // visible
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  field.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
});

initOptionListKeyboard();

applyTheme(CURRENT.theme, CURRENT.glass, CURRENT.accent);
if (ANDROID()) document.documentElement.dataset.host = "android";
applyStaticI18n();      // v0.44.0: every static string through t()
applyLanguageChrome();  // <html lang> + the window title
renderWhere(CFG.downloadDir);
wireCopyPath();
wireWelcome();
initOverrides();
$("presetSave").onclick = saveCurrentAsPreset;

/* The token the extension needs. It is already in this page's source — the
   engine inlines it so the UI can call its own API — so showing a masked copy
   costs nothing and saves a trip to ~/.suravidl/token, which the phone cannot
   make at all. Masked, because screenshots happen. */
function wireToken() {
  const el = $("apiToken");
  if (!el) return;
  const tok = (CFG && CFG.token) || "";
  el.textContent = tok ? tok.slice(0, 6) + "…" + tok.slice(-4) : t("not set");
  const btn = $("copyToken");
  if (btn) {
    btn.onclick = async () => {
      const legacy = (tok) => {          // most engines still allow this path
        try {
          const ta = document.createElement("textarea");
          ta.value = tok;
          ta.setAttribute("readonly", "");
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.append(ta);
          ta.select();
          const ok = document.execCommand("copy");
          ta.remove();
          return ok;
        } catch (_) { return false; }
      };
      let ok = false;
      if (navigator.clipboard) {
        try { await navigator.clipboard.writeText(tok); ok = true; }
        catch (_) { ok = legacy(tok); }
      } else {
        ok = legacy(tok);
      }
      if (!ok) {
        // "select it above" only works if the FULL token is up there — the
        // masked string copied an unusable half-token (v0.44.x audit)
        el.textContent = tok;
        try {
          const range = document.createRange();
          range.selectNodeContents(el);
          const sel = getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        } catch (_) { /* selection is best-effort */ }
      }
      btn.textContent = ok ? t("Copied") : t("Select it above");
      setTimeout(() => (btn.textContent = t("Copy")), 1800);
    };
  }
  el.title = t("send it as: Authorization: Bearer <token>");
}

wireToken();
loadVersions();
loadPresets();
wireUpdateRow();
wireWhatsNewRow();
checkAppUpdate();
maybeShowWhatsNew();
loadSettings();
initAppControls();
initPlayer();
initFolderSheet();
initBatch();
initArchive();
wireQueueFilters();
/* Start on Download — a quit and reopen is a fresh start, not a return to
   wherever the device was left (v0.38.1 report). The URL stays a real
   address: a hash that names a tab (#settings in a bookmark or a link)
   still opens it. */
(function bootTab() {
  const want = location.hash.slice(1);
  showTab(TABS.includes(want) ? want : "download", { keepScroll: true });
})();
refreshJobs();
setInterval(refreshJobs, 1200);

/* ---------- browser handoffs (v0.39.0) -----------------------------------
   The extension's popup hands a find to the engine; the engine probes it
   there (with the page's captured headers) and this deck picks the result
   up: the format list opens and the user chooses the quality — the popup
   stays a doorman. The seen-list lives in localStorage so a reload does
   not re-open the same handoff; the engine side keeps the item (and its
   headers — a job started from it reuses them) until its own TTL. */
let HANDOFF = null;               // { id, url } the deck is showing
let HANDOFF_ANNOUNCED = new Set();  // "preparing…" already said this session

function handoffSeen() {
  try { return JSON.parse(localStorage.getItem("suravidl.handoff.seen") || "[]"); }
  catch (_) { return []; }
}
function markHandoffSeen(id) {
  const seen = handoffSeen();
  if (!seen.includes(id)) {
    seen.push(id);
    try {
      localStorage.setItem("suravidl.handoff.seen", JSON.stringify(seen.slice(-20)));
    } catch (_) { /* private mode */ }
  }
}

function focusWindow() {
  // the desktop shell can raise itself; a plain browser tab just gets the
  // content when the user looks — the engine holds the handoff either way
  api("/app/focus", { method: "POST" }).catch(() => {});
}

async function checkHandoff() {
  let items = [];
  try {
    ({ items } = await api("/handoff"));
  } catch (_) { return; }        // no engine, or one without handoffs
  const seen = handoffSeen();
  const fresh = (items || []).filter((h) => !seen.includes(h.id));
  if (!fresh.length) return;
  const h = fresh[0];
  if (h.status === "probing") {
    if (!HANDOFF_ANNOUNCED.has(h.id)) {
      HANDOFF_ANNOUNCED.add(h.id);
      showTab("download");
      $("url").value = h.url;
      $("probeMsg").className = "msg muted";
      $("probeMsg").textContent = t("preparing the video your browser sent…");
      $("probeMsg").classList.remove("hidden");
      $("probeSay").classList.add("hidden");
      $("probeDetails").classList.add("hidden");
      setScopes("scan", { say: "reading the source…" });
      $("probeBtn").classList.add("busy");
      focusWindow();
    }
    return;
  }
  markHandoffSeen(h.id);
  $("probeBtn").classList.remove("busy");
  if (h.status === "ready" && h.probe) {
    $("url").value = h.resolved_url || h.url;
    $("probeMsg").textContent = "";
    renderProbe($("url").value, h.probe);
    setScopes("live", { say: "sent from your browser — pick a take" });
    HANDOFF = { id: h.id, url: $("url").value };
    toast(t("Sent from your browser — pick the quality, then take it"), "info");
    focusWindow();
  } else {
    // the engine probed it and it failed; said the one way every failed probe
    // is said — and stored, so a language switch can say it again
    showProbeFailure(h.error || t("probe failed"), null, $("url").value.trim());
    toast(t("the browser sent a video, but reading it failed"), "bad");
  }
}

setInterval(checkHandoff, 2600);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    checkHandoff();
    refreshJobs();      // the queue is current the moment it is visible
    checkUpdatePermResume();
  }
});
checkHandoff();

/** Play a finished download without leaving the page (the v0.22 review's #10:
 *  "check what you downloaded, before you hunt for the file"). A media element
 *  cannot send an Authorization header, so the stream route also takes the
 *  page's own token in the query string. */
function openPlayer(job, file) {
  // one entry of a playlist row plays by basename; everything else plays the
  // job's own filepath (2026-09-27: playlist rows had no Play at all)
  const stream = `/jobs/${encodeURIComponent(job.id)}/stream?`;
  if (file) {
    const name = baseName(file);
    openPlayerSrc(job.title || t("download"),
      stream + "name=" + encodeURIComponent(name) +
      "&token=" + encodeURIComponent(CFG.token), extOf(name));
    return;
  }
  openPlayerSrc(job.title || t("download"),
    stream + "token=" + encodeURIComponent(CFG.token), extOf(job.filepath));
}

/** The file's extension, lowercased ("e1.MP4" → "mp4"). */
function extOf(p) {
  return (String(p || "").split(".").pop() || "").toLowerCase();
}

/** The player modal, driven by whatever URL carries the media. */
function openPlayerSrc(title, src, ext) {
  const isVideo = ["mp4", "m4v", "webm", "mkv", "mov"].includes(ext);
  const isText = ["srt", "vtt"].includes(ext);
  $("playTitle").textContent = title || t("download");
  const body = $("playBody");
  body.replaceChildren();
  let node;
  if (isVideo) {
    node = document.createElement("video");
    node.controls = true;
    node.autoplay = true;
    node.className = "player-video";
    node.playsInline = true;
    node.src = src;
  } else if (isText) {
    node = document.createElement("pre");
    node.className = "player-text";
    fetch(src).then((r) => r.text()).then((txt) => { node.textContent = txt; })
      .catch(() => { node.textContent = t("could not load the subtitles"); });
  } else {
    node = document.createElement("audio");
    node.controls = true;
    node.autoplay = true;
    node.className = "player-audio";
    node.src = src;
  }
  body.append(node);
  PLAY_NODE = node;            // v0.40.4: what the marks read
  $("markIn").classList.toggle("hidden", !isVideo);
  $("markOut").classList.toggle("hidden", !isVideo);
  // the lifecycle, not a class poke (the audit): a close timer still
  // pending from 170ms ago could execute and hide the just-opened player
  openModal($("playModal"));
}

function closePlayer() {
  // the same exit every other dialog uses, then release the media element so a
  // hidden player cannot keep playing; closing used to hard-cut (motion review)
  closeModal($("playModal"));
  PLAY_NODE = null;            // v0.40.4: nothing left to mark
  setTimeout(() => $("playBody").replaceChildren(), motionMs(180));
}

/** v0.40.4: Mark in / Mark out — the player's own clock writes the clip
 *  fields, so a section is cut from what you are watching instead of a
 *  time typed from memory. */
function markClip(which) {
  const node = PLAY_NODE;
  if (!node) return;
  const t = node.currentTime;
  if (typeof t !== "number" || !isFinite(t)) return;
  const v = clock(t);
  if (which === "in") $("ovClipStart").value = v;
  else $("ovClipEnd").value = v;
  toast(which === "in" ? t("clip starts at {v}", { v: v })
                       : t("clip ends at {v}", { v: v }));
}

function initPlayer() {
  $("playClose").onclick = closePlayer;
  $("markIn").onclick = () => markClip("in");
  $("markOut").onclick = () => markClip("out");
  $("playModal").onclick = (e) => {
    if (e.target === $("playModal")) closePlayer();
  };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("playModal").classList.contains("hidden")) {
      closePlayer();
    }
  });
}

/* ---------- the folder sheet ("open folder") ---------- */
/** Desktop shells reveal the folder itself in the OS file manager; on
 *  Android no file manager may open Android/data, so the folder is shown
 *  inside the app instead — every file with Play, and Open / Share through
 *  the host bridge (2026-09-27 report: "Add the open folder button too,
 *  below copy path"). */
async function openFolderSheet() {
  const list = $("folderList");
  list.replaceChildren(el("div", "muted", t("loading…")));
  openModal($("folderModal"));
  try {
    const r = await api("/files/list");
    $("folderTitle").textContent = r.files.length === 1
      ? t("downloads · 1 file")
      : t("downloads · {n} files", { n: r.files.length });
    list.replaceChildren();
    if (!r.files.length) {
      list.append(el("div", "muted", t("the folder is empty")));
      return;
    }
    for (const f of r.files) list.append(folderItem(f));
  } catch (e) {
    list.replaceChildren(
      el("div", "muted", t("could not read the folder: {msg}", { msg: e.message })));
  }
}

/** One file line of the folder sheet. */
function folderItem(f) {
  const item = el("div", "jitem");
  const name = el("span", "jname", f.name);
  name.title = f.path;
  item.append(name, el("span", "fsize", humanBytes(f.bytes)));
  if (f.kind === "video" || f.kind === "audio") {
    const play = el("button", "ghost-sm", t("Play"));
    play.onclick = () => openPlayerSrc(f.name,
      "/files/stream?path=" + encodeURIComponent(f.name) +
      "&token=" + encodeURIComponent(CFG.token), extOf(f.name));
    item.append(play);
  }
  if (ANDROID() && window.AndroidHost) {
    const open = el("button", "ghost-sm", t("Open"));
    open.onclick = () => {
      try { window.AndroidHost.openFile(f.path); }
      catch (e) { toast(t("could not open: {msg}", { msg: e.message }), "bad"); }
    };
    const share = el("button", "ghost-sm", t("Share"));
    share.onclick = () => {
      try { window.AndroidHost.shareFile(f.path); }
      catch (e) { toast(t("could not share: {msg}", { msg: e.message }), "bad"); }
    };
    item.append(open, share);
  }
  return item;
}

function initFolderSheet() {
  const modal = $("folderModal");
  if (!modal) return;
  $("folderClose").onclick = () => closeModal(modal);
  modal.onclick = (e) => { if (e.target === modal) closeModal(modal); };
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      closeModal(modal);
    }
  });
  $("openDir").onclick = async () => {
    if (DESKTOP) {
      try {
        await api("/app/reveal-dir", { method: "POST" });
        return;
      } catch (_) { /* no file manager on this shell — show the sheet */ }
    }
    openFolderSheet();
  };
}

/** Several links in the box at once: offer to queue them all (review #5).
 *  Pasting into a single-line input collapses the newlines to spaces, so a
 *  multi-line paste arrives as space-separated URLs — split on whitespace.
 *
 *  A link counts with a scheme, or as the bare host shape the engine already
 *  accepts ("youtu.be/x"): the UI used to demand a scheme, so pasting a bare
 *  link produced no batch at all while the engine would have taken it (UI
 *  review). */
const BARE_HOST = /^[a-z0-9-]+(\.[a-z0-9-]+)+(:\d+)?(\/\S*)?$/i;

function pastedTokens() {
  const text = $("url").value.trim();
  return text ? text.split(/\s+/) : [];
}

function pastedUrls() {
  return pastedTokens().filter((s) =>
    /^(https?|ftp|magnet):/i.test(s) || BARE_HOST.test(s));
}

function renderBatchRow() {
  const tokens = pastedTokens();
  const urls = pastedUrls();
  const junk = tokens.length - urls.length;
  const show = tokens.length > 1 || urls.length > 1;
  const over = urls.length > 20;          // the engine's own batch ceiling
  $("batchRow").classList.toggle("hidden", !show);
  const links = urls.length === 1
    ? t("1 link") : t("{n} links", { n: urls.length });
  // v0.40.5: a line the paste cannot use is named, not silently uncounted
  const skipped = junk
    ? (junk === 1 ? t("1 skipped — not a link")
                  : t("{n} skipped — not links", { n: junk })) : "";
  const say = urls.length ? [links, skipped].filter(Boolean).join(" · ") : skipped;
  $("batchCount").textContent = !show ? ""
    : over ? t("{links} pasted{skipped} — only 20 fit in one batch",
               { links: links, skipped: skipped ? " · " + skipped : "" })
    : urls.length > 1 ? say + t(" — queue them all?")
    : say;
  $("batchBtn").disabled = over || urls.length < 2;
}

function initBatch() {
  $("url").addEventListener("input", renderBatchRow);
  $("url").addEventListener("change", renderBatchRow);
  $("batchBtn").onclick = async () => {
    const urls = pastedUrls();
    if (urls.length < 2) return;
    const body = { urls };
    if (OV.preset) body.preset = OV.preset;
    const overrides = readOv();
    if (overrides) body.overrides = overrides;
    $("batchBtn").classList.add("busy");
    try {
      const r = await api("/jobs/batch",
        { method: "POST", body: JSON.stringify(body) });
      $("url").value = "";
      renderBatchRow();
      clearOv();
      const n = (r.jobs || []).length;
      const skipped = r.skipped || [];
      if (skipped.length) {
        toast(t("{n} queued · {k} skipped: {err}",
                { n: n, k: skipped.length, err: skipped[0].error }), "bad");
      } else {
        toast(t("{n} links queued", { n: n }), "info");
      }
      refreshJobs();
    } catch (e) {
      toast(t("could not queue those links: {msg}", { msg: e.message }), "bad");
    } finally {
      $("batchBtn").classList.remove("busy");
    }
  };
}

/** The download archive used to be a black box (review #7): show what is in
 *  it, and let the user forget an entry so that video can be fetched again. */
async function loadArchive() {
  try {
    const a = await api("/archive");
    const n = a.count || 0;
    $("archiveCount").textContent = n
      ? (n === 1 ? t("· 1 entry") : t("· {n} entries", { n: n })) : t("· empty");
    const list = $("archiveList");
    list.replaceChildren();
    list.classList.remove("hidden");
    if (!n) {
      list.append(el("div", "muted small", t("nothing archived yet")));
      return;
    }
    const entries = (a.entries || []).slice(-50).reverse();
    if (a.entries && entries.length < n) {
      list.append(el("div", "muted small",
        t("showing the last {shown} of {n}", { shown: entries.length, n: n })));
    }
    for (const line of entries) {
      const row = el("div", "jrow");
      row.append(el("span", "small mono", line));
      const forget = el("button", "ghost-sm", t("forget"));
      forget.setAttribute("aria-label",
        t("Forget archive entry {entry}", { entry: line }));
      forget.onclick = async () => {
        try {
          await api("/archive/forget",
            { method: "POST", body: JSON.stringify({ entry: line }) });
          toast(t("forgotten — that video can be downloaded again"), "info");
          loadArchive();
        } catch (e) {
          toast(t("could not forget: {msg}", { msg: e.message }), "bad");
        }
      };
      row.append(forget);
      list.append(row);
    }
  } catch (e) {
    toast(t("could not read the archive: {msg}", { msg: e.message }), "bad");
  }
}

function initArchive() {
  $("archiveShow").onclick = () => {
    const list = $("archiveList");
    if (!list.classList.contains("hidden") && list.childElementCount) {
      list.classList.add("hidden");
      return;
    }
    loadArchive();
  };
  $("archiveForget").onclick = async () => {
    const entry = $("archiveEntry").value.trim();
    if (!entry) { toast(t("paste an archive entry first"), "bad"); return; }
    try {
      const r = await api("/archive/forget",
        { method: "POST", body: JSON.stringify({ entry }) });
      toast(r.removed === 1 ? t("forgotten 1 entry")
                            : t("forgotten {n} entries", { n: r.removed }),
        "info");
      $("archiveEntry").value = "";
      loadArchive();
    } catch (e) {
      toast(t("could not forget: {msg}", { msg: e.message }), "bad");
    }
  };
}

/** Put a failed job's URL and options back into the Download tab so the next
 *  attempt can be different — a site that refused one format often takes
 *  another, and re-running the identical request is a loop (review #11). */
function editAndRetry(j) {
  $("url").value = j.url || "";
  clearOv();
  if (j.preset) { OV.preset = j.preset; $("ovPreset").value = j.preset; }
  const ov = j.overrides || {};
  if (ov.subtitles_mode) $("ovSubs").value = ov.subtitles_mode;
  if (ov.subtitles_langs) $("ovSubLangs").value = ov.subtitles_langs;
  if (ov.sponsorblock_mode) $("ovSb").value = ov.sponsorblock_mode;
  $("ovMeta").value = ov.embed_metadata === true ? "on"
    : ov.embed_metadata === false ? "off" : "";
  $("ovThumb").value = ov.embed_thumbnail === true ? "on"
    : ov.embed_thumbnail === false ? "off" : "";
  if (ov.raw_args) $("ovRaw").value = ov.raw_args;
  if (ov.video_container) $("ovContainer").value = ov.video_container;
  if (ov.archive_ignore) $("ovArchive").value = "ignore";
  if (ov.download_sections) {
    const [start, end] = String(ov.download_sections)
      .replace(/^\*/, "").split("-");
    $("ovClipStart").value = (start || "").trim();
    $("ovClipEnd").value = (end || "").trim();
  }
  renderOvCount();
  showTab("download");
  toast(t("loaded the failed settings — change what you like, then start it"), "info");
}

addEventListener("scroll", () => {
  document.body.classList.toggle("scrolled", scrollY > 4);
}, { passive: true });
