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
view with large cover art and playback controls. Pull downward beyond the
queue's top to enter the song view; pull down on the fixed banner or tap Close
to collapse the queue. From the song view, pull up to return to the queue
or down to close the player.
Drag the mini player upward to reveal the queue under the finger. On trackpads,
scroll past the top of the queue to enter the song view. The queue menu has
playback controls; a queued track's menu can play it now, next, or last.
Animate the sheet between these states while the previous view remains visible.
Preserve Back and Close buttons for precise navigation. Queue and playlist rows use a grip
instead of visible position numbers.
Swipe horizontally between Browse, Audio, Playlists, and More on touchscreens;
a horizontal trackpad gesture does the same on PC. Keep each screen's vertical
scroll position. Let vertical scrolling, playlist strips, controls, and row
reordering retain their own gestures. In the song view, horizontal artwork
swipes move to the previous or next track. Respect reduced-motion preferences
when animating a screen change.
Move the prior main screen out as the next screen slides in across its full width.
Keep a sticky X first in the selection bar so long-press selection is easy to cancel.
Dismiss track and queue action menus when a user taps outside or presses Escape.

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
- [Claude Opus logo concepts](logo-claude-opus/contact-sheet.png): four candidates at launcher and navigation sizes. Grille is the current app icon.
- [Android v0.6.5](shots/emulator-v0.6.5.png): Browse after an in-place install and background library refresh.
- [Android v0.6.6](shots/emulator-v0.6.6.png): Audio with the Grille icon and the preserved two-track library.
- [Android v0.6.7 slide](shots/emulator-v0.6.7-slide.png): outgoing Audio and incoming Playlists during a real emulator swipe.
- [Android v0.6.7 selection](shots/emulator-v0.6.7-selection.png): the sticky cancel button stays at the start of multi-selection actions.
- [Galaxy S10 v0.6.8 queue](shots/s10-v0.6.8-queue.png): queue after dragging up from the mini player.
- [Galaxy S10 v0.6.8 song](shots/s10-v0.6.8-song.png): song view after pulling upward from the end of the queue.
- [Galaxy S10 v0.6.9 song](shots/s10-v0.6.9-down-pull.png): song view after pulling down from the queue's top.
- [Galaxy S10 v0.6.9 queue menu](shots/s10-v0.6.9-queue-menu.png): track actions appear near the top of the menu.

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

For v0.6.5, the Android 35 emulator preserved its two-track library after an
in-place install and showed the Claude Opus Drop icon. A touch pull on a queue
song row opened the song view; another pull on the artwork returned to Browse.
Adding and removing a test MP3 between app launches updated the listing through
the background scan. A browser check confirmed that a persisted library
snapshot appears when a refresh request fails. The Galaxy S10 was disconnected,
so this release has not been checked on that phone.

For v0.6.6, the Android 35 emulator kept the same two tracks after an in-place
install and displayed the Grille icon. A horizontal swipe moved Audio to
Playlists and back. In the expanded song view, an artwork swipe moved from the
90-second test track to the next track. The browser interaction check covered
vertical-scroll exclusion, playlist-strip exclusion, horizontal wheel input,
per-screen scroll restoration, and the player swipe. The Galaxy S10 was not
connected for this release.

For v0.6.7, the Android 35 emulator kept the same two-track library after an
in-place install. A recorded touch swipe showed Audio sliding out as Playlists
entered. Touch gestures opened the song view from the queue, returned to the
queue, collapsed to the mini player, and also exited directly from the song
view. A long press showed the cancel X first; an outside tap dismissed a track
menu. The Galaxy S10 accepted an in-place upgrade from an older debug build
and retained its existing test track. Its short screen timeout and lock screen
prevented a touch gesture check on the S10 during this pass.

For v0.6.8, the debug APK installed over v0.6.7 on the Galaxy S10 and retained
its Wikimedia test track. A real touch drag from the mini player opened the
queue; an upward pull on its only row opened the song view. The Android 35
emulator reproduced both gestures with its two-track library. The browser
interaction check covered a cancelled short drag, the moving sheet, and touch
and trackpad overscroll at the end of a long queue.

For v0.6.9, the Galaxy S10 kept its test track after an in-place install.
Pulling upward on its queue row left the queue open; pulling downward opened
the song view. The queue-wide options showed Play, Previous, and Next, with
unavailable actions disabled for its one-track queue. The track menu put Play
now and Remove from queue before metadata and file actions. The browser check
also verified Play next and Play last on a longer queue, including a track
moved from before the current song, and wheel overscroll at the queue's top.

For v0.6.10, an Android 35 emulator retained its two-track library after an
in-place install. A downward swipe on the song artwork collapsed directly to
the mini player; an upward swipe returned to the queue. The browser check
covered both touch directions and trackpad overscroll. The APK also installed
over v0.6.9 on the Galaxy S10, but its lock screen prevented a gesture check.
