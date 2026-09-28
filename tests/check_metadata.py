"""Run with: python tests/check_metadata.py (requires ffmpeg)."""

import base64
import http.client
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ytmp3.app import AppServer, Library


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        image = root / "cover.png"
        image.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg=="))
        track = root / "song.mp3"
        result = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-i", str(image), "-map", "0:a", "-map", "1:v", "-c:a", "libmp3lame", "-q:a", "8",
            "-c:v", "copy", "-disposition:v", "attached_pic", "-metadata", "title=Tagged title",
            "-metadata", "artist=Tagged artist", "-metadata", "album=Tagged album",
            "-id3v2_version", "3", "-y", str(track)],
            capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert result.returncode == 0, result.stderr
        library = Library(root)
        found = library.tracks()[0]
        assert (found["title"], found["artist"], found["album"]) == (
            "Tagged title", "Tagged artist", "Tagged album")
        assert found["artwork"] and found["duration"] > 0
        assert library.cover("song.mp3")[1] == "image/png"
        server = AppServer(("127.0.0.1", 0), library)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
            conn.request("GET", "/cover/song.mp3")
            assert conn.getresponse().status == 401
            conn.close()
            conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
            conn.request("GET", "/cover/song.mp3", headers={"Cookie": f"ytmp3_session={server.key}"})
            response = conn.getresponse()
            assert response.status == 200 and response.getheader("Content-Type") == "image/png"
            assert response.read() == image.read_bytes()
            conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        library.edit_track({"id": "song.mp3", "title": "New title", "artist": "New artist",
                            "album": "New album", "cover": base64.b64encode(image.read_bytes()).decode("ascii")})
        reopened = Library(root)
        assert reopened.tracks()[0]["title"] == "New title"
        assert reopened.cover("song.mp3")[0] == image.read_bytes()
        try:
            reopened.edit_track({"id": "../song.mp3", "title": "Oops"})
            assert False, "A path traversal was accepted"
        except ValueError:
            pass
        reopened.edit_track({"id": "song.mp3", "title": "New title", "artist": "New artist",
                             "album": "New album", "removeCover": True})
        assert reopened.cover("song.mp3")[1] == "image/png"  # Embedded cover remains.


if __name__ == "__main__":
    main()
    print("metadata check passed")
