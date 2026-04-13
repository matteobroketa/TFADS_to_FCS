from __future__ import annotations

import argparse
from pathlib import Path

from .converter import ConversionError, convert_to_fcs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TFADS .xls/.csv/.tsv to FCS 3.0 converter")
    parser.add_argument("input", nargs="?", help="Input data file")
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output .fcs path (defaults next to input file)",
    )
    parser.add_argument(
        "--nogui",
        action="store_true",
        help="Force CLI mode even when no input argument is provided.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.input:
        try:
            output = convert_to_fcs(args.input, args.output, progress=print)
        except ConversionError as exc:
            print(f"Error: {exc}")
            return 1
        print(f"Saved: {output}")
        return 0

    if args.nogui:
        parser.print_help()
        return 1

    from .gui import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
