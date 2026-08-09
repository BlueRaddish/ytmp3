"""Fetch the best audio stream and convert it to MP3."""

import os
import shutil
from pathlib import Path

from yt_dlp import YoutubeDL

# Where winget drops ffmpeg on Windows, checked when it is not on PATH.
_WINGET_FFMPEG = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
)


def find_ffmpeg() -> str | None:
    """Directory holding ffmpeg, or None if it cannot be found."""
    override = os.environ.get("FFMPEG_LOCATION")
    if override and (Path(override) / "ffmpeg.exe").exists():
        return override
    if override and (Path(override) / "ffmpeg").exists():
        return override

    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).parent)

    if _WINGET_FFMPEG.is_dir():
        for candidate in _WINGET_FFMPEG.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"):
            return str(candidate.parent)
    return None


def download_mp3(url: str, workdir: Path, filename: str, verbose: bool = False) -> Path:
    """Download `url` as MP3 into `workdir` under `filename`. Returns the path."""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found; install it and put it on PATH, "
            "or set FFMPEG_LOCATION to the directory containing it"
        )

    stem = filename[:-4] if filename.lower().endswith(".mp3") else filename
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(workdir / f"{stem}.%(ext)s"),
        "ffmpeg_location": ffmpeg,
        "writethumbnail": True,
        "noplaylist": True,
        "quiet": not verbose,
        "no_warnings": not verbose,
        "noprogress": not verbose,
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail", "already_have_thumbnail": False},
        ],
    }

    with YoutubeDL(opts) as ydl:
        ydl.download([url])

    produced = workdir / f"{stem}.mp3"
    if not produced.exists():
        raise RuntimeError(f"yt-dlp finished but {produced.name} was not produced")
    return produced
