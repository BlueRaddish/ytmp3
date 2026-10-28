"""Search goes through yt-dlp without downloading and returns bounded, safe links."""
from unittest.mock import MagicMock, patch

import pytest

from ytmp3.app import Library


@pytest.mark.parametrize("query", [None, [], {}, "", "   ", "a" * 201])
def test_search_rejects_invalid_query(tmp_path, query):
    with patch("ytmp3.app.YoutubeDL") as downloader:
        with pytest.raises(ValueError):
            Library(tmp_path).search(query)
        downloader.assert_not_called()


def test_search_resolves_only_flat_youtube_results(tmp_path):
    downloader = MagicMock()
    downloader.extract_info.return_value = {"entries": [None, {"id": "bad-url"}, {
        "id": "abcdefghijk", "title": "A title <script>", "uploader": "An artist",
        "url": "https://attacker.example/redirect", "duration": 63,
        "thumbnails": [{"url": "https://i.ytimg.com/vi/abcdefghijk/default.jpg"}],
    }, {"id": "12345678901", "title": "Another", "thumbnail": "javascript:alert(1)"}]}
    with patch("ytmp3.app.YoutubeDL") as factory:
        factory.return_value.__enter__.return_value = downloader
        result = Library(tmp_path).search("  앨범 artist & title  ")
        downloader.extract_info.assert_called_once_with("ytsearch12:앨범 artist & title", download=False)
        assert factory.call_args.args[0]["extract_flat"] is True
        assert factory.call_args.args[0]["skip_download"] is True
    assert result["query"] == "앨범 artist & title"
    assert len(result["results"]) == 2
    assert result["results"][0]["url"] == "https://www.youtube.com/watch?v=abcdefghijk"
    assert result["results"][0]["creator"] == "An artist"
    assert result["results"][1]["thumbnail"] == ""


def test_search_empty_differs_from_broken_extractor(tmp_path):
    with patch("ytmp3.app.YoutubeDL") as factory:
        extract = factory.return_value.__enter__.return_value.extract_info
        extract.return_value = {"entries": []}
        assert Library(tmp_path).search("no matches")["results"] == []
        extract.return_value = None
        with pytest.raises(RuntimeError, match="Could not search YouTube"):
            Library(tmp_path).search("broken")


def test_search_never_returns_more_than_twelve(tmp_path):
    with patch("ytmp3.app.YoutubeDL") as factory:
        factory.return_value.__enter__.return_value.extract_info.return_value = {
            "entries": [{"id": f"{i:011d}"} for i in range(40)]}
        assert len(Library(tmp_path).search("artist")["results"]) == 12
