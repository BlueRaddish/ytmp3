# ytmp3 app brief

Audience: one person using a Windows PC and an Android phone to save authorized
audio from supplied URLs and play a personal MP3 library. Density: compact and
touchable on phone, efficient on PC. Tone: clear, capable, quiet. One teal accent,
light and dark themes, system sans with tabular numerals, subtle motion. The
interface is a yt-dlp wrapper and player; source credit remains visible.

## Screen space rule

Put the task content and the controls used with it at the top of each screen.
The phone's visible area is scarce: count how many tracks are visible before
adding headers, cards, forms, or explanatory text. Keep a persistent element
only if it helps the user act, decide, read current state, or navigate. Do not
repeat the page title inside its content when the navigation bar already names
it. Keep secondary actions in a short menu or dialog. Explain a feature when it
is first needed, or in one-time onboarding, optional help, a separate website, or GitHub docs
instead of leaving a permanent introduction above the user's music. Apply
this rule to new screens and other projects.
Browse shows all accessible media in one compact list. A folder filter and
filename search narrow it without leaving the page. The link field stays small;
after a URL is entered, yt-dlp extracts a title, source, and artwork when
available. The desktop preview floats below the field and the phone preview
appears inline. A metadata preview avoids embedding arbitrary websites, which
many sites disallow. The preview makes no download and never replaces the
user's explicit Save action.
Use symbols for repeated page actions, with a 44 px touch target, a screen-reader
name, and a desktop tooltip. Keep explicit text in confirmation dialogs and menus.
In the expanded player, keep the current track fixed above an independently
scrolling, edge-to-edge queue. The current-track banner opens a focused song
view with large cover art and playback controls. Pull beyond the queue's top
to reach that view; a further vertical swipe leaves the player. Preserve Back
and Close buttons for precise navigation. Queue and playlist rows use a grip
instead of visible position numbers.

References:

- [VLC desktop playback controls](https://docs.videolan.me/vlc-user/desktop/3.0/en/gettingstarted/desktopoverview/windows_and_linux/playback_controls.html):
  seek, speed, repeat, shuffle and a queue stay reachable during playback.
- [VLC for Android audio player](https://docs.videolan.me/vlc-user/android/3.X/en/audio/audio_player.html):
  keep the current item and transport controls available in a compact player.
- [yt-dlp embedding examples](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp):
  extract metadata without downloading media for a PC link preview.
- [youtubedl-android usage](https://github.com/yausername/youtubedl-android#usage):
  run the same metadata probe through the Android downloader wrapper.
- [MDN frame-ancestors](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy/frame-ancestors):
  sites can block embedded pages, so the URL preview shows extracted metadata.

## Device matrix

| Surface | Width | Pointer / hover | Keyboard | Shell | Network | Primary action |
| --- | --- | --- | --- | --- | --- | --- |
| PC window | expanded / large | fine / hover | likely, confirmed by keydown | browser or installed PWA | usually online | paste URL |
| Android phone | compact | coarse / no hover | absent unless confirmed | installed Android WebView shell | intermittent | paste or receive shared URL |
| Narrow PC / tablet | medium | either | unknown | browser or PWA | variable | paste URL |

Safe areas and height change at runtime. The same DOM and player model serve all
surfaces. The Android shell supplies its own on-phone library, yt-dlp downloader,
and media responses through a native bridge. CSS handles input and width
adaptations; JavaScript tracks only the capabilities that affect behavior. No
device-name or user-agent branches.

## Content and states

Real content: an empty library, long filenames, failed and active conversions,
offline PC server, an offline on-phone library, a 100-file library, and a shared URL with extra text. The player
shows title, seek position, transport, queue and volume. A download error keeps
the typed URL so retry is possible. The library can still display its last
snapshot while offline, with the age stated.

Android shared text is treated as untrusted input, placed in the URL field, and
downloaded only after the user taps Save as MP3. Phone downloads are stored in
the app's private library; Save file exports a copy through MediaStore.

The first release handles MP3 only. Browser playback is the codec boundary;
VLC's broad video, subtitle, filter and network-stream support is a reference
for future work, not a claim about this app.

## Browser visual checks

These captures are from the responsive PC browser app. The Android shell uses
the same interface, but requires a separate on-device check.

- [Desktop library](shots/desktop.png): 1440 px viewport, populated library.
- [Desktop browse](shots/desktop-browse.png): URL preview floats beside the media list.
- [Phone audio](shots/phone-browser.png): 390 px viewport, populated library.
- [Phone browse](shots/phone-browse.png): 390 px viewport, link preview, folder filter, and accessible media list.
- [Phone playlists](shots/phone-playlists.png): 390 px viewport, playlist controls.
- [Phone queue](shots/phone-player-browser.png): 390 px viewport, fixed current track and full-width queue.
- [Phone song](shots/phone-song-browser.png): 390 px viewport, large cover and transport controls.
- [Tablet queue, light](shots/tablet-queue-light.png): 768 px viewport, light theme.
- [Logo concepts](shots/logo-concepts.png): three candidates at launcher and navigation sizes.

## Android device check

Galaxy S10 (SM-G977N), Android 12 / API 31, ARM64, 1080 × 2280 display:
the debug APK installed and opened; a [CC0 10-second Wikimedia test tone](https://commons.wikimedia.org/wiki/File:440_Sine_wave.ogg)
downloaded and converted on the phone; ffprobe confirmed a 10-second MP3;
the file played in the phone player and exported through MediaStore into
`Music/ytmp3`. Sharing a page from Firefox opened ytmp3 with its URL in the
input field and did not start another download. This check establishes one working source, device, and codec;
other sites and Android versions still need coverage.

For v0.6.4, an Android 35 emulator confirmed the new Browse list and preserved
the existing library after an in-place install. The ARM64 yt-dlp runtime could
not execute on that x86_64 emulator, so the Android link preview still needs
a check on the Galaxy S10. The PC preview returned metadata for the Wikimedia
test-tone page without downloading the audio.
