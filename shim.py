#!/usr/bin/env python3
"""Entry point for the ~/bin shims: run ytmp3 from the clone, uninstalled.

Deliberately not named ytmp3.py -- that would shadow the package next to it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ytmp3.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
