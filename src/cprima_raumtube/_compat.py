"""CLI-only helpers — never import from library code."""

import sys


def ensure_utf8_stdout() -> None:
    """Reconfigure stdout to UTF-8; required on Windows for emoji/Unicode output."""
    sys.stdout.reconfigure(encoding="utf-8")
