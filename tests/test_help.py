"""Lint the help output against the Help Screen Protocol.

Help rots silently, so these are cheap rules run in CI rather than review.
"""

import re
import subprocess
import sys
from pathlib import Path

from ytmp3 import help as helptext
from ytmp3.cli import BOOL_FLAGS, VALUE_FLAGS

HARD_WIDTH = 95
SOFT_WIDTH = 80
REPO_ROOT = Path(__file__).resolve().parents[1]

CANONICAL_ORDER = [
    "NAME", "USAGE", "DESCRIPTION", "EXAMPLES", "COMMANDS", "OPTIONS",
    "ARGUMENTS", "ENVIRONMENT", "FILES", "EXIT STATUS", "SEE ALSO",
]


def _run(args):
    return subprocess.run(
        [sys.executable, "-m", "ytmp3", *args],
        cwd=REPO_ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_no_line_exceeds_hard_width():
    for line in helptext.full_help().splitlines():
        assert len(line) <= HARD_WIDTH, f"{len(line)} cols: {line!r}"


def test_most_lines_stay_within_soft_width():
    lines = helptext.full_help().splitlines()
    over = [line for line in lines if len(line) > SOFT_WIDTH]
    assert not over, f"lines over {SOFT_WIDTH} cols: {over}"


def test_sections_appear_in_canonical_order():
    found = [
        line for line in helptext.full_help().splitlines()
        if line and not line.startswith(" ") and line.strip() == line
    ]
    assert found == CANONICAL_ORDER


def test_descriptions_are_lowercase_and_unpunctuated():
    tables = (
        helptext.COMMANDS + helptext.OPTIONS + helptext.ARGUMENTS
        + helptext.ENVIRONMENT + helptext.FILES + helptext.EXIT_STATUS
    )
    for left, description in tables:
        assert not description.endswith("."), f"{left}: trailing period"
        assert description[0].islower() or not description[0].isalpha(), (
            f"{left}: description should start lowercase"
        )
        assert "\n" not in description, f"{left}: description must be one line"


def test_documented_options_match_the_parser():
    documented = set()
    for left, _ in helptext.OPTIONS:
        for piece in left.split(","):
            token = piece.strip().split(" ")[0]
            if token.startswith("-"):
                documented.add(token)
    assert documented == set(VALUE_FLAGS) | set(BOOL_FLAGS)


def test_one_placeholder_style():
    # POSIX notation uses bare UPPER placeholders; no <angled> mixed in.
    assert "<" not in helptext.full_help()


def test_help_goes_to_stdout_and_exits_zero():
    for flag in ("-h", "--help"):
        proc = _run([flag])
        assert proc.returncode == 0
        assert proc.stderr == ""
        assert "USAGE" in proc.stdout


def test_bare_invocation_is_the_short_tier():
    proc = _run([])
    assert proc.returncode == 0
    assert proc.stderr == ""
    assert "--help" in proc.stdout
    assert len(proc.stdout.splitlines()) < 20


def test_usage_error_is_concise_stderr_exit_two():
    proc = _run(["--nonsense"])
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "usage:" in proc.stderr
    assert "OPTIONS" not in proc.stderr


def test_version_flag():
    proc = _run(["-V"])
    assert proc.returncode == 0
    assert re.fullmatch(r"ytmp3 \d+\.\d+\.\d+\s*", proc.stdout)


def test_every_example_parses():
    """Examples are a contract: each must at least survive the parser."""
    from ytmp3.cli import parse

    for _, command in helptext.EXAMPLES:
        argv = command.split()[1:]
        argv = [token.strip("'") for token in argv]
        parse(argv)
