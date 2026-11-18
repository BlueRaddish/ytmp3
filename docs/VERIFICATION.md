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
python tests/check_playback_reports.py
python tests/check_playback_reports_ui.py
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
The bridge adapter also returns a selected page to a freshly loaded Audio screen,
verifying that Browse opens and the download starts after app recreation. Native
delivery waits for the trusted app page to finish loading and acknowledge receipt.

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

On this Windows PC the default 3 GB heap failed to start under memory pressure.
The following process-local override built the APK successfully; it does not
change the machine or the project's normal Gradle settings:

```powershell
.\gradlew.bat assembleDebug --console=plain --no-daemon --max-workers=1 '-Dorg.gradle.jvmargs=-Xms64m -Xmx640m -XX:MaxMetaspaceSize=192m -XX:ReservedCodeCacheSize=48m -XX:ActiveProcessorCount=2 -XX:+UseSerialGC -Dfile.encoding=UTF-8'
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

## Intermittent Android pauses

Playback reports are now automatic. A pause, suppression or player error pins a
separate snapshot with the preceding events and subsequent controller/resume
events. The user can resume playback, close/reopen the app, and export later from
**More → Playback reports → Export playback report**. Do not require the user to
stay paused, connect USB at the moment of the fault, or interrupt their day.

Private `files/playback-reports/` retains up to64 reports /2MiB, each at most64KiB.
Writes run on one background worker, coalesce updates to the same report and
replace completed snapshots atomically where supported. Interrupted temporary
writes are cleaned on the next access. Reports include screen/power/charging
state and connected output-device types, without track names, URLs, device names
or addresses. Capture is local; there is no upload. All pauses are evidence,
including intentional ones; saving a report does not label it an application bug.

While actually playing, a30-second checkpoint records the last known position
for an interrupted process. It stops immediately when playback stops and owns
no additional wake lock. A later service start preserves a possible interrupted
session and the app's own Android exit history (Android11+). A missing clean exit
is a lead, not proof of a system kill. A sudden power/process loss can still lose
the latest asynchronous write.

`PlaybackService` keeps the latest 64 playback changes in the private
`playback-trace` preferences and also emits them under the `ytmp3-playback` logcat
tag. The trace has timestamps, playback position/state, pause reason, suppression
reason, controller package, errors/retries and service lifecycle events. It records
changes and active-playback checkpoints, without track titles or URLs. Preferences survive service
and process recreation; very abrupt termination can lose the last asynchronous
write. A new service session without a preceding `service_destroyed` event is a
lead to investigate, not proof that Android killed the app.

Use an authorized debug phone and substitute its actual serial. These can be
collected later, after resume/restart; the independent saved report is the key
artifact. The normal export includes saved reports, rolling context and exit info.

```powershell
adb devices -l
adb -s SERIAL exec-out run-as io.github.blueraddish.ytmp3 cat shared_prefs/playback-trace.xml
adb -s SERIAL logcat -d -s ytmp3-playback:I
adb -s SERIAL shell dumpsys audio
adb -s SERIAL shell dumpsys media_session
adb -s SERIAL shell dumpsys power
adb -s SERIAL shell dumpsys activity exit-info io.github.blueraddish.ytmp3
adb -s SERIAL shell run-as io.github.blueraddish.ytmp3 ls files/playback-reports
```

`audio_focus_loss` identifies a pause requested by Android's focus handling;
correlate the timestamp with the focus command history in `dumpsys audio` to
identify the competing app. Transient focus loss appears as suppression reason
1 and normally resumes after focus returns. A permanent loss stays paused until
Play. `audio_output_disconnected` identifies Android's becoming-noisy event
(for example, headphones disconnecting). `user_request` plus a `controller` event
helps identify app/media-button requests. An `error` event identifies a player
failure rather than an intentional pause. Do not override focus/noisy protection
or assume battery optimization is the cause without this evidence.

Verify a diagnostic APK with real local MP3 playback: advance in the foreground,
send the Activity to the background, turn the screen off, then return and check
that the actual position advanced. Check the service is foreground and its wake
lock exists. Include manual pause/resume and a separate audio-focus client with
transient and permanent requests; assert distinct trace reasons and the expected
automatic/manual resume behavior. Confirm the trace remains bounded and survives
process exit. An emulator proves these routes on that emulator; Samsung battery
management, Bluetooth interruptions and the reported handset failure still need
real-device evidence. A successful build or a 1.0.0 version label does not identify
the APK actually installed; retain its hash and update time.

`check_playback_reports.py` uses JDK17+ to exercise the production file store on
real temporary files: coalescing, persistence/recreation, interrupted writes,
64-report/2MiB limits, safe paths, oversize rejection and a real IO failure. It
fails if the Java check gives no receipt. `check_playback_reports_ui.py` verifies
native-adapter discovery/keyboard operation, duplicate suppression, picker cancel,
save/error recovery, state retention and narrow light/dark layouts. Its fixtures
do not establish native file-picker or on-device persistence behavior.

The native acceptance route must pause then resume without collecting immediately,
roll the64-event ordinary history past that pause, restart the app, and export
through Android's real save picker. Confirm the original pause, later resume and
device context remain in the JSON; include cancel/retry, file permissions and
return to More. Preserve the existing user's queue/settings/media and remove
only generated test files. Validate active checkpoints stop while paused.

## Repeated-work and resource measurements (Windows)

Install the optional verification dependencies (`psutil`, `playwright`, `Pillow`)
in the development environment; ffmpeg and the Edge path in the script must be
available. These are not application dependencies. Run sequentially with enough
free system commit space; do not close the user's applications to make room.

```powershell
python tests/measure_efficiency.py --repo C:/path/to/checkout --output C:/outside-repo/run.json
```

Use the same script against both revisions. Alternate fresh-process baseline and
candidate runs and retain failed attempts. The probe uses temporary own-tone MP3s,
5,000 synthetic tracks, a 1,000-item queue and controlled native/search adapters.
It records refresh/render latency, snapshot writes, polling/redraw counts,
deleted-file tag-cache retention, repeated extractor work and the owned process
tree's memory/CPU/I/O/handles. It also saves a matching screenshot. Never run it
against the user's normal library or browser profile.

The native adapter does not establish Android lifecycle, power or VRAM behavior.
See [the October 28 ledger](OPTIMIZATION.md) for measured outcomes and limits.
