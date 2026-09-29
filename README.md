# ytmp3

ytmp3 is a [yt-dlp](https://github.com/yt-dlp/yt-dlp) wrapper and personal MP3 player for PC and Android. yt-dlp does the site extraction and downloading; ffmpeg converts the result to MP3. This project adds a URL-based workflow, local library, and playback controls. Credit for the downloader and its site support belongs to the yt-dlp contributors.

Use it only with content you are authorized to download. A public URL, or a site appearing in yt-dlp's supported-sites list, does not by itself grant permission to copy its content. Check the source's terms and the rights in the recording before downloading. ytmp3 does not provide a music catalog or licenses to third-party media.

The app has four destinations: **Browse** for link downloads and folders, **Audio** for tracks, **Playlists** for saved collections, and **More** for settings and credits. Tap the bottom Now Playing bar to open playback and the ordered queue. From there, drag the numbered handle to reorder tracks, use **Mix** to jump among queued tracks, toggle **Loop queue**, or open queue options to save it as a playlist or clear it.

Main-screen actions use symbols: the triangle plays, crossed arrows mix, the star filters favorites, and the checked square selects tracks. The buttons have action names for screen readers and tooltips on PC.

## PC app

Requires Python 3.11+, ffmpeg on your PATH, and an internet connection for URL downloads.

```sh
git clone https://github.com/BlueRaddish/ytmp3
cd ytmp3
pip install -e .
ytmp3 app
```

Open the URL printed in the terminal. The app accepts a track URL or a playlist URL supported by yt-dlp, converts available audio to MP3, and keeps completed files on the PC in `~/Music/ytmp3` by default. Playlist links are limited to 100 items; each successful download stays saved if another item fails, and the app creates a local playlist from the saved files. The player supports playlists, queue editing, seek, volume, speed, shuffle, and repeat. Search title, artist, album, and folder; sort by date, title, artist, album, or duration; select a folder to play or mix its tracks. Switch between compact, list, and tile layouts. Use a track's three-dot menu for details, playlists, favorites, queue, sharing, and other actions. Long press a track to select several and apply actions together. Drag the handle on the left of playlist and queue tracks to reorder; arrow keys also work. Embedded MP3 tags and JPEG/PNG covers appear in the library and player. Playlists, favorites, hidden tracks, and interface preferences are saved in the browser on that device.

Add existing MP3 folders to the PC library at startup; included folders and their subfolders are read without moving their files:

```sh
ytmp3 app --include "C:\\Users\\you\\Music" --include "D:\\Recordings"
```

Repeat `--include` for each folder. `--library PATH` changes where new downloads are stored.

The server binds to `127.0.0.1` by default. `ytmp3 app --host 0.0.0.0` also exposes it to devices on the same trusted network, using the temporary access URL printed at startup. That network mode plays the PC's library; it does not move downloads to the phone. Keep the access URL private and do not expose the server directly to the public internet.

The web app can receive shared links when installed from a supporting browser on a secure origin. Plain HTTP LAN addresses work in a browser but generally cannot be installed or registered as share targets.

## Android app

The Android app runs yt-dlp and ffmpeg **on the phone**. It stores MP3s in its own on-device library and works without a PC server. It appears in Android's Share menu for text links; a shared URL fills the form and waits for you to tap **Save MP3**. **Save file** exports a copy to `Music/ytmp3` for other apps.

In **More → Media library**, choose additional MP3 folders with Android's folder picker. The app remembers the selected folders and rescans them on launch or when you tap **Rescan library**. Subfolders are included. Remove a folder in More to stop listing it; its files stay where they are. Playlists, queue edits, dark/light/device theme, library layouts, and playback speed are available on the phone. Audio keeps playing with the screen locked and offers Android media notification controls with track artwork. Playlist URLs download up to 100 items on the phone and create a local playlist of successful tracks. The track menu can share MP3s or set one as the phone ringtone; Android asks you to allow system-setting changes before setting a ringtone.

Use **Edit** on a library track to change its displayed title, artist, album, or cover. Edits are stored inside ytmp3 on that device and do not rewrite the MP3, including files in selected read-only folders. Removing a chosen cover reveals the embedded cover again. PC edits live in `.ytmp3-track-edits.json` and `.ytmp3-covers` inside the library; Android edits and covers live in app storage. Back up those alongside your library if you want to keep the edits.

In **Playlists**, **Import M3U** reads an `.m3u` or `.m3u8` file on either device. It matches filenames to MP3s already in that device's library, preserves the listed order, and reports entries it could not match. Importing an M3U does not download missing files. Spotify and YouTube Music account exports are not directly imported yet.

Before a download, Android checks for a newer stable yt-dlp at most once a day. If that check is unavailable, it uses the bundled copy. A download failure shows a short message in the app; technical details go to Android logs.

The app checks for a newer ytmp3 version daily and has a **Check now** control in More. On Android, **Open APK in Drive** opens the new APK's Drive page; download it and approve Android's install prompt. The package name and signing key must match the installed app, and the new APK must have a higher version code. On PC, **Install update** runs pip in the active Python environment; restart the app afterward. Source-checkout users should update their checkout instead. See [release steps](docs/RELEASING.md) for the update manifest and signing requirements.

The first Android build targets Android 10+ on ARM64 phones. Build a debug APK with Android SDK 36 and JDK 17:

```sh
cd android
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

On Windows, use `gradlew.bat assembleDebug`. Downloads currently run while the app stays open. The app disables Android cloud backup. Files in the private library, playlists, and preferences are removed if the Android app is uninstalled; export anything you want to keep first. The Android package uses [youtubedl-android](https://github.com/yausername/youtubedl-android) to bundle yt-dlp and ffmpeg. See [Android third-party notices](android/THIRD_PARTY.md) before distributing an APK.

## Command line

```sh
ytmp3 https://example.org/recording
ytmp3 -o ~/Music https://example.org/recording
ytmp3 --help
```

Pass one HTTP or HTTPS URL. The default destination is configured with `ytmp3 dest add NAME TARGET` and `ytmp3 dest default NAME`; `-o` chooses a local directory for one run. A destination may also be an rclone remote, which requires rclone. See `ytmp3 --help` for filename templates and other options.

## Limits

See the [VLC audio feature review](docs/VLC_AUDIO_RESEARCH.md) and [Spotify/YouTube Music feature review](docs/MUSIC_APP_FEATURE_RESEARCH.md) for source-backed comparisons and next candidates.

- The player takes cues from VLC's audio controls, but does not include VLC's broader codec, subtitle, or network-stream support.
- Android playback uses Media3 instead of WebView audio so the media session can continue in the background. PC playback remains in the browser; close that browser tab and playback stops. Equalizer, sleep timer, and VLC's broader codec support are not implemented yet.
- PC and Android keep separate local libraries. There is no sync service.
- Some URLs may be unsupported, restricted, or unavailable even when the corresponding page opens in a browser. Neither the wrapper nor a supplied URL changes the rights or source terms for that content.

## Development

```sh
python -m pytest
python tests/check_app.py
python tests/check_metadata.py
python tests/check_updates.py
node tests/check_playlists.js
python tests/check_library_ui.py  # requires Playwright and a Chromium browser
cd android && ./gradlew assembleDebug
```

The project source is licensed under [MIT](LICENSE). The Android APK includes separately licensed components described in [Android third-party notices](android/THIRD_PARTY.md). Software licenses do not grant rights to media obtained with it.
