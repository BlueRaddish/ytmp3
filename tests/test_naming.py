from ytmp3.naming import clean_title, fields_for, render, sanitize


def test_strips_leading_tag_and_trailing_marker():
    assert clean_title("[MV] Gift(선물)") == "Gift(선물)"
    assert clean_title("iKON - 취향저격(MY TYPE) M/V", artist="iKON") == "취향저격(MY TYPE)"


def test_strips_bracketed_cruft_but_keeps_meaning():
    assert clean_title("Painkiller (Official Video)") == "Painkiller"
    assert clean_title("시간이 들겠지 (Feat. Colde)") == "시간이 들겠지 (Feat. Colde)"
    assert clean_title("BABYDOLL (Lyric Video)") == "BABYDOLL"
    assert clean_title("Stray Nights (Hyperpop SPED UP)") == "Stray Nights (Hyperpop SPED UP)"


def test_never_returns_empty():
    assert clean_title("(Official Video)") == "(Official Video)"


def test_sanitize_removes_illegal_characters():
    assert sanitize('AC/DC: Back "Home"?') == "ACDC Back Home"
    assert sanitize("trailing dots...") == "trailing dots"
    assert sanitize("CON") == "_CON"


def test_render_applies_template():
    fields = {"title": "High Hopes", "artist": "Panic! At The Disco",
              "album": "", "year": "2018", "id": "abc"}
    assert render("[Music] {title}.mp3", fields) == "[Music] High Hopes.mp3"
    assert render("{artist} - {title}.mp3", fields) == "Panic! At The Disco - High Hopes.mp3"


def test_render_drops_separator_when_field_is_empty():
    fields = {"title": "Serenade", "artist": "", "album": "", "year": "", "id": ""}
    assert render("{artist} - {title}.mp3", fields) == "Serenade.mp3"


def test_render_rejects_unknown_field():
    fields = {"title": "x", "artist": "", "album": "", "year": "", "id": ""}
    try:
        render("{nope}.mp3", fields)
    except ValueError as exc:
        assert "nope" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_fields_prefer_catalog_metadata():
    info = {"title": "Tom Frane - Stray Nights (Lyrics)", "track": "Stray Nights",
            "artist": "Tom Frane", "album": "Stray Nights", "release_year": 2023,
            "id": "x"}
    fields = fields_for(info)
    assert fields["title"] == "Stray Nights"
    assert fields["year"] == "2023"


def test_fields_fall_back_to_cleaned_video_title():
    info = {"title": "Ruel - Painkiller (Official Video)", "uploader": "RUEL", "id": "y"}
    assert fields_for(info)["title"] == "Painkiller"


def test_name_override_wins():
    info = {"title": "whatever", "track": "Catalog Name", "id": "z"}
    assert fields_for(info, "My Name")["title"] == "My Name"


def test_topic_suffix_stripped_from_artist():
    info = {"title": "Johnny", "uploader": "Primary - Topic", "id": "w"}
    assert fields_for(info)["artist"] == "Primary"
