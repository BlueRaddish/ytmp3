"""Command line entry point."""

import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from . import help as helptext
from .config import Config, is_rclone
from .dest import DeliveryError, deliver, exists
from .download import download_mp3
from .naming import fields_for, render
from .info import detail

# Options that take a value, mapped to the attribute they set.
VALUE_FLAGS = {
    "-d": "dest", "--dest": "dest",
    "-o": "out", "--out": "out",
    "-t": "template", "--template": "template",
    "-n": "name", "--name": "name",
}
BOOL_FLAGS = {
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

    return opts


def _looks_negative(token: str) -> bool:
    """Allow a bare '-' and negative numbers through as arguments."""
    return token == "-" or token[1:].replace(".", "", 1).isdigit()


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
    parsed = urlsplit(text)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _resolve_target(opts: Options) -> tuple[str, str]:
    config = Config.load()
    if opts.out:
        return opts.out, opts.template or config.template
    _, target, template = config.resolve(opts.dest)
    return target, opts.template or template


def run(opts: Options) -> int:
    if len(opts.rest) != 1 or not _is_url(opts.rest[0]):
        raise UsageError("provide one HTTP or HTTPS URL")

    target, template = _resolve_target(opts)
    chosen_url = opts.rest[0]
    info = detail(chosen_url)
    if not info:
        print(f"ytmp3: could not read {chosen_url}", file=sys.stderr)
        return 1
    fields = fields_for(info, opts.name)

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
    if argv[0] == "app":
        from .app import main as app_main
        return app_main(argv[1:])

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
