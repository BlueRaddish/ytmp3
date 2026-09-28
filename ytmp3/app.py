"""Small authenticated server for a personal MP3 library."""

import argparse
import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import shutil
import socket
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, quote, unquote, urlsplit

from tinytag import TinyTag

from .config import DEFAULT_TEMPLATE
from .download import download_mp3
from .info import detail, source_items
from .naming import fields_for, render

WEB = Path(__file__).with_name("web")
RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")
MAX_POST = 8192
MAX_COVER = 1024 * 1024


def image_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


def validate_source(raw: str) -> str:
    """Accept one public HTTP(S) URL; this is a local tool, not a public proxy."""
    if not isinstance(raw, str):
        raise ValueError("Enter one HTTP or HTTPS URL.")
    url = raw.strip()
    parts = urlsplit(url)
    if (parts.scheme not in {"http", "https"} or not parts.hostname
            or parts.username or parts.password or len(url) > 4096):
        raise ValueError("Enter one HTTP or HTTPS URL.")
    try:
        addresses = socket.getaddrinfo(parts.hostname, None)
    except OSError as exc:
        raise ValueError("The URL's host could not be resolved.") from exc
    if not addresses or any(
        not ipaddress.ip_address(item[4][0]).is_global for item in addresses
    ):
        raise ValueError("Local and private network URLs are not accepted.")
    # yt-dlp may follow source-specific redirects; binding locally and requiring
    # a key is the boundary. A public service needs per-request egress controls.
    return url


def parse_range(value: str | None, size: int) -> tuple[int, int] | None:
    if not value:
        return None
    match = RANGE.fullmatch(value.strip())
    if not match or not any(match.groups()) or size == 0:
        raise ValueError("Invalid range")
    first, last = match.groups()
    if first:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    else:
        length = int(last)
        start, end = max(0, size - length), size - 1
    if start > end or start >= size or (not first and int(last) == 0):
        raise ValueError("Invalid range")
    return start, end


class Library:
    def __init__(self, path: Path, includes: list[Path] | None = None):
        self.path = path.expanduser().resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        self.includes = []
        for folder in includes or []:
            resolved = folder.expanduser().resolve()
            if not resolved.is_dir():
                raise ValueError(f"Not a folder: {folder}")
            if resolved != self.path and resolved not in self.includes:
                self.includes.append(resolved)
        self.jobs: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.edits_file = self.path / ".ytmp3-track-edits.json"
        try:
            self.edits = json.loads(self.edits_file.read_text("utf-8"))
            if not isinstance(self.edits, dict):
                self.edits = {}
        except (OSError, ValueError):
            self.edits = {}
        self.tag_cache: dict[str, tuple[int, int, dict]] = {}
        # One conversion at a time avoids filename races and keeps ffmpeg load
        # modest. Raise workers and add atomic reservation if queues become slow.
        self.pool = ThreadPoolExecutor(max_workers=1)

    def tracks(self) -> list[dict]:
        entries = []
        for index, root in enumerate([self.path, *self.includes]):
            paths = root.glob("*.mp3") if index == 0 else root.rglob("*.mp3")
            for path in paths:
                if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
                    continue
                stat = path.stat()
                track_id = path.name if index == 0 else f"@{index - 1}/{path.relative_to(root).as_posix()}"
                relative_folder = path.parent.relative_to(root).as_posix()
                folder = root.name if relative_folder == "." else f"{root.name}/{relative_folder}"
                data = self._tags(path, stat)
                edit = self.edits.get(track_id, {})
                if not isinstance(edit, dict):
                    edit = {}
                cover = self._cover_file(track_id)
                entries.append({"id": track_id, "title": edit.get("title") or data["title"] or path.stem,
                                "artist": edit.get("artist", data["artist"]),
                                "album": edit.get("album", data["album"]),
                                "duration": data["duration"], "artwork": cover.is_file() or data["artwork"],
                                "folder": folder, "folderId": f"{index}:{'' if relative_folder == '.' else relative_folder}",
                                "rootFolder": root.name, "rootFolderId": f"{index}:",
                                "size": stat.st_size, "modified": int(stat.st_mtime)})
        return sorted(entries, key=lambda item: item["modified"], reverse=True)

    def _tags(self, path: Path, stat: os.stat_result) -> dict:
        key = str(path)
        cached = self.tag_cache.get(key)
        if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
            return cached[2]
        data = {"title": "", "artist": "", "album": "", "duration": 0, "artwork": False}
        try:
            tag = TinyTag.get(path, image=True)
            picture = tag.images.any
            data.update(title=tag.title or "", artist=tag.artist or "", album=tag.album or "",
                        duration=round(tag.duration or 0),
                        artwork=bool(picture and image_type(picture.data) and len(picture.data) <= MAX_COVER))
        except Exception:
            pass  # An unreadable tag must not hide an otherwise playable file.
        self.tag_cache[key] = (stat.st_mtime_ns, stat.st_size, data)
        return data

    def _cover_file(self, track_id: str) -> Path:
        return self.path / ".ytmp3-covers" / hashlib.sha256(track_id.encode()).hexdigest()

    def cover(self, track_id: str) -> tuple[bytes, str] | None:
        path = self.file(track_id)
        if not path:
            return None
        custom = self._cover_file(track_id)
        if custom.is_file():
            data = custom.read_bytes()
        else:
            try:
                picture = TinyTag.get(path, image=True).images.any
                data = picture.data if picture else b""
            except Exception:
                data = b""
        mime = image_type(data) if len(data) <= MAX_COVER else None
        return (data, mime) if mime else None

    def edit_track(self, body: dict) -> None:
        if not isinstance(body, dict):
            raise ValueError("Invalid track details.")
        track_id = body.get("id")
        if not isinstance(track_id, str) or not self.file(track_id):
            raise ValueError("Track not found.")
        edit = {}
        for field in ("title", "artist", "album"):
            value = body.get(field, "")
            if not isinstance(value, str) or len(value) > 160:
                raise ValueError("Track details are too long.")
            edit[field] = value.strip()
        raw_cover = body.get("cover")
        cover_data = None
        if raw_cover is not None:
            if not isinstance(raw_cover, str) or len(raw_cover) > MAX_COVER * 4 // 3 + 8:
                raise ValueError("Cover must be a JPEG or PNG under 1 MB.")
            try:
                cover_data = base64.b64decode(raw_cover, validate=True)
            except binascii.Error as exc:
                raise ValueError("Invalid cover image.") from exc
            if not image_type(cover_data) or len(cover_data) > MAX_COVER:
                raise ValueError("Cover must be a JPEG or PNG under 1 MB.")
        cover = self._cover_file(track_id)
        with self.lock:
            if cover_data is not None:
                cover.parent.mkdir(exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=cover.parent, delete=False) as temporary:
                    temporary.write(cover_data)
                    temp_path = Path(temporary.name)
                os.replace(temp_path, cover)
            if body.get("removeCover") is True:
                cover.unlink(missing_ok=True)
            updated = dict(self.edits)
            updated[track_id] = edit
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path, delete=False) as temporary:
                json.dump(updated, temporary)
                temp_path = Path(temporary.name)
            os.replace(temp_path, self.edits_file)
            self.edits = updated

    def file(self, name: str) -> Path | None:
        if not name or not name.lower().endswith(".mp3"):
            return None
        if name.startswith("@") and "/" in name:
            prefix, relative = name[1:].split("/", 1)
            if not prefix.isdigit() or int(prefix) >= len(self.includes):
                return None
            parts = PurePosixPath(relative).parts
            if not parts or any(part in {".", "..", ""} for part in parts):
                return None
            root = self.includes[int(prefix)]
            path = root.joinpath(*parts)
        else:
            if name != Path(name).name:
                return None
            root = self.path
            path = root / name
        return path if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root) else None

    def submit(self, url: str) -> str:
        url = validate_source(url)
        job_id = secrets.token_urlsafe(9)
        with self.lock:
            self.jobs[job_id] = {"id": job_id, "state": "queued", "url": url}
            if len(self.jobs) > 30:
                old = next((key for key, item in self.jobs.items()
                            if item["state"] in {"done", "error"}), None)
                if old:
                    del self.jobs[old]
        self.pool.submit(self._download, job_id, url)
        return job_id

    def job(self, job_id: str) -> dict | None:
        with self.lock:
            item = self.jobs.get(job_id)
            return dict(item) if item else None

    def _set(self, job_id: str, **changes) -> None:
        with self.lock:
            self.jobs[job_id].update(changes)

    def _download(self, job_id: str, url: str) -> None:
        self._set(job_id, state="working")
        try:
            items, failed, playlist = source_items(url)
            total = len(items) + failed
            saved = 0
            tracks = []
            self._set(job_id, total=total, completed=0, failed=failed, playlist=playlist)
            for info in items:
                try:
                    item_url = validate_source(info["source_url"])
                    metadata = info if info.get("title") else detail(item_url) or info
                    filename = render(DEFAULT_TEMPLATE, fields_for(metadata))
                    with tempfile.TemporaryDirectory(prefix=".ytmp3-", dir=self.path) as temp:
                        produced = download_mp3(item_url, Path(temp), filename)
                        target = self.path / filename
                        number = 2
                        while target.exists():
                            target = self.path / f"{Path(filename).stem} ({number}).mp3"
                            number += 1
                        shutil.move(str(produced), str(target))
                    saved += 1
                    tracks.append(target.name)
                    self._set(job_id, track=target.name)
                except Exception:
                    logging.exception("ytmp3 playlist item failed")
                    failed += 1
                self._set(job_id, completed=saved + failed, saved=saved, failed=failed)
            if saved:
                self._set(job_id, state="done", tracks=tracks)
            else:
                raise ValueError("No items could be saved.")
        except ValueError as exc:
            logging.warning("ytmp3 download rejected: %s", exc)
            self._set(job_id, state="error", error=str(exc))
        except Exception:
            logging.exception("ytmp3 download failed")
            self._set(job_id, state="error",
                      error="Could not save this link. Check the URL and connection, then try again.")


class AppServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], library: Library):
        super().__init__(address, AppHandler)
        self.library = library
        self.key = secrets.token_urlsafe(24)


class AppHandler(BaseHTTPRequestHandler):
    server: AppServer

    def log_message(self, format: str, *args: object) -> None:
        # Access URLs contain a temporary key; do not write them to logs.
        pass

    def _cookie_authorized(self) -> bool:
        jar = SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        item = jar.get("ytmp3_session")
        return bool(item and hmac.compare_digest(item.value, self.server.key))

    def _authorized(self) -> bool:
        if self._cookie_authorized():
            return True
        self.send_error(HTTPStatus.UNAUTHORIZED, "Open the access URL printed by ytmp3.")
        return False

    def _send(self, status: int, body: bytes, content_type: str,
              headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "img-src 'self' data:; media-src 'self'; connect-src 'self'; "
                         "base-uri 'none'; form-action 'self'")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, value: object) -> None:
        self._send(status, json.dumps(value).encode("utf-8"), "application/json; charset=utf-8")

    def _asset(self, name: str, content_type: str) -> None:
        self._send(200, (WEB / name).read_bytes(), content_type)

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        if parts.path == "/" and "key" in query:
            supplied = query["key"][0]
            if not hmac.compare_digest(supplied, self.server.key):
                self.send_error(HTTPStatus.UNAUTHORIZED)
                return
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie",
                             f"ytmp3_session={self.server.key}; HttpOnly; SameSite=Lax; Path=/")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not self._authorized():
            return
        if parts.path == "/":
            self._asset("index.html", "text/html; charset=utf-8")
        elif parts.path == "/app.css":
            self._asset("app.css", "text/css; charset=utf-8")
        elif parts.path in {"/app.js", "/playlist-store.js"}:
            self._asset(parts.path[1:], "text/javascript; charset=utf-8")
        elif parts.path == "/manifest.webmanifest":
            self._asset("manifest.webmanifest", "application/manifest+json")
        elif parts.path in {"/icon-192.png", "/icon-512.png"}:
            self._asset(parts.path[1:], "image/png")
        elif parts.path == "/api/tracks":
            self._json(200, {"tracks": self.server.library.tracks()})
        elif parts.path.startswith("/cover/"):
            cover = self.server.library.cover(unquote(parts.path[len("/cover/"):]))
            self._send(200, *cover, headers={"Cache-Control": "no-store"}) if cover else self.send_error(HTTPStatus.NOT_FOUND)
        elif parts.path.startswith("/api/jobs/"):
            job = self.server.library.job(parts.path.rsplit("/", 1)[-1])
            self._json(200, job) if job else self.send_error(HTTPStatus.NOT_FOUND)
        elif parts.path.startswith(("/media/", "/export/")):
            name = unquote(parts.path.split("/", 2)[2])
            self._media(name, download=parts.path.startswith("/export/"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_POST(self) -> None:
        if not self._authorized():
            return
        if self.path not in {"/api/download", "/api/tracks/edit"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        origin = self.headers.get("Origin")
        if origin != f"http://{self.headers.get('Host')}" and origin != f"https://{self.headers.get('Host')}":
            self.send_error(HTTPStatus.FORBIDDEN, "Origin mismatch.")
            return
        if self.headers.get_content_type() != "application/json":
            self.send_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        try:
            size = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid content length.")
            return
        if size < 1 or size > (MAX_COVER * 4 // 3 + MAX_POST if self.path == "/api/tracks/edit" else MAX_POST):
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            body = json.loads(self.rfile.read(size))
            if self.path == "/api/tracks/edit":
                self.server.library.edit_track(body)
            else:
                job_id = self.server.library.submit(body["url"])
        except (ValueError, KeyError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(200, {}) if self.path == "/api/tracks/edit" else self._json(202, {"job": job_id})

    def _media(self, name: str, download: bool) -> None:
        path = self.server.library.file(name)
        if not path:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        size = path.stat().st_size
        try:
            selected = parse_range(self.headers.get("Range"), size)
        except ValueError:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start, end = selected or (0, size - 1)
        length = max(0, end - start + 1)
        self.send_response(206 if selected else 200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Last-Modified", formatdate(path.stat().st_mtime, usegmt=True))
        self.send_header("Cache-Control", "private, max-age=3600")
        self.send_header("X-Content-Type-Options", "nosniff")
        if selected:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download:
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(name)}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                chunk = handle.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ytmp3 app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--library", type=Path, default=Path.home() / "Music" / "ytmp3")
    parser.add_argument("--include", action="append", type=Path, default=[], metavar="FOLDER",
                        help="include MP3s from this folder and its subfolders; repeat to add more")
    opts = parser.parse_args(argv)
    library = Library(opts.library, opts.include)
    server = AppServer((opts.host, opts.port), library)
    display_host = "127.0.0.1" if opts.host == "0.0.0.0" else opts.host
    print(f"ytmp3 app: http://{display_host}:{server.server_port}/?key={server.key}")
    print(f"library: {library.path}")
    for folder in library.includes:
        print(f"included folder: {folder}")
    if opts.host == "0.0.0.0":
        try:
            addresses = {
                item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                if ipaddress.ip_address(item[4][0]).is_private
                and not ipaddress.ip_address(item[4][0]).is_loopback
                and not ipaddress.ip_address(item[4][0]).is_link_local
            }
        except OSError:
            addresses = set()
        for address in sorted(addresses):
            print(f"Android on this network: http://{address}:{server.server_port}/?key={server.key}")
        if not addresses:
            print("For Android, replace 127.0.0.1 with this PC's LAN IP in the access URL.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        library.pool.shutdown(wait=False, cancel_futures=True)
    return 0
