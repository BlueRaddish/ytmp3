"""Read and write the ytmp3 config file."""

import os
import re
import tomllib
from pathlib import Path

DEFAULT_TEMPLATE = "{artist} - {title}.mp3"

# An rclone target looks like "remote:path". A Windows drive is a single
# letter, so require at least two characters to avoid claiming "C:\Music".
_RCLONE_TARGET = re.compile(r"^[A-Za-z0-9_.\-]{2,}:")


def config_path() -> Path:
    override = os.environ.get("YTMP3_CONFIG")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".config"
    return root / "ytmp3" / "config.toml"


def is_rclone(target: str) -> bool:
    return bool(_RCLONE_TARGET.match(target))


class Config:
    def __init__(self, data: dict, path: Path):
        self.path = path
        self.default = data.get("default") or ""
        self.template = data.get("template") or DEFAULT_TEMPLATE
        self.dests: dict[str, dict] = dict(data.get("dest") or {})

    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        if not path.exists():
            return cls({}, path)
        with path.open("rb") as handle:
            return cls(tomllib.load(handle), path)

    def resolve(self, name: str | None) -> tuple[str, str, str]:
        """Return (name, target, template) for a destination."""
        chosen = name or self.default
        if not chosen:
            raise LookupError(
                "no destination given and no default is set; "
                "use -o TARGET, or run 'ytmp3 dest add NAME TARGET'"
            )
        if chosen not in self.dests:
            known = ", ".join(sorted(self.dests)) or "none configured"
            raise LookupError(f"unknown destination {chosen!r}; known: {known}")
        entry = self.dests[chosen]
        return chosen, entry["target"], entry.get("template") or self.template

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self._dump(), encoding="utf-8")

    def _dump(self) -> str:
        lines = []
        if self.default:
            lines.append(f"default = {_quote(self.default)}")
        lines.append(f"template = {_quote(self.template)}")
        for name in sorted(self.dests):
            entry = self.dests[name]
            lines.append("")
            lines.append(f"[dest.{_key(name)}]")
            lines.append(f"target = {_quote(entry['target'])}")
            if entry.get("template"):
                lines.append(f"template = {_quote(entry['template'])}")
        return "\n".join(lines) + "\n"


def _quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _key(name: str) -> str:
    return name if re.fullmatch(r"[A-Za-z0-9_-]+", name) else _quote(name)
