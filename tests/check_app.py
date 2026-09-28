"""Run with: python tests/check_app.py"""

import http.client
import math
import struct
import sys
import tempfile
import threading
import time
import wave
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ytmp3.app as app
from ytmp3.app import AppServer, Library, parse_range
from ytmp3.info import source_items


def request(port, method, path, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.request(method, path, body=body, headers=headers or {})
    response = conn.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    conn.close()
    return result


def main():
    assert parse_range("bytes=2-4", 10) == (2, 4)
    assert parse_range("bytes=-3", 10) == (7, 9)
    with patch("ytmp3.info.YoutubeDL") as fake:
        fake.return_value.__enter__.return_value.extract_info.return_value = {
            "_type": "playlist", "title": "My list", "entries": [
                {"id": "abc", "ie_key": "Youtube", "title": "One"},
                {"url": "https://example.org/two", "title": "Two"}, None]}
        items, skipped, title = source_items("https://example.org/list", limit=3)
        assert title == "My list" and skipped == 1 and len(items) == 2
        assert items[0]["source_url"] == "https://www.youtube.com/watch?v=abc"
        try:
            source_items("https://open.spotify.com/playlist/example")
            raise AssertionError("Spotify playlist should be rejected")
        except ValueError as error:
            assert "M3U" in str(error)
        fake.return_value.__enter__.return_value.extract_info.return_value["entries"] *= 2
        try:
            source_items("https://example.org/list", limit=3)
            raise AssertionError("oversized playlist should be rejected")
        except ValueError as error:
            assert "more than 3" in str(error)
    with tempfile.TemporaryDirectory() as temp:
        included = Path(temp) / "existing" / "album"
        included.mkdir(parents=True)
        (included / "imported.mp3").write_bytes(b"abcdefghij")
        library = Library(Path(temp) / "downloaded", [included.parent])
        (library.path / "sample.mp3").write_bytes(b"0123456789")
        assert library.file("@0/album/imported.mp3") == included / "imported.mp3"
        assert library.file("@0/../downloaded/sample.mp3") is None
        assert library.file("@1/album/imported.mp3") is None
        server = AppServer(("127.0.0.1", 0), library)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            assert request(port, "GET", "/api/tracks")[0] == 401
            status, headers, _ = request(port, "GET", f"/?key={server.key}")
            assert status == 303
            cookie = headers["Set-Cookie"].split(";", 1)[0]
            status, _, data = request(port, "GET", "/api/tracks", {"Cookie": cookie})
            assert status == 200 and b"sample.mp3" in data and b"@0/album/imported.mp3" in data
            assert request(port, "GET", "/playlist-store.js", {"Cookie": cookie})[0] == 200
            status, headers, data = request(port, "GET", "/media/sample.mp3",
                                            {"Cookie": cookie, "Range": "bytes=2-4"})
            assert status == 206 and data == b"234"
            assert headers["Content-Range"] == "bytes 2-4/10"
            status, _, data = request(port, "GET", "/media/%400%2Falbum%2Fimported.mp3",
                                      {"Cookie": cookie, "Range": "bytes=1-3"})
            assert status == 206 and data == b"bcd"
            assert request(port, "GET", "/media/..%2Fsample.mp3", {"Cookie": cookie})[0] == 404
            assert request(port, "POST", "/api/download",
                           {"Cookie": cookie, "Content-Type": "application/json",
                            "Origin": "http://evil.test"},
                           b'{"url":"https://example.org/test"}')[0] == 403
            assert request(port, "POST", "/api/download",
                           {"Cookie": cookie, "Content-Type": "application/json",
                            "Origin": f"http://127.0.0.1:{port}"},
                           b'{"url":42}')[0] == 400
        finally:
            server.shutdown()
            server.server_close()
            library.pool.shutdown(wait=False, cancel_futures=True)

    # A failed playlist entry must not discard completed files.
    with tempfile.TemporaryDirectory() as temp:
        library = Library(Path(temp) / "library")
        library.jobs["batch"] = {"id": "batch", "state": "queued"}
        items = [{"title": "One", "id": "one", "source_url": "https://example.org/one"},
                 {"title": "Two", "id": "two", "source_url": "https://example.org/two"}]

        def fake_download(url, workdir, filename):
            if url.endswith("two"):
                raise OSError("unavailable")
            path = workdir / filename
            path.write_bytes(b"mp3")
            return path

        with patch.object(app, "source_items", return_value=(items, 0, "Test playlist")), \
             patch.object(app, "validate_source", side_effect=lambda url: url), \
             patch.object(app, "download_mp3", side_effect=fake_download), \
             patch.object(app.logging, "exception"):
            library._download("batch", "https://example.org/list")
        job = library.job("batch")
        assert job["state"] == "done" and job["saved"] == 1 and job["failed"] == 1, job
        assert job["playlist"] == "Test playlist" and job["tracks"] == [job["track"]]
        assert (library.path / job["track"]).read_bytes() == b"mp3"
        library.pool.shutdown(wait=False, cancel_futures=True)

    # Exercise yt-dlp and ffmpeg against audio generated by this check itself.
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        with wave.open(str(folder / "own-tone.wav"), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(8000)
            samples = b"".join(struct.pack("<h", int(9000 * math.sin(n * .08)))
                               for n in range(8000))
            out.writeframes(samples)
        source = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=temp))
        thread = threading.Thread(target=source.serve_forever, daemon=True)
        thread.start()
        original = app.validate_source
        app.validate_source = lambda url: url  # Allow the owned local test source.
        library = Library(folder / "library")
        try:
            job_id = library.submit(f"http://127.0.0.1:{source.server_port}/own-tone.wav")
            for _ in range(100):
                job = library.job(job_id)
                if job["state"] in {"done", "error"}:
                    break
                time.sleep(.1)
            assert job["state"] == "done", job
            assert library.file(job["track"]).stat().st_size > 1000
        finally:
            app.validate_source = original
            source.shutdown()
            source.server_close()
            library.pool.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
