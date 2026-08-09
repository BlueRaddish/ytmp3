"""Command line entry point."""

import sys
import tempfile
import unicodedata
from pathlib import Path

from . import help as helptext
from .config import Config, is_rclone
from .dest import DeliveryError, deliver, exists
from .download import download_mp3
from .naming import fields_for, render
from .search import Result, detail, search

# Options that take a value, mapped to the attribute they set.
VALUE_FLAGS = {
    "-d": "dest", "--dest": "dest",
    "-o": "out", "--out": "out",
    "-t": "template", "--template": "template",
    "-n": "name", "--name": "name",
    "-l": "limit", "--limit": "limit",
}
BOOL_FLAGS = {
    "-y": "yes", "--yes": "yes",
    "--any": "any",
    "--force": "force",
    "--dry-run": "dry_run",
    "-v": "verbose", "--verbose": "verbose",
    "-V": "version", "--version": "version",
    "-h": "help", "--help": "help",
}


class UsageError(Exception):
    pass


class Options:
    def __init__(self):
        self.dest = None
        self.out = None
        self.template = None
        self.name = None
        self.limit = 10
        self.yes = False
        self.any = False
        self.force = False
        self.dry_run = False
        self.verbose = False
        self.version = False
        self.help = False
        self.rest: list[str] = []


def parse(argv: list[str]) -> Options:
    opts = Options()
    index = 0
    while index < len(argv):
        token = argv[index]

        if token == "--":
            opts.rest.extend(argv[index + 1:])
            break

        if token.startswith("--") and "=" in token:
            flag, _, value = token.partition("=")
            if flag not in VALUE_FLAGS:
                raise UsageError(f"unknown option {flag}")
            setattr(opts, VALUE_FLAGS[flag], value)
            index += 1
            continue

        if token in VALUE_FLAGS:
            if index + 1 >= len(argv):
                raise UsageError(f"{token} needs a value")
            setattr(opts, VALUE_FLAGS[token], argv[index + 1])
            index += 2
            continue

        if token in BOOL_FLAGS:
            setattr(opts, BOOL_FLAGS[token], True)
            index += 1
            continue

        if token.startswith("-") and len(token) > 1 and not _looks_negative(token):
            raise UsageError(f"unknown option {token}")

        opts.rest.append(token)
        index += 1

    if isinstance(opts.limit, str):
        if not opts.limit.isdigit() or int(opts.limit) < 1:
            raise UsageError(f"--limit needs a positive number, got {opts.limit!r}")
        opts.limit = int(opts.limit)
    return opts


def _looks_negative(token: str) -> bool:
    """Allow a bare '-' and negative numbers through as arguments."""
    return token == "-" or token[1:].replace(".", "", 1).isdigit()


# --- display helpers -------------------------------------------------------

def _width(text: str) -> int:
    """Terminal columns a string occupies, counting CJK glyphs as two."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _fit(text: str, limit: int) -> str:
    if _width(text) <= limit:
        return text
    out, used = "", 0
    for char in text:
        step = 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if used + step > limit - 1:
            break
        out += char
        used += step
    return out + "…"


def _pad(text: str, limit: int) -> str:
    return text + " " * max(0, limit - _width(text))


def _views(count: int) -> str:
    for size, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if count >= size:
            return f"{count / size:.1f}{suffix}"
    return str(count)


def _clock(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


TITLE_COLUMN = 46
CHANNEL_COLUMN = 20


def _show(results: list[Result]) -> None:
    for number, item in enumerate(results, start=1):
        mark = "★" if item.is_catalog else " "
        head = f"{number:>3}  {mark}  {_views(item.views):>6}  {_clock(item.duration):>5}  "
        title = _pad(_fit(item.title, TITLE_COLUMN), TITLE_COLUMN)
        print(f"{head}{title}  {_fit(item.channel, CHANNEL_COLUMN)}")
    if any(item.is_catalog for item in results):
        print("  ★ = youtube music catalog track")


def _choose(results: list[Result], auto: bool = False) -> Result | None:
    if len(results) == 1:
        only = results[0]
        print(f"only match: {_fit(only.title, 60)}  ({_fit(only.channel, 24)})")
        return only

    if auto:
        top = results[0]
        print(f"top hit: {_fit(top.title, 60)}  ({_fit(top.channel, 24)})")
        return top

    _show(results)
    while True:
        try:
            raw = input(f"select [1-{len(results)}, enter=1, q=quit]: ").strip().lower()
        except EOFError:
            return None
        if raw in {"q", "quit"}:
            return None
        picked = 1 if not raw else int(raw) if raw.isdigit() else 0
        if 1 <= picked <= len(results):
            if not sys.stdin.isatty():
                print()
            return results[picked - 1]
        print(f"  not a choice: {raw!r}")


# --- the dest subcommand ---------------------------------------------------

def cmd_dest(args: list[str]) -> int:
    config = Config.load()
    action = args[0] if args else "list"

    if action == "list":
        if not config.dests:
            print("no destinations configured")
            print("add one with: ytmp3 dest add NAME TARGET")
            return 0
        width = max(len(name) for name in config.dests) + 2
        for name in sorted(config.dests):
            entry = config.dests[name]
            kind = "rclone" if is_rclone(entry["target"]) else "local"
            marker = "*" if name == config.default else " "
            template = entry.get("template") or config.template
            print(f"{marker} {name.ljust(width)}{kind:<8}{entry['target']}")
            print(f"  {' '.ljust(width)}{'':<8}{template}")
        return 0

    if action == "add":
        if len(args) < 3:
            raise UsageError("dest add needs NAME and TARGET")
        name, target = args[1], args[2]
        entry = {"target": target}
        if len(args) > 3:
            entry["template"] = args[3]
        config.dests[name] = entry
        if not config.default:
            config.default = name
        config.save()
        print(f"added {name} -> {target}")
        return 0

    if action == "remove":
        if len(args) < 2:
            raise UsageError("dest remove needs NAME")
        name = args[1]
        if name not in config.dests:
            print(f"ytmp3: no destination named {name}", file=sys.stderr)
            return 1
        del config.dests[name]
        if config.default == name:
            config.default = next(iter(sorted(config.dests)), "")
        config.save()
        print(f"removed {name}")
        return 0

    if action == "default":
        if len(args) < 2:
            raise UsageError("dest default needs NAME")
        name = args[1]
        if name not in config.dests:
            print(f"ytmp3: no destination named {name}", file=sys.stderr)
            return 1
        config.default = name
        config.save()
        print(f"default is now {name}")
        return 0

    raise UsageError(f"unknown dest action {action!r}")


# --- the main flow ---------------------------------------------------------

def _is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")


def _resolve_target(opts: Options) -> tuple[str, str]:
    config = Config.load()
    if opts.out:
        return opts.out, opts.template or config.template
    _, target, template = config.resolve(opts.dest)
    return target, opts.template or template


def run(opts: Options) -> int:
    query = " ".join(opts.rest).strip()
    if not query:
        raise UsageError("nothing to search for")

    target, template = _resolve_target(opts)

    if _is_url(query):
        info = detail(query)
        if not info:
            print(f"ytmp3: could not read {query}", file=sys.stderr)
            return 1
        chosen_url = query
        fields = fields_for(info, opts.name)
    else:
        results = search(query, limit=opts.limit, music_only=not opts.any)
        if not results:
            print(f"ytmp3: no music results for {query!r}", file=sys.stderr)
            print("try --any to include non-music results", file=sys.stderr)
            return 1
        picked = _choose(results, auto=opts.yes)
        if picked is None:
            return 130
        chosen_url = picked.url
        fields = fields_for(picked.info(), opts.name)

    filename = render(template, fields)
    print(f"→ {filename}")
    print(f"  {target}")

    if opts.dry_run:
        print(f"  (dry run, source: {chosen_url})")
        return 0

    if not opts.force and exists(target, filename, opts.verbose):
        print("already there; use --force to replace it")
        return 0

    with tempfile.TemporaryDirectory(prefix="ytmp3-") as scratch:
        produced = download_mp3(chosen_url, Path(scratch), filename, opts.verbose)
        final = deliver(produced, target, filename, opts.verbose)

    print(f"  saved to {final}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        sys.stdout.write(helptext.short_help())
        return 0

    try:
        opts = parse(argv)
        if opts.help:
            sys.stdout.write(helptext.full_help())
            return 0
        if opts.version:
            sys.stdout.write(helptext.version())
            return 0
        if opts.rest and opts.rest[0] == "dest":
            return cmd_dest(opts.rest[1:])
        return run(opts)
    except UsageError as exc:
        sys.stderr.write(helptext.usage_error(str(exc)))
        return 2
    except LookupError as exc:
        print(f"ytmp3: {exc}", file=sys.stderr)
        return 1
    except (DeliveryError, RuntimeError, ValueError) as exc:
        print(f"ytmp3: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())
