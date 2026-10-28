# Local verification routes

Run from the checkout being tested. Keep the normal music library and browser
profile out of automated checks. These scripts create temporary data and launch
a headless browser without taking desktop focus.

```powershell
python -m pytest -q
node --check ytmp3/web/app.js
node --check ytmp3/web/source-search.js
python tests/check_app.py
python tests/check_metadata.py
python tests/check_updates.py
node tests/check_playlists.js
python tests/check_library_ui.py
python tests/check_source_search.py
```

`check_source_search.py` starts the real authenticated server, uses controlled
search/download fixtures, and drives search → result → preview → Save. It also
checks empty/error/stale responses, query preservation, custom-source CRUD and
restart persistence, safe template encoding, keyboard dismissal, narrow light/dark
layouts, and the Android bridge adapter. Its screenshots default to
`%TEMP%/ytmp3-source-search`; set `YTMP3_EVIDENCE` to retain them elsewhere. Fixtures
do not prove live YouTube, video playback, or the native WebView.

For the external boundary, run `Library(...).search("a test query")` against
YouTube or drive an unmocked local app (`python shim.py app --library PATH`). Verify
results and preview availability; search must not create MP3s. Never download
third-party recordings merely to test search. Use the existing authorized test
tone route if download verification is needed.

Build Android with JDK 17 and SDK 36:

```powershell
cd android
.\gradlew.bat assembleDebug --console=plain
```

Use an isolated emulator or an authorized phone. Install over the existing APK
with `adb install -r` and preserve its data. Search a name, verify the actual
website opens in SourcePreviewActivity, open a result, inspect Back/Close, then
save an authorized source. Repeat with a custom HTTPS search template. Verify
the search page's Save button is disabled, track-page Save uses the displayed
page URL, closing preserves the query, a failed page offers Reload, and playback
can continue behind the preview. Inspect logcat for crashes. The preview has no
`addJavascriptInterface`, file/content access, or automatic download handler.

A build or browser adapter fixture does not establish native-device success.
Record attempted routes, failures, output hash, and remaining coverage in the
dated project worklog. Local debug iterations keep the existing public version;
release/version/feed changes follow RELEASING.md only when a release is approved.
