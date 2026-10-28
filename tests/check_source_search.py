"""Drive search, previews, custom sources and recovery in a real headless browser.

External results/downloads are controlled fixtures; live sites are a separate probe.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import patch

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ytmp3.app import AppServer, Library

EVIDENCE = Path(os.environ.get("YTMP3_EVIDENCE", tempfile.gettempdir())) / "ytmp3-source-search"
EVIDENCE.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory() as temp:
    library = Library(Path(temp))
    server = AppServer(("127.0.0.1", 0), library)
    base = f"http://127.0.0.1:{server.server_port}"
    selected = []
    searches = []

    def search(query):
        searches.append(query)
        if query == "slow":
            time.sleep(.6)
        if query == "offline":
            raise RuntimeError("Could not search YouTube. Check your connection and try again.")
        return {"results": [] if query == "nothing" else [{
            "url": "https://www.youtube.com/watch?v=abcdefghijk", "title": f"{query} <script> example",
            "creator": "Test artist", "duration": 91, "thumbnail": ""}]}

    def submit(url):
        selected.append(url)
        return "test-job"

    patches = [patch.object(library, "search", side_effect=search), patch.object(library, "submit", side_effect=submit),
        patch.object(library, "job", return_value={"state": "done", "saved": 1, "total": 1}),
        patch("ytmp3.app.check_updates", return_value={"current": "1.0.0", "version": "1.0.0", "available": False})]
    for item in patches: item.start()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
            browser = pw.chromium.launch(executable_path=str(edge) if edge.exists() else None, headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{base}/?key={server.key}#browse")
            field = page.locator("#url-input")
            field.fill("Test artist")
            page.get_by_role("button", name="Search YouTube", exact=True).click()
            page.get_by_role("button", name="Preview Test artist <script> example", exact=True).wait_for()
            assert not selected, "A search downloaded audio"
            page.locator(".search-result").click()
            assert page.locator("#source-preview-dialog").evaluate("e => e.open")
            assert page.locator("#source-preview-content iframe").get_attribute("src") == "https://www.youtube-nocookie.com/embed/abcdefghijk"
            assert page.locator("#source-preview-open").get_attribute("rel") == "noopener noreferrer"
            page.keyboard.press("Escape")
            page.locator("#source-preview-content iframe").wait_for(state="detached")
            assert page.locator("#source-preview-content iframe").count() == 0
            assert page.evaluate("!!document.activeElement.closest('.search-result')"), "Preview did not restore focus"
            assert field.input_value() == "Test artist"
            page.locator(".search-result").click()
            page.locator("#save-source-preview").click()
            page.wait_for_function("() => document.querySelector('#job-container').textContent.includes('Saved')")
            assert selected == ["https://www.youtube.com/watch?v=abcdefghijk"]
            assert field.input_value() == "Test artist", "Completion erased the search query"
            assert page.locator(".search-result").count() == 1
            field.fill("slow")
            field.press("Enter")
            page.get_by_text("Searching YouTube…", exact=True).wait_for()
            field.fill("newer")
            field.press("Enter")
            page.get_by_role("button", name="Preview newer <script> example", exact=True).wait_for()
            page.wait_for_timeout(800)
            assert page.locator(".search-result strong").inner_text() == "newer <script> example"
            field.fill("nothing")
            field.press("Enter")
            page.get_by_text("No results. Try a different name or artist.", exact=True).wait_for()
            field.fill("offline")
            field.press("Enter")
            page.get_by_role("button", name="Retry search").wait_for()
            assert field.input_value() == "offline"
            field.fill("Fixture artist")
            field.press("Enter")
            page.locator(".search-result").wait_for()
            for theme, width in [("dark", 1280), ("light", 390), ("dark", 320)]:
                page.evaluate("theme => { state.settings.theme = theme; persistSettings(); }", theme)
                page.set_viewport_size({"width": width, "height": 900})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(EVIDENCE / f"results-{theme}-{width}.png"), full_page=True)
            page.emulate_media(reduced_motion="reduce")
            page.locator("#source-select").select_option("manage")
            page.keyboard.press("Tab")
            assert page.evaluate("!!document.activeElement.closest('#source-dialog')"), "Source dialog lost keyboard focus"
            page.locator("#source-name").fill("Example source")
            page.locator("#source-template").fill("https://example.com/search")
            page.get_by_role("button", name="Save source", exact=True).click()
            assert "{query}" in page.locator("#source-error").inner_text()
            assert page.locator("#source-name").input_value() == "Example source"
            page.locator("#source-template").fill("javascript:alert('{query}')")
            page.get_by_role("button", name="Save source", exact=True).click()
            assert page.locator("#source-error").inner_text()
            page.locator("#source-template").fill("example.com/search?q={query}")
            page.get_by_role("button", name="Save source", exact=True).click()
            assert page.get_by_text("Example source saved and selected.", exact=True).is_visible()
            source_id = page.locator("#source-select").input_value()
            page.screenshot(path=str(EVIDENCE / "custom-source.png"), full_page=True)
            page.locator("#close-sources").click()
            assert field.input_value() == "Fixture artist"
            page.reload()
            assert page.locator("#source-select").input_value() == source_id
            page.route("https://example.com/**", lambda route: route.fulfill(body="<h1>Search fixture</h1>", content_type="text/html"))
            field.fill("앨범 & title")
            field.press("Enter")
            frame = page.locator("#source-preview-content iframe")
            assert frame.get_attribute("src") == "https://example.com/search?q=%EC%95%A8%EB%B2%94%20%26%20title"
            page.locator("#save-source-preview").click()
            assert page.locator("#source-preview-error").inner_text()
            assert len(selected) == 1
            page.keyboard.press("Escape")
            page.locator("#source-select").select_option("manage")
            page.get_by_role("button", name="Edit Example source", exact=True).click()
            page.locator("#source-name").fill("Renamed source")
            page.get_by_role("button", name="Save source", exact=True).click()
            page.get_by_role("button", name="Remove Renamed source", exact=True).click()
            assert page.locator("#source-select").input_value() == "youtube"
            page.locator("#close-sources").click()
            field.fill("https://example.com/track")
            assert page.get_by_role("button", name="Save MP3 from link", exact=True).is_visible()
            field.press("Enter")
            page.wait_for_function("() => document.querySelector('#job-container').textContent.includes('Saved')")
            assert selected[-1] == "https://example.com/track"
            # Exercise the Android UI adapter separately from real native-device coverage.
            native = browser.new_page(viewport={"width": 390, "height": 844})
            native.add_init_script("""window.__opened = []; window.Ytmp3Android = {
              openSourcePreview(...args) { window.__opened.push(args); }, cachedTracks() { return '{"tracks":[]}'; },
              refreshTracks() {}, playback() { return '{}'; }, checkAppUpdate() {}
            };""")
            native.goto(f"{base}/?key={server.key}#browse")
            native.locator("#url-input").fill("Some artist & song")
            native.locator("#url-input").press("Enter")
            opened = native.evaluate("window.__opened")
            assert opened[0][0] == "https://www.youtube.com/results?search_query=Some%20artist%20%26%20song"
            assert opened[0][1] is True
            assert native.locator("#source-preview-content iframe").count() == 0, "Untrusted content entered the bridged app WebView"
            assert not errors, errors
            browser.close()
    finally:
        for item in patches: item.stop()
        server.shutdown()
        server.server_close()
        library.pool.shutdown(wait=True)
        thread.join()
print("source search browser checks passed: search, preview/save, stale/empty/error, custom CRUD, persistence, native adapter, themes/widths")
print(f"evidence: {EVIDENCE}")
