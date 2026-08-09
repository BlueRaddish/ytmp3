"""Search YouTube and rank the results that are actually music."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

# Anything shorter is a Short or a clip; anything longer is a compilation,
# a full album upload or a livestream recording.
MIN_SECONDS = 60
MAX_SECONDS = 900

# How many search hits to pull before filtering. The flat search is a single
# request, so asking for plenty is nearly free.
SEARCH_POOL = 30

# How many of those to fetch full metadata for. This costs one request each,
# so it is the real budget.
PROBE_LIMIT = 14


@dataclass
class Result:
    id: str
    url: str
    title: str
    channel: str
    duration: int
    views: int
    category: str = ""
    track: str = ""
    artist: str = ""
    album: str = ""

    @property
    def is_catalog(self) -> bool:
        """True when this is a YouTube Music catalog track, not just a video."""
        return bool(self.track)

    @property
    def is_music(self) -> bool:
        return self.category == "Music" or self.is_catalog

    def info(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "uploader": self.channel,
            "channel": self.channel,
            "track": self.track,
            "artist": self.artist,
            "album": self.album,
        }


class _Silent:
    """Swallow yt-dlp's own reporting; unavailable videos are expected here."""

    def debug(self, message): pass

    def info(self, message): pass

    def warning(self, message): pass

    def error(self, message): pass


def _ydl(**extra) -> YoutubeDL:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noprogress": True,
        "logger": _Silent(),
    }
    opts.update(extra)
    return YoutubeDL(opts)


def flat_search(query: str, pool: int = SEARCH_POOL) -> list[Result]:
    """One request: titles, channels, durations and view counts, no details."""
    with _ydl(extract_flat="in_playlist") as ydl:
        info = ydl.extract_info(f"ytsearch{pool}:{query}", download=False)

    results = []
    for entry in info.get("entries") or []:
        if not entry or not entry.get("id"):
            continue
        duration = int(entry.get("duration") or 0)
        if not MIN_SECONDS <= duration <= MAX_SECONDS:
            continue
        results.append(
            Result(
                id=entry["id"],
                url=entry.get("url") or f"https://www.youtube.com/watch?v={entry['id']}",
                title=entry.get("title") or "",
                channel=entry.get("channel") or entry.get("uploader") or "",
                duration=duration,
                views=int(entry.get("view_count") or 0),
            )
        )
    return results


def detail(url: str) -> dict | None:
    """Full metadata for one video. Returns None if it cannot be read."""
    try:
        with _ydl() as ydl:
            return ydl.extract_info(url, download=False)
    except (DownloadError, OSError):
        return None


def _enrich(results: list[Result], workers: int = 8) -> list[Result]:
    def annotate(result: Result) -> Result:
        info = detail(result.url)
        if info:
            categories = info.get("categories") or []
            result.category = categories[0] if categories else ""
            result.track = info.get("track") or ""
            result.artist = info.get("artist") or info.get("creator") or ""
            result.album = info.get("album") or ""
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(annotate, results))


def search(query: str, limit: int = 10, music_only: bool = True) -> list[Result]:
    """Search, keep the music, and return the most-viewed first."""
    hits = flat_search(query)
    if not hits:
        return []

    hits.sort(key=lambda r: r.views, reverse=True)

    if not music_only:
        return hits[:limit]

    probed = _enrich(hits[:PROBE_LIMIT])
    music = [r for r in probed if r.is_music]
    music.sort(key=lambda r: r.views, reverse=True)
    return music[:limit]
