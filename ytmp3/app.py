"""Small authenticated server for a personal MP3 library."""

import argparse
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

from .config import DEFAULT_TEMPLATE
from .download import download_mp3
from .info import detail
from .naming import fields_for, render

WEB = Path(__file__).with_name("web")
RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")
MAX_POST = 8192


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
                entries.append({"id": track_id, "title": path.stem,
                                "size": stat.st_size, "modified": int(stat.st_mtime)})
        return sorted(entries, key=lambda item: item["modified"], reverse=True)

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
            info = detail(url)
            if not info or info.get("_type") in {"playlist", "multi_video"}:
                raise ValueError("This URL did not resolve to one downloadable item.")
            filename = render(DEFAULT_TEMPLATE, fields_for(info))
            with tempfile.TemporaryDirectory(prefix=".ytmp3-", dir=self.path) as temp:
                produced = download_mp3(url, Path(temp), filename)
                target = self.path / filename
                number = 2
                while target.exists():
                    target = self.path / f"{Path(filename).stem} ({number}).mp3"
                    number += 1
                shutil.move(str(produced), str(target))
            self._set(job_id, state="done", track=target.name)
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
        if self.path != "/api/download":
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
        if size < 1 or size > MAX_POST:
            self.send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            body = json.loads(self.rfile.read(size))
            job_id = self.server.library.submit(body["url"])
        except (ValueError, KeyError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
            return
        self._json(202, {"job": job_id})

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
