# Privacy

suravidl's browser extension, desktop app and Android app talk to **your own
suravidl engine**, running on your own computer. There is no suravidl server,
no account and no sign-in.

## What the extension handles

- **Page URLs and the media URLs detected on them** — requests the page makes
  for video/audio, and media elements in the page — are sent to the engine
  address you configure. The default is `http://127.0.0.1:8787`; if you point it
  somewhere else, that address is one you chose.
- **Cookies and request headers** are passed along with a page you explicitly
  send to the engine, so the download behaves the way the page does. They go to
  your engine — never to the project, its authors, or anyone else.
- **Settings** (engine address, access token, preferences) live in the
  browser's own extension storage.

## What is never done

- No analytics, telemetry, crash reporting or advertising — in the extension or
  anywhere else in the project.
- Nothing is uploaded, shared or sold. The only network destination the
  extension itself talks to is the engine address you configure.
- No remote code: the extension ships as readable source, and a stable Firefox
  can only run a build signed by Mozilla, so it cannot be changed from a
  distance.

## Your engine is yours

The engine writes downloads, a job database and settings under `~/.suravidl` on
the machine running it (folder mode `0700`, files `0600`), and redacts cookie
values both on disk and in its API responses. Deleting a job in the app deletes
its files from disk too.

## Contact

Open an issue: <https://github.com/LoLyeah/suravidl/issues>
