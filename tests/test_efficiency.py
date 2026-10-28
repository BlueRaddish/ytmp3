"""Resource bounds are tested through the app's consuming library operations."""
import threading
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from ytmp3.app import Library


def test_malformed_track_edits_keep_library_usable(tmp_path):
    (tmp_path / "one.mp3").write_bytes(b"test")
    (tmp_path / ".ytmp3-track-edits.json").write_text(json.dumps({
        "one.mp3": {"title": [], "artist": {}, "album": "Valid album"}, "another.mp3": None
    }), encoding="utf-8")
    tracks = Library(tmp_path).tracks()
    assert tracks[0]["title"] == "one"
    assert tracks[0]["artist"] == ""
    assert tracks[0]["album"] == "Valid album"


def test_removed_tracks_release_tag_cache(tmp_path):
    library = Library(tmp_path)
    tag = MagicMock(title="Test", artist="Artist", album="Album", duration=1)
    tag.images.any = None
    path = tmp_path / "one.mp3"
    path.write_bytes(b"test")
    with patch("ytmp3.app.TinyTag.get", return_value=tag) as read:
        assert library.tracks()[0]["title"] == "Test"
        assert library.tracks()[0]["title"] == "Test"
        assert read.call_count == 1, "Unchanged tags were re-read"
        path.rename(tmp_path / "renamed.mp3")
        assert library.tracks()[0]["id"] == "renamed.mp3"
        assert len(library.tag_cache) == 1
        (tmp_path / "renamed.mp3").unlink()
        assert library.tracks() == []
        assert not library.tag_cache


def test_search_cache_expires_and_is_bounded(tmp_path):
    library = Library(tmp_path)
    with patch("ytmp3.app.YoutubeDL") as factory, patch("ytmp3.app.time.monotonic", return_value=100) as clock:
        extract = factory.return_value.__enter__.return_value.extract_info
        extract.return_value = {"entries": [{"id": "abcdefghijk", "title": "Original"}]}
        first = library.search("artist")
        first["results"][0]["title"] = "Edited by caller"
        assert library.search("artist")["results"][0]["title"] == "Original"
        assert extract.call_count == 1
        clock.return_value = 161
        library.search("artist")
        assert extract.call_count == 2
        for i in range(20):
            library.search(f"artist {i}")
        assert len(library.search_cache) == 16
        assert "artist" not in library.search_cache
        clock.return_value = 222
        library.search("fresh")
        assert list(library.search_cache) == ["fresh"]


def test_failed_search_is_retryable(tmp_path):
    library = Library(tmp_path)
    with patch("ytmp3.app.YoutubeDL") as factory:
        extract = factory.return_value.__enter__.return_value.extract_info
        extract.side_effect = OSError("offline")
        for _ in range(3):
            with pytest.raises(RuntimeError, match="Could not search"):
                library.search("artist")
        assert not library.search_cache
        extract.side_effect = None
        extract.return_value = {"entries": []}
        assert library.search("artist")["results"] == []


def test_search_limits_expensive_concurrency(tmp_path):
    library = Library(tmp_path)
    release = threading.Event()
    started = threading.Event()
    lock = threading.Lock()
    entered = 0

    def extract(*args, **kwargs):
        nonlocal entered
        with lock:
            entered += 1
            if entered == 2:
                started.set()
        assert release.wait(5), "Test worker was not released"
        return {"entries": []}

    with patch("ytmp3.app.YoutubeDL") as factory, ThreadPoolExecutor(max_workers=2) as pool:
        factory.return_value.__enter__.return_value.extract_info.side_effect = extract
        futures = [pool.submit(library.search, query) for query in ["one", "two"]]
        try:
            assert started.wait(5), "The two allowed workers did not start"
            with pytest.raises(RuntimeError, match="Search is busy"):
                library.search("three")
            assert entered == 2
        finally:
            release.set()
        assert all(future.result()["results"] == [] for future in futures)
