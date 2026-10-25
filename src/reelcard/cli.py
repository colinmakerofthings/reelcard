"""Command-line entry point for Reelcard."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="reelcard",
        description="Create a postcard-sized film barcode poster from a video.",
    )
    parser.add_argument("input", help="path to a local video file")
    return parser


def main() -> int:
    """Parse arguments and report that video processing is not implemented yet."""
    parser = build_parser()
    parser.parse_args()
    print(
        "Reelcard is not ready to process videos yet.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
