"""raumtube-model — dump every source file in the model package to stdout."""

import argparse
from pathlib import Path

from cprima_raumtube._compat import ensure_utf8_stdout


def main() -> None:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description="Print all model source files to stdout.")
    ap.add_argument(
        "--model-dir",
        default=None,
        help="Override path to model package (default: auto-detected relative to this script)",
    )
    args = ap.parse_args()

    if args.model_dir:
        model_dir = Path(args.model_dir)
    else:
        model_dir = Path(__file__).parent.parent / "src" / "cprima_raumtube" / "model"

    if not model_dir.is_dir():
        ap.error(f"Model directory not found: {model_dir}")

    files = sorted(model_dir.glob("*.py"))
    if not files:
        print(f"No .py files found in {model_dir}")
        return

    for path in files:
        print(f"# {'=' * 76}")
        print(f"# {path.name}")
        print(f"# {'=' * 76}")
        print(path.read_text(encoding="utf-8"))
