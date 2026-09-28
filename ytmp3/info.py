"""Read metadata for a user-supplied URL."""

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


def detail(url: str) -> dict | None:
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True,
                        "noplaylist": True}) as ydl:
            return ydl.extract_info(url, download=False)
    except (DownloadError, OSError):
        return None
