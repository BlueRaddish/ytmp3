import base64
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ytmp3.app import AppServer, Library

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    library_dir = root / "Downloads"
    include = root / "Music"
    (include / "Album").mkdir(parents=True)
    library_dir.mkdir()
    image = root / "cover.png"
    image.write_bytes(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg=="))
    track = library_dir / "song.mp3"
    result = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=duration=1",
        "-i", str(image), "-map", "0:a", "-map", "1:v", "-c:a", "libmp3lame", "-q:a", "8",
        "-c:v", "copy", "-disposition:v", "attached_pic", "-metadata", "title=Tagged title",
        "-metadata", "artist=Tagged artist", "-metadata", "album=Tagged album",
        "-id3v2_version", "3", "-y", str(track)], capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert result.returncode == 0, result.stderr
    shutil.copy2(track, include / "Album" / "other.mp3")
    server = AppServer(("127.0.0.1", 0), Library(library_dir, [include]))
    update_stub = patch("ytmp3.app.check_updates", return_value={
        "current": "0.5.0", "version": "0.5.0", "available": False,
        "notes": "", "android_apk_url": "https://drive.google.com/open?id=test"})
    update_stub.start()
    preview_stub = patch.object(server.library, "preview", return_value={
        "title": "Preview test tone", "site": "example.org", "creator": "Test artist",
        "kind": "track", "thumbnail": ""})
    preview_stub.start()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
            browser = playwright.chromium.launch(executable_path=str(edge) if edge.exists() else None,
                headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/?key={server.key}")
            page.locator("#track-list .track-row").first.wait_for()
            assert page.locator("#play-selection .action-icon").count() == 1
            assert page.locator("#mix-selection .action-icon path").count() == 1
            assert page.locator("#mix-selection").get_attribute("aria-label") == "Mix visible tracks"
            assert page.locator("#play-selection").bounding_box()["height"] >= 44
            assert page.locator("#track-list .track-row").count() == 2
            assert page.locator("#track-list .track-art img").count() == 2
            assert page.locator("#track-list .track-art img").first.evaluate("e => e.naturalWidth") > 0
            page.locator("#sort-tracks").select_option("artist")
            page.get_by_role("button", name="Tile view").click()
            assert page.locator("#track-list").get_attribute("data-layout") == "tiles"
            page.locator(".tile-menu summary").first.click()
            page.wait_for_function("""() => {
                const menu = document.querySelector('.tile-options').getBoundingClientRect();
                const player = document.querySelector('#player').getBoundingClientRect();
                return menu.bottom <= player.top + 1;
            }""")
            menu = page.locator(".tile-options").first.bounding_box()
            player = page.locator("#player").bounding_box()
            topbar = page.locator(".topbar").bounding_box()
            assert menu and menu["y"] >= topbar["y"] + topbar["height"] - 1
            assert menu["y"] + menu["height"] <= player["y"] + 1
            assert menu["x"] >= 0 and menu["x"] + menu["width"] <= 390
            page.locator(".tile-menu summary").first.click()
            page.get_by_role("button", name="Compact view").click()
            assert page.locator("#track-list").get_attribute("data-layout") == "compact"
            page.get_by_role("button", name="List view").click()
            page.locator("#filter").fill("Tagged artist")
            assert page.locator("#track-list .track-row").count() == 2
            page.locator("#filter").fill("")
            page.locator("#folder-filter").select_option("1:")
            assert page.locator("#track-list .track-row").count() == 1
            page.locator("#mix-selection").click()
            assert len(page.evaluate("JSON.parse(localStorage.ytmp3_queue)")) == 1
            page.locator(".tile-menu summary").first.click()
            page.get_by_role("button", name="Edit details and cover").click()
            page.locator("#edit-title").fill("Edited title")
            page.locator("#track-editor button[type=submit]").click()
            page.locator("#track-list .track-row strong").get_by_text("Edited title", exact=True).wait_for(timeout=5000)
            assert page.locator("#track-list .track-row strong").first.inner_text() == "Edited title"
            page.locator(".tile-menu summary").first.click()
            page.get_by_role("button", name="View info").click()
            assert page.locator("#info-title").inner_text() == "Edited title"
            assert "Tagged artist" in page.locator("#info-details").inner_text()
            page.locator("#close-info").click()
            page.locator(".tile-menu summary").first.click()
            page.get_by_role("button", name="Remove from Library").click()
            page.locator("#confirm-hide").click()
            assert page.locator("#track-list .track-row").count() == 0
            page.locator('.nav-item[data-view="more"]').click()
            page.locator("#hidden-tracks button").click()
            page.locator('.nav-item[data-view="audio"]').click()
            assert page.locator("#track-list .track-row").count() == 1
            page.locator("#select-mode").click()
            page.locator(".track-select").first.check()
            assert page.locator("#selected-count").inner_text() == "1 selected"
            assert page.locator("#selected-play .action-icon").count() == 1
            assert page.locator("#selected-queue .action-icon").count() == 1
            page.locator("#selected-favorite").click()
            assert page.evaluate("JSON.parse(localStorage.ytmp3_favorites).length") == 1
            page.locator("#clear-selection").click()
            page.locator("#track-list .track-meta").first.hover()
            page.mouse.down()
            page.wait_for_timeout(650)
            page.mouse.up()
            assert page.locator("#selection-bar").is_visible()
            assert page.locator("#selected-count").inner_text() == "1 selected"
            page.locator("#clear-selection").click()
            page.locator("#folder-filter").select_option("")
            page.locator("#mix-selection").click()
            before = page.evaluate("JSON.parse(localStorage.ytmp3_queue)")
            assert page.locator('.nav-item').count() == 4
            page.locator("#expand-player").click()
            assert page.locator("#player-queue").is_visible()
            assert page.locator("#player").get_attribute("data-panel") == "queue"
            assert page.locator("#queue-mix .action-icon").count() == 1
            assert page.locator("#queue-loop .action-icon").count() == 1
            assert page.locator("#queue-list .drag-handle").count() == 2
            assert page.locator("#queue-list .drag-handle").first.inner_text() == "⠿"
            bounds = page.locator("#queue-list").bounding_box()
            assert bounds["x"] == 0 and bounds["width"] == 390
            banner_y = page.locator("#expand-player").bounding_box()["y"]
            page.locator("#queue-list").evaluate("e => { const spacer = document.createElement('div'); spacer.id = 'scroll-check'; spacer.style.height = '1200px'; e.append(spacer); e.scrollTop = 300; }")
            assert page.locator("#queue-list").evaluate("e => e.scrollTop") > 0
            assert page.locator("#expand-player").bounding_box()["y"] == banner_y
            page.locator("#scroll-check").evaluate("e => e.remove()")
            page.locator("#queue-list").evaluate("e => e.scrollTop = 0")
            page.screenshot(path=str(root / "queue.png"), full_page=True)
            shutil.copy2(root / "queue.png", Path(tempfile.gettempdir()) / "ytmp3-queue-check.png")
            page.locator("#expand-player").click()
            assert page.locator("#player").get_attribute("data-panel") == "song"
            assert not page.locator("#player-queue").is_visible()
            assert page.locator(".player-art").bounding_box()["width"] > 200
            assert page.locator("#close-player").is_visible()
            page.screenshot(path=str(root / "song.png"), full_page=True)
            shutil.copy2(root / "song.png", Path(tempfile.gettempdir()) / "ytmp3-song-check.png")
            page.locator("#back-to-queue").click()
            assert page.locator("#player-queue").is_visible()
            page.locator("#queue-list .drag-handle").first.focus()
            page.keyboard.press("ArrowDown")
            after = page.evaluate("JSON.parse(localStorage.ytmp3_queue)")
            assert after == before[::-1]
            first = page.locator("#queue-list .drag-handle").first.bounding_box()
            second = page.locator("#queue-list .drag-handle").nth(1).bounding_box()
            page.mouse.move(first["x"] + 12, first["y"] + 20)
            page.mouse.down()
            page.mouse.move(second["x"] + 12, second["y"] + 20, steps=8)
            page.mouse.up()
            assert page.evaluate("JSON.parse(localStorage.ytmp3_queue)") == before
            page.locator("#queue-loop").click()
            assert page.locator("#queue-loop").get_attribute("aria-pressed") == "true"
            page.locator("#queue-mix").click()
            assert page.locator("#queue-mix").get_attribute("aria-pressed") == "true"
            page.locator("#queue-options summary").click()
            page.locator("#save-queue").click()
            page.locator("#queue-name").fill("Test queue")
            page.locator("#save-queue-form button[type=submit]").click()
            page.locator("#queue-list").dispatch_event("wheel", {"deltaY": -120})
            assert page.locator("#player").get_attribute("data-panel") == "song"
            page.wait_for_timeout(650)
            page.locator("#player").dispatch_event("wheel", {"deltaY": -120})
            page.wait_for_function("!document.body.classList.contains('player-open')")
            page.locator('.nav-item[data-view="playlists"]').click()
            assert page.locator('.nav-item[data-view="playlists"] .nav-list-icon').count() == 1
            assert page.locator(".playlist-card").count() == 1
            assert page.locator("#new-playlist .action-icon").count() == 1
            assert page.locator("#playlist-play .action-icon").count() == 1
            page.locator("#new-playlist").click()
            page.locator("#new-playlist-name").fill("Another playlist")
            page.locator("#create-playlist button[type=submit]").click()
            assert page.locator(".playlist-card").count() == 2
            page.screenshot(path=str(root / "playlists.png"), full_page=True)
            shutil.copy2(root / "playlists.png", Path(tempfile.gettempdir()) / "ytmp3-playlists-check.png")
            page.locator('.nav-item[data-view="more"]').click()
            page.locator("#check-update").wait_for(state="visible")
            assert page.locator("#hidden-tracks").count() == 0
            assert page.locator("#check-update .action-icon").count() == 1
            assert page.locator("#check-update").bounding_box()["y"] < page.locator("#player").bounding_box()["y"]
            page.locator(".about-details summary").click()
            assert page.get_by_text("Downloads use").is_visible()
            page.locator('.nav-item[data-view="audio"]').click()
            assert not errors, errors
            page.screenshot(path=str(root / "mobile.png"), full_page=True)
            shutil.copy2(root / "mobile.png", Path(tempfile.gettempdir()) / "ytmp3-mobile-check.png")
            desktop = browser.new_page(viewport={"width": 1440, "height": 900})
            desktop.on("pageerror", lambda error: errors.append(str(error)))
            desktop.goto(f"http://127.0.0.1:{server.server_port}/?key={server.key}")
            desktop.locator("#track-list .track-row").first.wait_for()
            desktop.screenshot(path=str(root / "desktop.png"), full_page=True)
            shutil.copy2(root / "desktop.png", Path(tempfile.gettempdir()) / "ytmp3-desktop-check.png")
            desktop.locator("#expand-player").click()
            assert desktop.locator("#player-queue").is_visible()
            assert desktop.locator("#queue-options").is_visible()
            desktop.locator("#close-player").click()
            desktop.locator('.nav-item[data-view="browse"]').click()
            desktop.locator("#url-input").fill("https://example.org/tone")
            desktop.locator("#link-preview strong").wait_for()
            assert desktop.locator("#link-preview").evaluate("e => getComputedStyle(e).position") == "absolute"
            desktop.screenshot(path=str(root / "desktop-browse.png"), full_page=True)
            shutil.copy2(root / "desktop-browse.png", Path(tempfile.gettempdir()) / "ytmp3-desktop-browse-check.png")
            desktop.close()
            tablet = browser.new_page(viewport={"width": 768, "height": 900})
            tablet.goto(f"http://127.0.0.1:{server.server_port}/?key={server.key}")
            tablet.locator("#track-list .track-row").first.wait_for()
            tablet.locator("#theme-button").click()
            assert tablet.locator("html").get_attribute("data-theme") == "light"
            tablet.locator("#play-selection").click()
            tablet.locator("#expand-player").click()
            assert tablet.locator("#queue-list").bounding_box()["width"] <= 768
            tablet.screenshot(path=str(root / "tablet-queue.png"), full_page=True)
            shutil.copy2(root / "tablet-queue.png", Path(tempfile.gettempdir()) / "ytmp3-tablet-queue-check.png")
            tablet.locator("#expand-player").click()
            tablet.screenshot(path=str(root / "tablet-song.png"), full_page=True)
            shutil.copy2(root / "tablet-song.png", Path(tempfile.gettempdir()) / "ytmp3-tablet-song-check.png")
            tablet.close()
            shared = browser.new_page(viewport={"width": 390, "height": 844})
            shared.goto(f"http://127.0.0.1:{server.server_port}/?key={server.key}")
            shared.goto(f"http://127.0.0.1:{server.server_port}/?url=https%3A%2F%2Fexample.org%2Ftone")
            assert shared.locator('.nav-item[data-view="browse"]').get_attribute("aria-current") == "page"
            assert shared.locator("#url-input").input_value() == "https://example.org/tone"
            assert shared.locator("#url-form button .action-icon").count() == 1
            shared.locator("#link-preview strong").wait_for()
            assert shared.locator("#link-preview strong").inner_text() == "Preview test tone"
            assert shared.locator("#browse-tracks .track-row").count() == 2
            assert shared.locator("#browse-tracks .track-meta span").first.is_visible()
            assert shared.locator(".browse-library").bounding_box()["y"] - shared.locator(".download-panel").bounding_box()["y"] - shared.locator(".download-panel").bounding_box()["height"] >= 20
            shared.screenshot(path=str(root / "browse.png"), full_page=True)
            shutil.copy2(root / "browse.png", Path(tempfile.gettempdir()) / "ytmp3-browse-check.png")
            shared.locator("#browse-folder").select_option("1:")
            assert shared.locator("#browse-tracks .track-row").count() == 1
            shared.locator("#browse-folder").select_option("")
            shared.locator("#browse-search").fill("other")
            assert shared.locator("#browse-tracks .track-row").count() == 1
            shared.locator("#browse-search").fill("")
            shared.locator("#browse-tracks .track-meta").first.click()
            assert shared.locator("#player-title").inner_text() != "Nothing playing"
            shared.locator("#browse-tracks .tile-menu summary").first.click()
            shared.get_by_role("button", name="Remove from Library").click()
            shared.locator("#confirm-hide").click()
            assert shared.locator("#browse-tracks .track-row").count() == 1
            shared.close()
            assert not errors, errors
            browser.close()
    finally:
        update_stub.stop()
        preview_stub.stop()
        server.shutdown()
        server.server_close()
        thread.join()
print("UI check passed")
