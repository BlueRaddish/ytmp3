"""Deliver a finished file to a local directory or an rclone remote."""

import shutil
import subprocess
from pathlib import Path

from .config import is_rclone


class DeliveryError(RuntimeError):
    pass


def _rclone() -> str:
    found = shutil.which("rclone")
    if not found:
        raise DeliveryError(
            "rclone not found; install it from https://rclone.org/downloads/ "
            "or use a local destination"
        )
    return found


def _run(args: list[str], verbose: bool) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=not verbose,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def exists(target: str, filename: str, verbose: bool = False) -> bool:
    """Is `filename` already present at `target`?"""
    if not is_rclone(target):
        return (Path(target).expanduser() / filename).exists()

    remote = f"{target.rstrip('/')}/{filename}"
    proc = _run([_rclone(), "lsf", remote], verbose=False)
    return proc.returncode == 0 and bool((proc.stdout or "").strip())


def deliver(source: Path, target: str, filename: str, verbose: bool = False) -> str:
    """Move `source` to `target` as `filename`. Returns the final location."""
    if is_rclone(target):
        remote = f"{target.rstrip('/')}/{filename}"
        proc = _run([_rclone(), "copyto", str(source), remote], verbose)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            tail = detail[-1] if detail else f"rclone exited {proc.returncode}"
            raise DeliveryError(f"upload failed: {tail}")
        return remote

    directory = Path(target).expanduser()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        final = directory / filename
        shutil.move(str(source), str(final))
    except OSError as exc:
        raise DeliveryError(f"could not write to {directory}: {exc}") from exc
    return str(final)
