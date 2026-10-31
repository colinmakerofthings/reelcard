"""Command-line interface and end-to-end poster pipeline."""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from reelcard.colors import make_barcode
from reelcard.errors import ReelcardError
from reelcard.metadata import MetadataLookupError, lookup_movie
from reelcard.poster import (
    DEFAULT_DPI,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    render_poster,
    render_svg,
    save_poster,
    save_svg,
)
from reelcard.video import MAX_STRIPES, iter_video_frames, probe_video


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="reelcard",
        description="Create a postcard-sized film barcode poster from a video.",
    )
    parser.add_argument("input", type=Path, help="path to a local video file")
    parser.add_argument("--title", help="film title (defaults to the input filename)")
    parser.add_argument("--year", type=_parse_year, help="film release year")
    parser.add_argument("--director", help="director credit")
    parser.add_argument("--writer", help="writer credit")
    parser.add_argument("--starring", help="lead cast")
    parser.add_argument(
        "--runtime",
        type=_parse_runtime,
        help="runtime label (e.g. '122 min'; overrides IMDb and video runtime)",
    )
    parser.add_argument("--rating", help="MPAA film rating")
    parser.add_argument("--imdb-rating", help="IMDb score (e.g. 8.0/10)")
    parser.add_argument("--plot", help="short plot summary for the poster footer")
    parser.add_argument("--subtitle", help="short descriptor below the barcode")
    parser.add_argument("--credits", help="optional footer credits")
    parser.add_argument(
        "--imdb-id",
        help="look up missing metadata for this IMDb ID via OMDb",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="output path (defaults to a title-based name in the current directory)",
    )
    parser.add_argument(
        "--format",
        choices=("png", "svg"),
        default="png",
        help="output format (default: png)",
    )
    parser.add_argument(
        "--stripes",
        type=_positive_int,
        default=300,
        help=f"number of sampled frames/stripes (1-{MAX_STRIPES}; default: 300)",
    )
    parser.add_argument(
        "--color-style",
        choices=("natural", "brighter", "vivid"),
        default="natural",
        help="barcode color treatment (default: natural)",
    )
    parser.add_argument(
        "--size",
        choices=("postcard",),
        default="postcard",
        help="named print-size preset (default: postcard, 148 x 105 mm)",
    )
    parser.add_argument("--width", type=_positive_int, help="custom output width in pixels")
    parser.add_argument("--height", type=_positive_int, help="custom output height in pixels")
    parser.add_argument(
        "--dpi",
        type=_positive_float,
        default=DEFAULT_DPI,
        help=f"print resolution metadata (default: {DEFAULT_DPI})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace the output file if it already exists",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the video-to-poster pipeline and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path = args.input
    title = args.title if args.title is not None else input_path.stem
    output_path = args.output or Path.cwd() / f"{_safe_filename(title)}.{args.format}"

    try:
        if not title.strip():
            raise ValueError("title must not be empty")
        width, height = _resolve_dimensions(args.width, args.height)
        _validate_dpi(args.dpi)
        _validate_stripes(args.stripes)
        _validate_input_and_output(
            input_path,
            output_path,
            output_format=args.format,
            overwrite=args.force,
        )

        movie_metadata = None
        if args.imdb_id:
            try:
                movie_metadata = lookup_movie(
                    imdb_id=args.imdb_id,
                    api_key=os.environ.get("OMDB_API_KEY"),
                )
                if movie_metadata is None:
                    print(
                        "reelcard: warning: no OMDb match found; using supplied "
                        "metadata and defaults.",
                        file=sys.stderr,
                    )
            except MetadataLookupError as exc:
                print(
                    f"reelcard: warning: {exc} Continuing without lookup.",
                    file=sys.stderr,
                )
                movie_metadata = None

        if movie_metadata is not None:
            if args.title is None and movie_metadata.title:
                title = movie_metadata.title

        print(f"Analyzing {input_path}...", file=sys.stderr)
        metadata = probe_video(input_path)
        print(f"Sampling {args.stripes} frames...", file=sys.stderr)
        barcode = make_barcode(
            iter_video_frames(input_path, args.stripes, metadata=metadata),
            color_style=args.color_style,
        )
        render_options = {
            "title": title,
            "runtime_seconds": metadata.duration,
            "year": args.year or (movie_metadata.year if movie_metadata else None),
            "director": args.director
            or (movie_metadata.director if movie_metadata else None),
            "writer": args.writer or (movie_metadata.writer if movie_metadata else None),
            "starring": args.starring
            or (movie_metadata.starring if movie_metadata else None),
            "runtime": args.runtime or (movie_metadata.runtime if movie_metadata else None),
            "rating": args.rating or (movie_metadata.rating if movie_metadata else None),
            "imdb_rating": args.imdb_rating
            or (movie_metadata.imdb_rating if movie_metadata else None),
            "plot": args.plot or (movie_metadata.plot if movie_metadata else None),
            "subtitle": args.subtitle,
            "credits": args.credits,
            "width": width,
            "height": height,
            "dpi": args.dpi,
        }
        if args.format == "svg":
            svg = render_svg(barcode, **render_options)
            save_svg(svg, output_path, overwrite=args.force)
        else:
            poster = render_poster(barcode, **render_options)
            save_poster(
                poster,
                output_path,
                dpi=args.dpi,
                overwrite=args.force,
            )
    except (ReelcardError, ValueError, OSError) as exc:
        print(f"reelcard: error: {exc}", file=sys.stderr)
        return 2

    print(f"Saved poster to {output_path}")
    return 0


def _parse_year(value: str) -> int:
    try:
        year = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("year must be an integer from 1 to 9999") from exc
    if not 1 <= year <= 9999:
        raise argparse.ArgumentTypeError("year must be between 1 and 9999")
    return year


def _parse_runtime(value: str) -> str:
    runtime = " ".join(value.split())
    if not runtime:
        raise argparse.ArgumentTypeError("runtime must not be empty")
    return runtime


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _positive_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive number") from exc
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return number


def _resolve_dimensions(width: int | None, height: int | None) -> tuple[int, int]:
    if (width is None) != (height is None):
        raise ValueError("custom output dimensions require both --width and --height")
    resolved_width = DEFAULT_WIDTH if width is None else width
    resolved_height = DEFAULT_HEIGHT if height is None else height
    if (
        resolved_width < 300
        or resolved_width > 10_000
        or resolved_height < 400
        or resolved_height > 20_000
    ):
        raise ValueError(
            "output dimensions must be between 300x400 and 10000x20000 pixels"
        )
    if resolved_width <= resolved_height:
        raise ValueError("output dimensions must be landscape (width greater than height)")
    return resolved_width, resolved_height


def _validate_dpi(dpi: float) -> None:
    if not math.isfinite(dpi) or not 1 <= dpi <= 2400:
        raise ValueError("DPI must be between 1 and 2400")


def _validate_stripes(count: int) -> None:
    if count > MAX_STRIPES:
        raise ValueError(f"stripe count must not exceed {MAX_STRIPES}")


def _validate_input_and_output(
    input_path: Path,
    output_path: Path,
    *,
    output_format: str,
    overwrite: bool,
) -> None:
    if not input_path.is_file():
        raise ValueError(f"input does not exist or is not a file: {input_path}")
    if output_path.suffix.lower() != f".{output_format}":
        raise ValueError(f"output path must have a .{output_format} extension")
    if not output_path.parent.is_dir():
        raise ValueError(f"output directory does not exist: {output_path.parent}")
    if output_path.exists() and output_path.is_dir():
        raise ValueError(f"output path is a directory: {output_path}")
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"output already exists: {output_path} (use --force to replace it)"
        )
    if input_path.resolve() == output_path.resolve():
        raise ValueError("output path must not be the same as the input video")


def _safe_filename(title: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", title.strip())
    sanitized = re.sub(r"\s+", "-", sanitized).strip(" .-")
    sanitized = sanitized[:100].rstrip(" .-")
    if not sanitized or sanitized.split(".", 1)[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }:
        sanitized = "reelcard-poster"
    return sanitized


if __name__ == "__main__":
    raise SystemExit(main())
