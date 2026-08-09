# ytmp3

A [yt-dlp](https://github.com/yt-dlp/yt-dlp) wrapper that turns a track name into a tagged MP3
in the right folder with the right filename.

`ytmp3 <words>` searches YouTube, discards the hits that are not music, lists what is left
most-viewed first, and downloads whichever one you pick. The result is converted to MP3,
given cover art and ID3 tags, named from a template, and written to a destination — a local
directory or any rclone remote.

This README is the manual. `ytmp3 --help` is the command reference.

---

## Contents

- [The pipeline](#the-pipeline)
- [Requirements](#requirements)
- [Installing](#installing)
- [Selecting a track](#selecting-a-track)
- [The music filter](#the-music-filter)
- [Naming and templates](#naming-and-templates)
- [Destinations](#destinations)
- [Configuration](#configuration)
- [Audio and metadata](#audio-and-metadata)
- [Exit status](#exit-status)
- [Development](#development)

---

## The pipeline

Every run walks the same six stages.

| Stage | What happens |
| --- | --- |
| Search | one flat search request returns up to 30 hits with titles, channels, durations and view counts |
| Prefilter | hits shorter than 60s or longer than 900s are dropped — Shorts, clips, compilations, livestreams |
| Probe | the top 14 by view count get a full metadata fetch, in parallel, to read their category |
| Select | Music-category hits are listed most-viewed first; you pick one, or `-y` takes the top |
| Download | the best audio-only stream is fetched and converted to MP3 |
| Deliver | the file is named from a template and moved to the destination |

Passing a URL instead of search words skips the first four stages.

## Requirements

| Component | Needed for | Notes |
| --- | --- | --- |
| Python 3.11+ | everything | `tomllib` is used to read the config |
| yt-dlp | everything | installed as a dependency |
| ffmpeg | everything | found on `PATH`, at `FFMPEG_LOCATION`, or in the winget package directory |
| rclone | remote destinations only | not needed if you only save locally |

## Installing

```
git clone https://github.com/BlueRaddish/ytmp3
cd ytmp3
pip install -e .
```

Or run it straight from the clone, uninstalled:

```
python -m ytmp3 --help
```

On Windows, `install.ps1` writes two shims into `~/bin`, so the command resolves from
PowerShell, cmd, Git Bash and MSYS2 alike:

```
powershell -ExecutionPolicy Bypass -File install.ps1
```

PowerShell and cmd prefer `ytmp3.cmd`; bash looks for the extensionless `ytmp3`. Both are
written, both bake in the absolute repo path, and both call `shim.py`, so nothing depends on
`PYTHONPATH` at call time. The script warns if `~/bin` is not on your User `PATH`.

## Selecting a track

```
$ ytmp3 취향저격
  1      65.2M   3:55  iKON - 취향저격(MY TYPE) M/V                    iKON
  2  ★    6.8M   2:55  STAY THE NIGHT (Feat. DeVita) (STAY THE NIGHT…  GRAY (그레이)
  3  ★    4.8M   4:18  How's your night (She is My Type♡ X Jeong Eun…  JEONG EUNJI - Topic
  4       4.1M   3:34  iKON - My Type (취향저격) (Color Coded Han|Ro…  yankat
  5       3.9M   3:33  iKON - '취향저격(MY TYPE)' 0124 SBS Inkigayo    iKON
  ★ = youtube music catalog track
select [1-5, enter=1, q=quit]:
```

The columns are rank, catalog marker, view count, duration, title and channel. Titles are
truncated to fit and are measured in terminal columns, so CJK text stays aligned.

| Input | Effect |
| --- | --- |
| a number | download that result |
| enter | download result 1 |
| `q` | quit without downloading, exit 130 |

Two cases skip the prompt. When only one result survives filtering it is used automatically,
and with `-y` the most-viewed result is taken. Both print the choice before proceeding.

`-l N` changes how many results are offered (default 10). It caps the list, not the probe —
raising it past 14 cannot surface more, because that is how many candidates get checked.

## The music filter

YouTube search returns lyric reuploads, covers, reactions and clips alongside the track you
want. ytmp3 keeps only what YouTube itself files under the Music category.

The catch is that the cheap flat search does not report categories. It returns titles,
channels, durations and view counts in a single request, but `categories` and `track` require
a full metadata fetch per video. So the probe stage fetches the top 14 candidates across an
8-thread pool. That is the entire latency cost of the filter — expect a second or two before
the list appears.

Two different signals come out of that probe:

| Signal | Meaning | Used for |
| --- | --- | --- |
| `categories == ['Music']` | YouTube classifies the upload as music | the filter — non-music results are dropped |
| `track` is set | YouTube Music has this as a catalog release | the ★ marker, and better title/artist metadata |

A catalog track — an "art track", usually on a `- Topic` channel — carries label-supplied
`track`, `artist`, `album` and `release_year`. An official music video is category Music but
has none of those, so it appears in the list without a ★. Videos with neither, like a lyric
reupload filed under *People & Blogs*, never appear at all.

`--any` disables the filter entirely. That also skips the probe stage, so it is faster, and
results carry no ★ markers or catalog metadata.

## Naming and templates

The filename comes from a template. Five fields are available:

| Field | Source |
| --- | --- |
| `{title}` | catalog track name, else the video title with cruft stripped, else `-n` |
| `{artist}` | catalog artist, else the channel name with a trailing `- Topic` removed |
| `{album}` | catalog album, empty for non-catalog videos |
| `{year}` | catalog release year, else the upload year |
| `{id}` | YouTube video id |

Title resolution runs in that order of preference. When the video is not a catalog track, the
video title is cleaned: bracketed groups are dropped if their contents look like upload cruft,
and a leading `Artist - ` prefix is removed when the artist is known.

| Raw video title | Channel | `{title}` |
| --- | --- | --- |
| `Ruel - Painkiller (Official Video)` | `RUEL` | `Painkiller` |
| `Tom Frane - Stray Nights (Lyrics)` | `Tom Frane` | `Stray Nights` |
| `iKON - 취향저격(MY TYPE) M/V` | `iKON` | `취향저격(MY TYPE)` |
| `[MV] MeloMance(멜로망스) _ Gift(선물)` | `1theK` | `MeloMance(멜로망스) _ Gift(선물)` |
| `로꼬 - 시간이 들겠지 (Feat. Colde)` | `1theK` | `로꼬 - 시간이 들겠지 (Feat. Colde)` |

Groups containing words like *official*, *lyrics*, *audio*, *가사* or *m/v* are treated as
cruft; anything else is kept, which is why `(Feat. Colde)` and `(MY TYPE)` survive.

The last two rows show the limits. Prefix removal compares the title against the channel name,
so it works for artist-owned uploads and fails on label channels like 1theK, where the channel
is not the artist. Label uploads also use their own separators — `_` rather than `-` — which
the cleaner does not treat as an artist boundary. When the guess is wrong, `-n TITLE` sets
`{title}` outright:

```
$ ytmp3 -n '선물' -d music 멜로망스 선물
```

Every field is sanitized before substitution: characters Windows forbids are removed, trailing
dots and spaces are trimmed, and reserved device names like `CON` are prefixed. A separator
stranded by an empty field is cleaned up too, so `{artist} - {title}.mp3` produces
`Serenade.mp3` rather than ` - Serenade.mp3`.

## Destinations

A destination is a named target plus an optional template.

```
$ ytmp3 dest add music gdrive:media/music '[Music] {title}.mp3'
$ ytmp3 dest add local ~/Music
$ ytmp3 dest default music
$ ytmp3 dest list
* music  rclone  gdrive:media/music
                 [Music] {title}.mp3
  local  local   ~/Music
                 {artist} - {title}.mp3
```

The `*` marks the default, used when neither `-d` nor `-o` is given. Adding the first
destination makes it the default automatically; removing the default promotes another.

| Command | Effect |
| --- | --- |
| `dest list` | show destinations, kinds, targets and templates |
| `dest add NAME TARGET [TPL]` | add a destination, optionally with its own template |
| `dest remove NAME` | delete a destination |
| `dest default NAME` | set the default |

**Local or remote** is decided by the target's shape. A prefix of two or more characters
followed by a colon is an rclone remote, delivered with `rclone copyto`; anything else is a
local directory, delivered with a move, creating the directory if needed. The two-character
minimum is what keeps `C:\Music` local rather than reading it as a remote named `C`.

`-o TARGET` bypasses the config for one run and accepts either form:

```
$ ytmp3 -o ~/Downloads serenade
$ ytmp3 -o gdrive:media/music -t '[Music] {title}.mp3' babydoll
```

Before downloading, ytmp3 checks whether the filename already exists at the destination — with
`rclone lsf` for remotes, a filesystem check for local paths — and stops if it does. `--force`
overwrites instead.

## Configuration

`~/.config/ytmp3/config.toml`, or `$XDG_CONFIG_HOME/ytmp3/config.toml`, or wherever
`YTMP3_CONFIG` points.

```toml
default = "music"
template = "{artist} - {title}.mp3"

[dest.music]
target = "gdrive:media/music"
template = "[Music] {title}.mp3"

[dest.local]
target = "~/Music"
```

Precedence runs from most to least specific:

| Setting | Order |
| --- | --- |
| target | `-o` → `-d` → `default` in the config |
| template | `-t` → the destination's `template` → the top-level `template` → `{artist} - {title}.mp3` |

Two environment variables are read:

| Variable | Effect |
| --- | --- |
| `YTMP3_CONFIG` | use this config file instead of the default location |
| `FFMPEG_LOCATION` | directory holding ffmpeg, when it is not on `PATH` |

## Audio and metadata

The `bestaudio/best` format is requested, so only an audio stream is transferred — no video is
downloaded and discarded. ffmpeg then runs three postprocessors in order:

| Postprocessor | Result |
| --- | --- |
| `FFmpegExtractAudio` | MP3 at `--audio-quality 0`, the highest VBR setting |
| `FFmpegMetadata` | title, artist and album written to ID3 tags |
| `EmbedThumbnail` | the video thumbnail embedded as cover art |

Work happens in a temporary directory that is removed afterwards, so a failed or interrupted
run leaves nothing behind and never writes a partial file to the destination.

## Exit status

| Code | Meaning |
| --- | --- |
| 0 | a track was downloaded and filed, or nothing needed doing |
| 1 | the operation failed |
| 2 | the command line was wrong |
| 130 | interrupted at the prompt |

## Development

```
pip install -e . pytest
python -m pytest -q
```

| Module | Responsibility |
| --- | --- |
| `cli.py` | argument parsing, the result list, the prompt, the run flow |
| `help.py` | help text, built from data tables so columns align and CI can lint it |
| `search.py` | flat search, the parallel probe, music filtering and ranking |
| `download.py` | ffmpeg discovery, format selection, MP3 conversion |
| `dest.py` | existence checks and delivery, local and rclone |
| `naming.py` | title cleaning, filesystem sanitizing, template rendering |
| `config.py` | reading and writing the TOML config |

`tests/test_help.py` lints the help output rather than trusting review: line widths, canonical
section order, lowercase unpunctuated descriptions, a single placeholder style, help on stdout
exiting 0, usage errors on stderr exiting 2, every documented flag existing in the parser, and
every example in the help actually parsing. CI runs the suite on Windows and Linux against
Python 3.11 and 3.13.

The launcher is `shim.py` rather than `ytmp3.py` deliberately — a root-level `ytmp3.py` shadows
the `ytmp3/` package and breaks imports.

## Licence

MIT. Download only what you have the right to download.
