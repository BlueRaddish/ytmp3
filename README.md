# ytmp3

Search YouTube for a track, pick from the results that are actually music, and save it as
MP3 — to a local folder or straight to any rclone remote.

A thin wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp). It exists because the raw
command for "find this song, grab the audio, name it properly, put it in my library" is long
enough that nobody types it twice.

```
$ ytmp3 high hopes
  1     855.9M   3:17  Panic! At The Disco - High Hopes (Official Video)  Panic! At The Disco
  2     143.7M   7:49  Pink Floyd - High Hopes (Official Music Video HD)  Pink Floyd
  3     135.0M   4:10  Kodaline - High Hopes                              Kodaline
  4  ★   95.9M   3:13  High Hopes                                         Panic! At The Disco
  ★ = youtube music catalog track
select [1-4, enter=1, q=quit]: 1
→ [Music] High Hopes.mp3
  gdrive:media/music
  saved to gdrive:media/music/[Music] High Hopes.mp3
```

## What it does that plain yt-dlp doesn't

- **Filters to music.** Search hits are checked against YouTube's own category, so lyric
  reuploads tagged *People & Blogs*, reaction videos and Shorts drop out.
- **Ranks by view count**, which is a decent proxy for "the version you meant".
- **Marks catalog tracks.** A ★ means YouTube Music has it as a real release (yt-dlp reports
  `track`/`artist`/`album` for it), not just a video someone uploaded.
- **Names files from a template** instead of leaving you with
  `[MV] MeloMance(멜로망스) _ Gift(선물).mp3`.
- **Files to a destination**, local or rclone, and refuses to silently overwrite.

## Install

Requires Python 3.11+, [ffmpeg](https://ffmpeg.org/), and — only for remote destinations —
[rclone](https://rclone.org/).

```
git clone https://github.com/BlueRaddish/ytmp3
cd ytmp3
pip install -e .
```

Or run it from the clone without installing:

```
python -m ytmp3 --help
```

On Windows, `install.ps1` drops `ytmp3` and `ytmp3.cmd` shims into `~/bin` so the command
works from PowerShell, cmd, Git Bash and MSYS2 alike:

```
powershell -ExecutionPolicy Bypass -File install.ps1
```

ffmpeg is found on `PATH`, at `FFMPEG_LOCATION`, or in the usual winget install directory.

## Destinations

A destination is a name for "where tracks go", plus an optional filename template.

```
$ ytmp3 dest add music gdrive:media/music '[Music] {title}.mp3'
$ ytmp3 dest add local ~/Music
$ ytmp3 dest default music
$ ytmp3 dest list
* music    rclone  gdrive:media/music
                   [Music] {title}.mp3
  local    local   C:\Users\you\Music
                   {artist} - {title}.mp3
```

Anything matching `remote:path` goes through `rclone copyto`; everything else is a local
directory. A single-letter prefix is treated as a Windows drive, so `C:\Music` stays local.

Skip the config entirely with `-o`:

```
$ ytmp3 -o ~/Downloads serenade
$ ytmp3 -o gdrive:media/music -t '[Music] {title}.mp3' babydoll
```

## Templates

Fields: `{title}` `{artist}` `{album}` `{year}` `{id}`. Each is sanitized for the filesystem
before substitution, and a separator left dangling by an empty field is cleaned up — so
`{artist} - {title}.mp3` yields `Serenade.mp3`, not ` - Serenade.mp3`.

`{title}` is the YouTube Music track name when the video is a catalog track. Otherwise it is
the video title with upload cruft stripped: `Ruel - Painkiller (Official Video)` becomes
`Painkiller`, while meaningful parentheticals like `(Feat. Colde)` survive. When the guess is
wrong, override it with `-n`:

```
$ ytmp3 -n '취향저격' -d music iKON 취향저격
```

## Config

`~/.config/ytmp3/config.toml`, or wherever `YTMP3_CONFIG` points.

```toml
default = "music"
template = "{artist} - {title}.mp3"

[dest.music]
target = "gdrive:media/music"
template = "[Music] {title}.mp3"

[dest.local]
target = "~/Music"
```

## Notes

- Search costs one request; the music check costs one request per candidate, run across a
  thread pool, capped at 14 candidates. Expect a couple of seconds before the list appears.
- `--any` skips the music filter when you want something that isn't categorised as music.
- Audio is `bestaudio`, converted to MP3 at the highest VBR setting, with the thumbnail
  embedded as cover art and metadata written to ID3 tags.
- Download only what you have the right to download.

## Licence

MIT.
