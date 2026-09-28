"""Run with: python tests/check_updates.py."""

import json
import http.client
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ytmp3.updates import check, newer
from ytmp3.app import AppServer, Library


class Response:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, limit):
        return self.data[:limit]


def check_manifest(payload):
    with patch("ytmp3.updates.urlopen", return_value=Response(json.dumps(payload).encode())):
        return check("0.4.0")


def main():
    assert newer("0.5.0", "0.4.9")
    assert not newer("0.4.0", "0.4.0")
    assert check_manifest({"version": "0.5.0",
        "android_apk_url": "https://drive.google.com/open?id=abc", "notes": "New features"})["available"]
    assert not check_manifest({"version": "0.3.0",
        "android_apk_url": "https://drive.google.com/open?id=abc"})["available"]
    for bad in ["http://drive.google.com/open?id=abc", "https://example.com/app.apk",
                "https://drive.google.com@evil.example/app.apk", "https://drive.google.com:8443/app.apk"]:
        try:
            check_manifest({"version": "0.5.0", "android_apk_url": bad})
            assert False, "An untrusted update link was accepted"
        except ValueError:
            pass
    with tempfile.TemporaryDirectory() as temp:
        library = Library(Path(temp))
        server = AppServer(("127.0.0.1", 0), library)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            cookie = f"ytmp3_session={server.key}"
            with patch("ytmp3.app.check_updates", return_value={
                "current": "0.5.0", "version": "0.6.0", "available": True,
                "android_apk_url": "https://drive.google.com/open?id=abc", "notes": "Next"}):
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.request("GET", "/api/update", headers={"Cookie": cookie})
                result = connection.getresponse()
                assert result.status == 200 and json.loads(result.read())["available"]
                connection.close()
            assert server.update_version == "0.6.0"
            headers = {"Cookie": cookie, "Content-Type": "application/json",
                       "Origin": f"http://127.0.0.1:{port}"}
            with patch.object(server, "install_update", return_value={"state": "working"}):
                connection = http.client.HTTPConnection("127.0.0.1", port)
                connection.request("POST", "/api/update/install", "{}", headers)
                result = connection.getresponse()
                assert result.status == 202 and json.loads(result.read())["state"] == "working"
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
            library.pool.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
    print("update checks passed")
