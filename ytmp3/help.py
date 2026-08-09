"""Help text, built from data so the columns line up and CI can lint it.

Follows the Help Screen Protocol: canonical section order, POSIX usage
notation, lowercase one-line descriptions, 80 soft / 95 hard columns.
"""

from . import __version__

REPO = "https://github.com/BlueRaddish/ytmp3"

USAGE_LINES = (
    "ytmp3 [options] QUERY...",
    "ytmp3 [options] URL",
    "ytmp3 dest {list|add|remove|default} [ARGS...]",
    "ytmp3 {-h|--help|-V|--version}",
)

DESCRIPTION = (
    "Searches YouTube for QUERY, keeps the hits YouTube classifies as Music,",
    "and lists them most-viewed first so you can pick one. The choice is",
    "downloaded, converted to MP3 with cover art and tags, and filed at a",
    "destination -- a local directory or any rclone remote -- under a name",
    "built from a template.",
)

EXAMPLES = (
    ("search, pick from the list, save to the default destination",
     "ytmp3 high hopes"),
    ("take the most-viewed result without prompting",
     "ytmp3 -y heartbreak anniversary"),
    ("save into a destination defined in the config",
     "ytmp3 -d music more than words"),
    ("save into a local directory this once",
     "ytmp3 -o ~/Music serenade"),
    ("save straight to an rclone remote with a custom name",
     "ytmp3 -o gdrive:media/music -t '[Music] {title}.mp3' babydoll"),
    ("skip the search when you already have the URL",
     "ytmp3 https://www.youtube.com/watch?v=IPXIgEAGe4U"),
)

COMMANDS = (
    ("dest list", "show configured destinations"),
    ("dest add NAME TARGET", "add a destination, local path or rclone remote:path"),
    ("dest remove NAME", "delete a destination"),
    ("dest default NAME", "set the destination used when -d and -o are omitted"),
)

OPTIONS = (
    ("-d, --dest NAME", "save into the named destination from the config"),
    ("-o, --out TARGET", "save into an ad-hoc target, overriding -d"),
    ("-t, --template TPL", "filename template, overriding the destination's"),
    ("-n, --name TITLE", "set {title} explicitly instead of detecting it"),
    ("-l, --limit N", "how many results to offer (default: 10)"),
    ("-y, --yes", "take the most-viewed result without prompting"),
    ("    --any", "offer results outside the Music category too"),
    ("    --force", "overwrite a file already present at the destination"),
    ("    --dry-run", "print what would happen, download nothing"),
    ("-v, --verbose", "show yt-dlp and rclone output"),
    ("-V, --version", "print version and exit"),
    ("-h, --help", "print this help and exit"),
)

ARGUMENTS = (
    ("QUERY", "words to search for, joined with spaces"),
    ("URL", "a YouTube video URL, used instead of searching"),
    ("TARGET", "a local directory, or an rclone REMOTE:PATH"),
    ("TPL", "template over {title} {artist} {album} {year} {id}"),
)

ENVIRONMENT = (
    ("YTMP3_CONFIG", "config file path, overriding the default below"),
    ("FFMPEG_LOCATION", "directory holding ffmpeg, when it is not on PATH"),
)

FILES = (
    ("~/.config/ytmp3/config.toml", "destinations, default template"),
)

EXIT_STATUS = (
    ("0", "a track was downloaded and filed"),
    ("1", "the operation failed"),
    ("2", "the command line was wrong"),
    ("130", "interrupted at the prompt"),
)

SEE_ALSO = ("yt-dlp(1)", "rclone(1)", REPO)

_GUTTER = 2


def _column(rows) -> int:
    return max(len(left) for left, _ in rows) + _GUTTER


def _table(rows, indent: str = "  ") -> list[str]:
    width = _column(rows)
    return [f"{indent}{left.ljust(width)}{right}".rstrip() for left, right in rows]


def _section(name: str, body: list[str]) -> list[str]:
    return [name, *body, ""]


def full_help() -> str:
    out: list[str] = []
    out += _section("NAME", ["  ytmp3 - search youtube for a track and save it as mp3"])
    out += _section("USAGE", [f"  {line}" for line in USAGE_LINES])
    out += _section("DESCRIPTION", [f"  {line}" for line in DESCRIPTION])

    examples: list[str] = []
    for caption, command in EXAMPLES:
        examples.append(f"  {caption}")
        examples.append(f"    $ {command}")
        examples.append("")
    out += _section("EXAMPLES", examples[:-1])

    out += _section("COMMANDS", _table(COMMANDS))
    out += _section("OPTIONS", _table(OPTIONS))
    out += _section("ARGUMENTS", _table(ARGUMENTS))
    out += _section("ENVIRONMENT", _table(ENVIRONMENT))
    out += _section("FILES", _table(FILES))
    out += _section("EXIT STATUS", _table(EXIT_STATUS))
    out += ["SEE ALSO", *[f"  {item}" for item in SEE_ALSO]]
    return "\n".join(out) + "\n"


def short_help() -> str:
    quick = (
        ("ytmp3 high hopes", "search, pick, save to the default destination"),
        ("ytmp3 -y -d music karma", "top hit, straight into the 'music' destination"),
    )
    lines = [
        "ytmp3 - search youtube for a track and save it as mp3",
        "",
        "usage:",
        *[f"  {line}" for line in USAGE_LINES[:2]],
        "",
        "examples:",
        *[f"  $ {left.ljust(_column(quick))}{right}".rstrip() for left, right in quick],
        "",
        "commands:",
        *_table(COMMANDS[:2]),
        "",
        "run 'ytmp3 --help' for the full reference",
    ]
    return "\n".join(lines) + "\n"


def usage_error(message: str) -> str:
    return "\n".join([
        f"ytmp3: {message}",
        "",
        f"usage: {USAGE_LINES[0]}",
        "",
        "try 'ytmp3 --help'",
    ]) + "\n"


def version() -> str:
    return f"ytmp3 {__version__}\n"
