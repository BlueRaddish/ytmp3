"""Check the project's small public update manifest."""

import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

FEED = "https://raw.githubusercontent.com/BlueRaddish/ytmp3/main/updates.json"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def newer(candidate: str, current: str) -> bool:
    if not VERSION.fullmatch(candidate) or not VERSION.fullmatch(current):
        raise ValueError("Invalid app version.")
    return tuple(map(int, candidate.split("."))) > tuple(map(int, current.split(".")))


def check(current: str) -> dict:
    request = Request(FEED, headers={"User-Agent": "ytmp3-update-check"})
    with urlopen(request, timeout=5) as response:
        raw = response.read(8193)
    if len(raw) > 8192:
        raise ValueError("Update manifest is too large.")
    manifest = json.loads(raw)
    version = manifest["version"]
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ValueError("Invalid update version.")
    apk_url = manifest["android_apk_url"]
    if not isinstance(apk_url, str):
        raise ValueError("Invalid Android update URL.")
    parts = urlsplit(apk_url)
    if parts.scheme != "https" or parts.hostname != "drive.google.com" or parts.username or parts.password or parts.port:
        raise ValueError("Invalid Android update URL.")
    notes = manifest.get("notes", "")
    if not isinstance(notes, str) or len(notes) > 400:
        raise ValueError("Invalid update notes.")
    return {"current": current, "version": version, "available": newer(version, current),
            "notes": notes, "android_apk_url": apk_url}
