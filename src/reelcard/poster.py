"""Postcard poster layout and PNG export."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_WIDTH = 1240
DEFAULT_HEIGHT = 1748
DEFAULT_DPI = 300
PAPER = (247, 244, 236)
INK = (40, 36, 32)
MUTED_INK = (105, 96, 84)
BORDER = (183, 172, 154)
_FONT_PATH = Path(__file__).parent / "fonts" / "CormorantGaramond.ttf"


def render_poster(
    barcode: Image.Image,
    *,
    title: str,
    runtime_seconds: float,
    year: int | None = None,
    director: str | None = None,
    subtitle: str | None = None,
    credits: str | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    dpi: float = DEFAULT_DPI,
) -> Image.Image:
    """Render a portrait postcard poster from a plain color barcode."""
    _validate_dimensions(width, height)
    _validate_dpi(dpi)
    if not isinstance(barcode, Image.Image) or barcode.width <= 0 or barcode.height <= 0:
        raise ValueError("barcode must be a non-empty Pillow image")
    if barcode.width > 10_000:
        raise ValueError("barcode must not contain more than 10000 stripes")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must not be empty")
    if year is not None and (
        isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 9999
    ):
        raise ValueError("year must be an integer between 1 and 9999")
    runtime_label = _format_runtime(runtime_seconds)
    title_text = _normalize_text(title)
    director_text = _normalize_optional_text(director)
    subtitle_text = _normalize_optional_text(subtitle)
    credits_text = _normalize_optional_text(credits)

    poster = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(poster)
    scale = min(width / DEFAULT_WIDTH, height / DEFAULT_HEIGHT)
    _draw_border(draw, width, height, scale)

    content_left = round(width * 0.10)
    content_right = round(width * 0.90)
    content_width = content_right - content_left
    center_x = width // 2

    title_font, title_lines = _fit_wrapped_text(
        title_text,
        max_width=round(content_width * 0.98),
        max_lines=2,
        initial_size=max(10, round(width * 0.074)),
        minimum_size=max(9, round(width * 0.038)),
        weight=500,
    )
    title_line_height = _line_height(title_font)
    title_top = round(height * 0.075)
    for index, line in enumerate(title_lines):
        draw.text(
            (center_x, title_top + index * title_line_height),
            line,
            fill=INK,
            font=title_font,
            anchor="mt",
        )

    if year is not None:
        year_font = _font(max(10, round(width * 0.027)), weight=400)
        draw.text(
            (center_x, round(height * 0.226)),
            str(year),
            fill=MUTED_INK,
            font=year_font,
            anchor="mt",
        )

    barcode_box = (
        content_left,
        round(height * 0.292),
        content_right,
        round(height * 0.753),
    )
    resized_barcode = barcode.convert("RGB").resize(
        (barcode_box[2] - barcode_box[0], barcode_box[3] - barcode_box[1]),
        Image.Resampling.NEAREST,
    )
    poster.paste(resized_barcode, barcode_box[:2])

    if subtitle_text is not None:
        subtitle_font = _fit_single_line(
            subtitle_text,
            max_width=content_width,
            initial_size=max(10, round(width * 0.031)),
            minimum_size=max(9, round(width * 0.018)),
            weight=400,
        )
        draw.text(
            (center_x, round(height * 0.777)),
            subtitle_text,
            fill=INK,
            font=subtitle_font,
            anchor="mt",
        )

    if director_text is not None:
        director_label = f"DIRECTED BY {director_text}"
        director_font = _fit_single_line(
            director_label,
            max_width=content_width,
            initial_size=max(9, round(width * 0.020)),
            minimum_size=max(8, round(width * 0.014)),
            weight=400,
        )
        draw.text(
            (center_x, round(height * 0.827)),
            director_label,
            fill=MUTED_INK,
            font=director_font,
            anchor="mt",
        )

    footer_y = round(height * 0.902)
    draw.line(
        (
            content_left,
            round(height * 0.872),
            content_right,
            round(height * 0.872),
        ),
        fill=BORDER,
        width=max(1, round(scale)),
    )
    if credits_text is not None:
        credits_font, credit_lines = _fit_wrapped_text(
            credits_text,
            max_width=round(content_width * 0.60),
            max_lines=2,
            initial_size=max(9, round(width * 0.020)),
            minimum_size=max(8, round(width * 0.013)),
            weight=400,
        )
        credit_line_height = _line_height(credits_font)
        for index, line in enumerate(credit_lines):
            draw.text(
                (content_left, footer_y + index * credit_line_height),
                line,
                fill=MUTED_INK,
                font=credits_font,
                anchor="lt",
            )

    runtime_font = _fit_single_line(
        runtime_label,
        max_width=round(content_width * 0.35),
        initial_size=max(10, round(width * 0.026)),
        minimum_size=max(9, round(width * 0.018)),
        weight=500,
    )
    draw.text(
        (content_right, footer_y),
        runtime_label,
        fill=INK,
        font=runtime_font,
        anchor="rt",
    )
    return poster


def save_poster(
    poster: Image.Image,
    output_path: str | Path,
    *,
    dpi: float = DEFAULT_DPI,
    overwrite: bool = False,
) -> None:
    """Save a poster as PNG with print-resolution metadata."""
    if not isinstance(poster, Image.Image):
        raise TypeError("poster must be a Pillow image")
    _validate_dpi(dpi)
    path = Path(output_path)
    if path.suffix.lower() != ".png":
        raise ValueError("poster output path must have a .png extension")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {path.parent}")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path}")
    poster.convert("RGB").save(path, format="PNG", dpi=(dpi, dpi))


def _validate_dimensions(width: int, height: int) -> None:
    if (
        isinstance(width, bool)
        or not isinstance(width, int)
        or isinstance(height, bool)
        or not isinstance(height, int)
        or width < 300
        or height < 400
        or width > 10_000
        or height > 20_000
    ):
        raise ValueError(
            "poster dimensions must be integers between 300x400 and 10000x20000"
        )
    if width >= height:
        raise ValueError("poster dimensions must be portrait (width less than height)")


def _validate_dpi(dpi: float) -> None:
    if (
        isinstance(dpi, bool)
        or not isinstance(dpi, (int, float))
        or not math.isfinite(dpi)
        or not 1 <= dpi <= 2400
    ):
        raise ValueError("dpi must be finite and between 1 and 2400")


def _format_runtime(runtime_seconds: float) -> str:
    if (
        isinstance(runtime_seconds, bool)
        or not isinstance(runtime_seconds, (int, float))
        or not math.isfinite(runtime_seconds)
        or runtime_seconds <= 0
    ):
        raise ValueError("runtime_seconds must be a positive finite number")
    total_minutes = max(1, math.floor(runtime_seconds / 60 + 0.5))
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours}H {minutes:02d}M"
    return f"{total_minutes} MIN"


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("poster text fields must be strings")
    normalized = _normalize_text(value)
    return normalized or None


def _font(size: int, *, weight: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(_FONT_PATH), size=max(1, size))
    font.set_variation_by_axes([weight])
    return font


def _fit_single_line(
    text: str,
    *,
    max_width: int,
    initial_size: int,
    minimum_size: int,
    weight: int,
) -> ImageFont.FreeTypeFont:
    for size in range(initial_size, minimum_size - 1, -1):
        font = _font(size, weight=weight)
        if font.getlength(text) <= max_width:
            return font
    raise ValueError("poster text is too long to fit in its allocated area")


def _fit_wrapped_text(
    text: str,
    *,
    max_width: int,
    max_lines: int,
    initial_size: int,
    minimum_size: int,
    weight: int,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    for size in range(initial_size, minimum_size - 1, -1):
        font = _font(size, weight=weight)
        lines = _wrap_text(text, font, max_width)
        if lines is not None and len(lines) <= max_lines:
            return font, lines
    raise ValueError("poster text is too long to fit in its allocated area")


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str] | None:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if font.getlength(candidate) > max_width:
            if not current or font.getlength(word) > max_width:
                return None
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    bounds = font.getbbox("Ag")
    return max(1, bounds[3] - bounds[1] + round(font.size * 0.1))


def _draw_border(
    draw: ImageDraw.ImageDraw,
    width: int,
    height: int,
    scale: float,
) -> None:
    inset_x = round(width * 0.035)
    inset_y = round(height * 0.025)
    draw.rectangle(
        (inset_x, inset_y, width - inset_x - 1, height - inset_y - 1),
        outline=BORDER,
        width=max(1, round(1.4 * scale)),
    )
