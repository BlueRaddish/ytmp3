"""Help text, built from data so the columns line up and CI can lint it.

Follows the Help Screen Protocol: canonical section order, POSIX usage
notation, lowercase one-line descriptions, 80 soft / 95 hard columns.
"""

from . import __version__

REPO = "https://github.com/BlueRaddish/ytmp3"

USAGE_LINES = (
    "ytmp3 [options] URL",
    "ytmp3 app [--host HOST] [--port PORT] [--library DIR]",
    "ytmp3 dest {list|add|remove|default} [ARGS...]",
    "ytmp3 {-h|--help|-V|--version}",
)

DESCRIPTION = (
    "Takes a URL you supply and uses yt-dlp to save its audio as MP3,",
    "with metadata and cover art when available. Files go to a local",
    "directory or an rclone remote. The app command starts a personal",
    "browser-based library and player for desktop and Android.",
)

EXAMPLES = (
    ("start the personal library and player",
     "ytmp3 app"),
    ("save from a URL to the default destination",
     "ytmp3 https://example.org/recording"),
    ("save from a URL into a local directory",
     "ytmp3 -o ~/Music https://example.org/recording"),
    ("use a configured destination",
     "ytmp3 -d archive https://example.org/recording"),
)

COMMANDS = (
    ("app", "start the personal library and player"),
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
    ("    --force", "overwrite a file already present at the destination"),
    ("    --dry-run", "print what would happen, download nothing"),
    ("-v, --verbose", "show yt-dlp and rclone output"),
    ("-V, --version", "print version and exit"),
    ("-h, --help", "print this help and exit"),
)

ARGUMENTS = (
    ("URL", "one HTTP or HTTPS source URL supplied by you"),
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
    ("0", "the operation completed"),
    ("1", "the operation failed"),
    ("2", "the command line was wrong"),
    ("130", "interrupted"),
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
    out += _section("NAME", ["  ytmp3 - save audio from a URL and play your MP3 library"])
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
        ("ytmp3 app", "open the personal library and player"),
        ("ytmp3 -o ~/Music URL", "save a URL as MP3"),
    )
    lines = [
        "ytmp3 - save audio from a URL and play your MP3 library",
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
