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

The source written for ytmp3 is offered under the repository's MIT license. The
distributed Android APK combines it with the GPL-3.0 youtubedl-android library;
the [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html) describes the
combined-work distribution requirements. Ship the tagged ytmp3 source and the
corresponding source and notices for bundled components alongside any public
APK. The upstream [0.18.1 release](https://github.com/yausername/youtubedl-android/releases/tag/0.18.1)
identifies the library used by this build. Review the provenance and source
availability of its bundled native runtime before broader distribution.

The upstream [build-provenance request](https://github.com/yausername/youtubedl-android/issues/363)
for the 0.18.1 prebuilt runtime is still open; its tagged build notes do not
identify all inputs that produced those binaries. Keep the APK in test
distribution until corresponding source and notices can be verified.
