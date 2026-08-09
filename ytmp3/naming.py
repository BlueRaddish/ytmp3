"""Turn a YouTube result into a clean track title and a filename."""

import re

# Bracketed groups whose contents look like upload cruft rather than part of the
# title. "(Official Video)" goes; "(Feat. Colde)" and "(MY TYPE)" stay.
_JUNK_WORDS = (
    "official", "lyric", "lyrics", "audio only", "visualizer", "color coded",
    "colour coded", "m/v", "teaser", "eng sub", "kor sub", "sub español",
    "가사", "자막", "해석", "번역", "한글", "auto-generated",
)
_JUNK_EXACT = (
    "mv", "hd", "hq", "4k", "8k", "60fps", "audio", "video", "music video",
    "full", "full ver", "full ver.", "full version", "live", "inst", "inst.",
    "instrumental", "cover", "remaster", "remastered", "explicit",
)

_BRACKETED = re.compile(r"\s*[\(\[\{]([^\(\)\[\]\{\}]*)[\)\]\}]")
_TRAILING_BARE = re.compile(
    r"(?i)\s*[-–—|]?\s*(official\s+(music\s+)?video|official\s+audio|"
    r"lyric\s+video|music\s+video|m/v|mv|audio|visualizer)\s*$"
)
_SEPARATOR = re.compile(r"\s+[-–—_|]\s+")

# Characters Windows forbids outright, plus control characters.
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _is_junk(inner: str) -> bool:
    text = inner.strip().lower()
    if not text:
        return True
    if text in _JUNK_EXACT:
        return True
    return any(word in text for word in _JUNK_WORDS)


def clean_title(raw: str, artist: str | None = None) -> str:
    """Strip upload cruft from a video title to get at the song name."""
    title = raw.strip()

    # Leading tags such as "[MV] " or "[Official Video] ".
    while True:
        stripped = re.sub(r"^\s*[\(\[\{]([^\)\]\}]*)[\)\]\}]\s*", "", title)
        if stripped == title:
            break
        if not _is_junk(re.match(r"^\s*[\(\[\{]([^\)\]\}]*)", title).group(1)):
            break
        title = stripped

    title = _BRACKETED.sub(lambda m: "" if _is_junk(m.group(1)) else m.group(0), title)

    previous = None
    while previous != title:
        previous = title
        title = _TRAILING_BARE.sub("", title)

    # "iKON - 취향저격" when we already know the artist is iKON.
    if artist:
        pattern = rf"(?i)^\s*{re.escape(artist.strip())}\s*[-–—_|:]\s*"
        title = re.sub(pattern, "", title)

    title = re.sub(r"\s{2,}", " ", title).strip(" -–—_|·")
    return title or raw.strip()


def sanitize(name: str, replacement: str = "") -> str:
    """Make a string safe to use as a filename on Windows, macOS and Linux."""
    cleaned = _ILLEGAL.sub(replacement, name)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    # Windows discards trailing dots and spaces; do it here so the name we
    # report is the name that lands on disk.
    cleaned = cleaned.rstrip(". ")
    stem = cleaned.split(".")[0].upper()
    if stem in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned or "untitled"


def render(template: str, fields: dict[str, str]) -> str:
    """Fill a filename template, sanitizing each field before substitution."""
    safe = {key: sanitize(str(value)) if value else "" for key, value in fields.items()}
    try:
        rendered = template.format(**safe)
    except KeyError as exc:
        known = ", ".join(sorted(fields))
        raise ValueError(f"unknown template field {exc}; available: {known}") from exc
    # An empty field can leave " - " style debris behind.
    rendered = re.sub(r"\s*[-–—]\s*(?=\.)", "", rendered)
    rendered = re.sub(r"^\s*[-–—]\s*", "", rendered)
    rendered = re.sub(r"\s{2,}", " ", rendered).strip()
    return sanitize(rendered)


def fields_for(info: dict, name_override: str | None = None) -> dict[str, str]:
    """Build the template field map from a yt-dlp info dict."""
    artist = info.get("artist") or info.get("creator") or ""
    if not artist:
        uploader = info.get("uploader") or info.get("channel") or ""
        artist = re.sub(r"\s*-\s*Topic$", "", uploader)

    title = name_override or info.get("track") or clean_title(
        info.get("title") or "", artist
    )

    year = info.get("release_year") or ""
    if not year and info.get("upload_date"):
        year = str(info["upload_date"])[:4]

    return {
        "title": title,
        "artist": artist,
        "album": info.get("album") or "",
        "year": str(year),
        "id": info.get("id") or "",
    }
