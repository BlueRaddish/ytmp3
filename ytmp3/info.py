"""Read metadata for a user-supplied URL."""

from urllib.parse import urlsplit

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


def detail(url: str) -> dict | None:
    try:
        with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True,
                        "noplaylist": True}) as ydl:
            return ydl.extract_info(url, download=False)
    except (DownloadError, OSError):
        return None


def source_items(url: str, limit: int = 100) -> tuple[list[dict], int, str | None]:
    """Resolve one URL to a track or a bounded playlist of flat entries."""
    parts = urlsplit(url)
    if parts.hostname == "open.spotify.com" and parts.path.startswith("/playlist/"):
        raise ValueError("Spotify playlist links are not supported. Import an M3U of local MP3s instead.")
    with YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True,
                    "extract_flat": "in_playlist", "playlistend": limit + 1,
                    "ignoreerrors": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise ValueError("This link has no available audio items.")
    if info.get("_type") not in {"playlist", "multi_video"}:
        return [{**info, "source_url": url}], 0, None
    entries = list(info.get("entries") or [])
    if len(entries) > limit:
        raise ValueError(f"This playlist has more than {limit} items. Use a shorter playlist.")
    items = []
    skipped = 0
    for entry in entries:
        if not entry:
            skipped += 1
            continue
        address = entry.get("webpage_url") or entry.get("url")
        if not isinstance(address, str) or not address.startswith(("http://", "https://")):
            if entry.get("ie_key") == "Youtube" and entry.get("id"):
                address = f"https://www.youtube.com/watch?v={entry['id']}"
            else:
                skipped += 1
                continue
        items.append({**entry, "source_url": address})
    if not items:
        raise ValueError("This playlist has no downloadable items.")
    return items, skipped, str(info.get("title") or "Playlist")[:80]
