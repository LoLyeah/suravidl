"""On-device proof that bundled yt-dlp imports and reports its version."""


def yt_dlp_version() -> str:
    import yt_dlp.version

    return yt_dlp.version.__version__
