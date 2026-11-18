"""Controlled native-adapter UI checks; real SAF export still requires Android."""
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ytmp3.app import AppServer, Library

evidence = Path(os.environ.get("YTMP3_EVIDENCE", tempfile.gettempdir())) / "playback-reports"
evidence.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
    library = Library(Path(temp))
    server = AppServer(("127.0.0.1", 0), library)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with patch("ytmp3.app.check_updates", return_value={"available": False}), sync_playwright() as pw:
            edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
            browser = pw.chromium.launch(executable_path=str(edge) if edge.exists() else None, headless=True)
            page = browser.new_page(viewport={"width": 390, "height": 844})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.add_init_script("""window.__exports = 0; window.Ytmp3Android = {
                cachedTracks() { return '{"tracks":[]}'; }, refreshTracks() {},
                playback() { return '{}'; }, folders() { return '[]'; }, checkAppUpdate() {},
                exportPlaybackReport() { window.__exports++; }
            };""")
            page.goto(f"http://127.0.0.1:{server.server_port}/?key={server.key}#more")
            button = page.get_by_role("button", name="Export playback report", exact=True)
            button.scroll_into_view_if_needed()
            before = page.evaluate("JSON.stringify({queue:state.queue,settings:state.settings})")
            button.focus()
            page.keyboard.press("Enter")
            assert page.evaluate("window.__exports") == 1
            assert page.get_by_role("button", name="Choose a location…").is_disabled()
            page.evaluate("renderMore()")
            assert page.get_by_role("button", name="Saving report…").is_disabled()
            page.evaluate("window.ytmp3PlaybackReportResult('cancelled')")
            button = page.get_by_role("button", name="Export playback report", exact=True)
            assert button.is_enabled()
            for outcome in ["saved", "error"]:
                button.click()
                page.evaluate("window.ytmp3PlaybackReportResult('saving')")
                assert page.get_by_role("button", name="Saving report…").is_disabled()
                page.evaluate(f"window.ytmp3PlaybackReportResult({json.dumps(outcome)})")
                assert button.is_enabled()
            assert page.evaluate("window.__exports") == 3
            assert page.evaluate("JSON.stringify({queue:state.queue,settings:state.settings})") == before
            assert page.evaluate("state.view") == "more"
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            for theme in ["light", "dark"]:
                page.select_option("#theme-setting", theme)
                button.scroll_into_view_if_needed()
                page.evaluate("Promise.all(document.getAnimations().filter(a => a.effect.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))")
                colors = button.evaluate("e => ({ink:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor})")
                def luminance(value):
                    channels = [int(n)/255 for n in re.findall(r"\d+", value)[:3]]
                    linear = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in channels]
                    return sum(c*w for c,w in zip(linear, [.2126,.7152,.0722]))
                values = sorted([luminance(colors["ink"]), luminance(colors["background"])])
                assert (values[1]+.05)/(values[0]+.05) >= 4.5, colors
                page.screenshot(path=str(evidence / f"report-export-{theme}.png"), animations="disabled")
            assert not errors, errors
            desktop = browser.new_page()
            desktop.goto(f"http://127.0.0.1:{server.server_port}/?key={server.key}#more")
            assert desktop.get_by_role("button", name="Export playback report").count() == 0
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        library.pool.shutdown(wait=True)
        thread.join()
print("PASS: native report export discovery, keyboard, duplicate suppression, cancellation, save/error recovery, state retention and narrow themes")
print(f"Evidence: {evidence}")
