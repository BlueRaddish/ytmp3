# Releasing ytmp3

The app checks `updates.json` on the public `main` branch for a newer version. Keep this file current after every release so installed copies can find the next one. An update check is automatic at most once a day; **More → Check now** bypasses that interval.

## Version numbers

Use `X.Y.Z` for published releases. Bump `X` for a major compatibility or product milestone, `Y` for a batch of user-facing features, and `Z` only for a fix that should ship before the next feature batch. Do not assign a new public patch version to each UI tweak or phone test. Keep those iterations as untagged commits and local debug APKs, with the commit hash in test notes. `adb install -r` can replace a debug APK with the same Android `versionCode` during local testing. Bump all app version fields and Android `versionCode` when the next release is ready. Keep existing tags as the historical record; do not renumber them.

The update manifest advertises tagged numeric releases. It accepts `X.Y.Z`, so local iterations do not go into `updates.json`.

1. Bump `pyproject.toml`, `ytmp3/__init__.py`, Android `versionName`, and Android `versionCode`. The version code must increase for Android to accept an update.
2. Run the checks in the README and build the APK. Test the APK with an install over the preceding version. Confirm the new layout and assets appear without clearing app data, and exercise playback, sharing, and the update control. Loop a short MP3 in the background for several minutes and check `adb shell dumpsys media_session` for an active playback state; inspect `adb logcat -s ytmp3-playback:E` for stalls. While a track plays, tap its media notification and confirm the app returns to the foreground with playback still active. Use the same Android package ID and signing key as the preceding APK. The current APK is debug signed; keep that keystore backed up. A new key will require uninstalling the old app, which removes its private library.
3. Commit the code, tag it `vX.Y.Z`, and push both to GitHub. The PC update button installs this tag through pip in the active Python environment. Verify the tag exists before advertising it.
4. Upload the APK and source artifacts to the release folder in Drive. Verify the uploaded files with checksums and open the APK link. Review `android/THIRD_PARTY.md`, including the GPL source requirements for the Android APK, before distributing it publicly.
5. Set `updates.json` on `main` to this version and the verified Drive APK link, then commit and push it. The manifest has no release notes beyond 400 characters. It intentionally points to the previous release while a new APK is being prepared; publish the new link only after the upload succeeds.
6. Check the live raw manifest and **More → Check now** in the new app. For subsequent releases, also check from the preceding app version. On Android the button opens Drive, where the user downloads the APK and approves installation. It does not silently install an APK. On PC, restart the app after pip finishes.

Android and PC app updates are separate from yt-dlp's downloader update check. Keep the bundled yt-dlp current in the next APK, even if the on-device downloader check can fetch a newer engine between app releases.
