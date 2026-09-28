# Android third-party components

The Android app uses [youtubedl-android](https://github.com/yausername/youtubedl-android)
0.18.1 to bundle and invoke [yt-dlp](https://github.com/yt-dlp/yt-dlp) and FFmpeg
on the device. youtubedl-android is GPL-3.0 licensed. Its source and license are
available in its repository; a copy of its license is included in the Android
assets. yt-dlp is maintained by the yt-dlp contributors, and FFmpeg is maintained
by the [FFmpeg contributors](https://ffmpeg.org/). The bundled binaries and their transitive components
have their own license terms; review the upstream notices and provide the
corresponding source and license materials when distributing an APK.

This project supplies the interface and local library integration. It does not
claim ownership of yt-dlp's extractors, FFmpeg's codecs, or content obtained with
them. A tool's software license does not grant permission to download media from
third-party services.
