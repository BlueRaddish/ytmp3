# Music app feature review

Reviewed official Spotify, YouTube Music, and yt-dlp documentation on 2026-09-28. The useful reference is library organization and playback for files the user already has or may download. ytmp3 does not have a licensed streaming catalog.

| Pattern | Reference | ytmp3 status | Useful next step |
| --- | --- | --- | --- |
| Import and move playlists | [YouTube Music transfers](https://support.google.com/youtubemusic/answer/14729358?hl=en) report unmatched songs; [Spotify account exports](https://support.spotify.com/lc/article/understanding-my-data/) include playlist names and track metadata. | M3U/M3U8 files can now be matched to existing MP3s; unmatched entries are counted. A supported playlist URL can download up to 100 entries and create a local playlist of successful items. | Export/import ytmp3 playlists as a portable backup, then preview matches before importing Spotify or Google exports. A catalog entry must only match a local file; it does not supply the audio. |
| Library navigation | [Spotify sorting and filtering](https://support.spotify.com/us/article/sort-and-filter/) includes recent, alphabetical, creator, pinning, and playlist search; [YouTube Music uploads](https://support.google.com/youtubemusic/answer/9716522?hl=en) retain metadata and artwork. | Filename filter and newest-first library; no artist, album, cover, or duration index. | Read MP3 tags and artwork, add artist/album views, then sorting and filtering. Resolve duplicate and missing tags explicitly. |
| Quick collections | [Spotify Liked Songs](https://support.spotify.com/cz/article/your-library/) and [playlist folders](https://support.spotify.com/is-en/article/playlist-folders/) speed up finding favorites. | Manual playlists and queue. | Add a one-tap Favorites collection and playlist pinning. Folders can wait until many playlists exist. |
| Playback flow | [Spotify crossfade and gapless](https://support.spotify.com/tv/article/tracks-transitions/) smooth transitions; [Spotify keyboard shortcuts](https://support.spotify.com/us/article/keyboard-shortcuts/) support fast desktop control. | Seek, queue, speed, shuffle, repeat, Android lock-screen controls. | Restore last track/position, add a sleep timer, then test gapless playback. Crossfade needs two-player coordination and should follow playback-state reliability. |
| Download management | [YouTube Music offline settings](https://support.google.com/youtubemusic/answer/6313535?hl=en-GB) include per-playlist downloads, Wi-Fi choice, and storage controls; [Spotify offline settings](https://support.spotify.com/us/article/listen-offline/) expose status and cellular choice. | Per-URL job and a 100-item playlist cap; Android downloads require the app to stay open. | Persistent batch queue with cancel/retry per item, Wi-Fi-only option, and storage estimate. Move Android jobs into a durable foreground/background worker after that. |

## Order of work

1. **Protect collections:** portable playlist backup/export and an import preview with unmatched entries. Current browser/WebView local storage can be lost on reset or uninstall.
2. **Make the library browsable:** MP3 artist, album, duration, and artwork; sort and filter; Favorites.
3. **Improve daily listening:** last-position resume, sleep timer, queue undo and bulk actions.
4. **Harden batch downloads:** durable jobs, cancel/retry, network choice, and clear per-item outcomes.
5. **Audio polish:** gapless playback, then optional crossfade and equalizer.

Spotify and YouTube Music links are service catalog references, not file manifests. Direct account transfer would require an authorized export and a review of unmatched tracks; it should not silently search for or download substitutes. yt-dlp's [playlist options](https://github.com/yt-dlp/yt-dlp#playlist-selection) support bounded playlist processing, but source availability varies by site and over time.
