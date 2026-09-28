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
            page.locator(".track-row").first.wait_for()
            assert page.locator(".track-row").count() == 2
            assert page.locator(".track-art img").count() == 2
            assert page.locator(".track-art img").first.evaluate("e => e.naturalWidth") > 0
            page.locator("#sort-tracks").select_option("artist")
            page.get_by_role("button", name="Tile view").click()
            assert page.locator("#track-list").get_attribute("data-layout") == "tiles"
            page.locator(".tile-menu summary").first.click()
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
            assert page.locator(".track-row").count() == 2
            page.locator("#filter").fill("")
            page.locator("#folder-filter").select_option("1:")
            assert page.locator(".track-row").count() == 1
            page.locator("#mix-selection").click()
            assert len(page.evaluate("JSON.parse(localStorage.ytmp3_queue)")) == 1
            page.locator(".tile-menu summary").first.click()
            page.get_by_role("button", name="Edit details and cover").click()
            page.locator("#edit-title").fill("Edited title")
            page.locator("#track-editor button[type=submit]").click()
            page.locator(".track-row strong").get_by_text("Edited title", exact=True).wait_for(timeout=5000)
            assert page.locator(".track-row strong").first.inner_text() == "Edited title"
            page.locator(".tile-menu summary").first.click()
            page.get_by_role("button", name="View info").click()
            assert page.locator("#info-title").inner_text() == "Edited title"
            assert "Tagged artist" in page.locator("#info-details").inner_text()
            page.locator("#close-info").click()
            page.locator(".tile-menu summary").first.click()
            page.get_by_role("button", name="Remove from Library").click()
            page.locator("#confirm-hide").click()
            assert page.locator(".track-row").count() == 0
            page.locator('.nav-item[data-view="settings"]').click()
            page.locator("#hidden-tracks button").click()
            page.locator('.nav-item[data-view="library"]').click()
            assert page.locator(".track-row").count() == 1
            page.locator("#select-mode").click()
            page.locator(".track-select").first.check()
            assert page.locator("#selected-count").inner_text() == "1 selected"
            page.locator("#selected-favorite").click()
            assert page.evaluate("JSON.parse(localStorage.ytmp3_favorites).length") == 1
            page.locator("#clear-selection").click()
            page.locator(".track-meta").first.hover()
            page.mouse.down()
            page.wait_for_timeout(650)
            page.mouse.up()
            assert page.locator("#selection-bar").is_visible()
            assert page.locator("#selected-count").inner_text() == "1 selected"
            page.locator("#clear-selection").click()
            page.locator("#folder-filter").select_option("")
            page.locator("#mix-selection").click()
            before = page.evaluate("JSON.parse(localStorage.ytmp3_queue)")
            page.locator('.nav-item[data-view="queue"]').click()
            assert page.locator(".drag-handle").count() == 2
            page.locator(".drag-handle").first.focus()
            page.keyboard.press("ArrowDown")
            after = page.evaluate("JSON.parse(localStorage.ytmp3_queue)")
            assert after == before[::-1]
            first = page.locator(".drag-handle").first.bounding_box()
            second = page.locator(".drag-handle").nth(1).bounding_box()
            page.mouse.move(first["x"] + 12, first["y"] + 20)
            page.mouse.down()
            page.mouse.move(second["x"] + 12, second["y"] + 20, steps=8)
            page.mouse.up()
            assert page.evaluate("JSON.parse(localStorage.ytmp3_queue)") == before
            page.locator('.nav-item[data-view="library"]').click()
            assert not errors, errors
            page.screenshot(path=str(root / "mobile.png"), full_page=True)
            shutil.copy2(root / "mobile.png", Path(tempfile.gettempdir()) / "ytmp3-mobile-check.png")
            browser.close()
    finally:
        update_stub.stop()
        server.shutdown()
        server.server_close()
        thread.join()
print("UI check passed")
