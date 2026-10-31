"""Postcard poster layout and PNG/SVG export."""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DEFAULT_WIDTH = 1748
DEFAULT_HEIGHT = 1240
DEFAULT_DPI = 300
PAPER = (243, 242, 236)
INK = (22, 23, 22)
PLACEHOLDER = "NOT PROVIDED"
_FONT_PATH = Path(__file__).parent / "fonts" / "Montserrat.ttf"
_FONT_LICENSE_PATH = Path(__file__).parent / "fonts" / "Montserrat-OFL.txt"


@dataclass(frozen=True)
class _FooterLayout:
    top: int
    barcode_top: int
    barcode_bottom: int
    plot_lines: list[str]
    plot_font: ImageFont.FreeTypeFont | None
    credits_top: int
    credits_font: ImageFont.FreeTypeFont | None
    subtitle_top: int
    subtitle_font: ImageFont.FreeTypeFont | None


@dataclass(frozen=True)
class _MetadataFieldLayout:
    label: str
    x: int
    label_font: ImageFont.FreeTypeFont
    value_font: ImageFont.FreeTypeFont
    value_top: int
    lines: list[str]


def render_poster(
    barcode: Image.Image,
    *,
    title: str,
    runtime_seconds: float,
    year: int | None = None,
    director: str | None = None,
    writer: str | None = None,
    starring: str | None = None,
    runtime: str | None = None,
    rating: str | None = None,
    imdb_rating: str | None = None,
    plot: str | None = None,
    subtitle: str | None = None,
    credits: str | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    dpi: float = DEFAULT_DPI,
) -> Image.Image:
    """Render a minimal landscape postcard poster from a color barcode."""
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
    runtime_label = _normalize_optional_text(runtime) or _format_runtime(runtime_seconds)
    title_text = _normalize_text(title)
    director_text = _normalize_optional_text(director) or PLACEHOLDER
    writer_text = _normalize_optional_text(writer) or PLACEHOLDER
    starring_text = _normalize_optional_text(starring) or PLACEHOLDER
    rating_text = _normalize_optional_text(rating)
    imdb_rating_text = _normalize_optional_text(imdb_rating)
    plot_text = _normalize_optional_text(plot)
    subtitle_text = _normalize_optional_text(subtitle)
    credits_text = _normalize_optional_text(credits)

    poster = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(poster)
    content_left = round(width * 0.045)
    content_right = round(width * 0.955)
    content_width = content_right - content_left

    title_max_width = round(content_width * 0.75)
    title_initial_size = max(10, round(width * 0.040))
    title_font = _font(title_initial_size, weight=700)
    title_lines = _wrap_text(title_text.upper(), title_font, title_max_width)
    if title_lines is None or len(title_lines) > 2:
        raise ValueError("title is too long to fit in its allocated area")
    title_line_height = _line_height(title_font)
    title_top = round(height * 0.055)
    for index, line in enumerate(title_lines):
        draw.text(
            (content_left, title_top + index * title_line_height),
            line,
            fill=INK,
            font=title_font,
            anchor="lt",
        )

    year_text = str(year) if year is not None else "YEAR N/A"
    year_font = _fit_single_line(
        year_text,
        max_width=round(content_width * 0.25),
        initial_size=max(10, round(width * 0.040)),
        minimum_size=max(9, round(width * 0.022)),
        weight=700,
    )
    draw.text(
        (content_right, title_top),
        year_text,
        fill=INK,
        font=year_font,
        anchor="rt",
    )
    metadata_fields = (
        ("DIRECTED BY", director_text),
        ("WRITTEN BY", writer_text),
        ("STARRING", starring_text),
        ("RUNTIME", runtime_label),
    )
    if rating_text is not None:
        metadata_fields += (("RATED", rating_text),)
    if imdb_rating_text is not None:
        metadata_fields += (("IMDB RATING", imdb_rating_text),)
    metadata_top = max(
        round(height * 0.135),
        title_top + len(title_lines) * title_line_height + round(height * 0.015),
    )
    metadata_layout, metadata_bottom = _layout_metadata_fields(
        metadata_fields,
        content_left=content_left,
        content_width=content_width,
        gap=round(width * 0.02),
        metadata_top=metadata_top,
        width=width,
        height=height,
    )
    for field in metadata_layout:
        draw.text(
            (field.x, metadata_top),
            field.label,
            fill=INK,
            font=field.label_font,
            anchor="lt",
        )
        for line_index, line in enumerate(field.lines):
            draw.text(
                (
                    field.x,
                    field.value_top + line_index * _line_height(field.value_font),
                ),
                line,
                fill=INK,
                font=field.value_font,
                anchor="lt",
            )

    footer = _layout_footer(
        plot_text,
        credits_text,
        subtitle_text,
        width=width,
        height=height,
        content_width=content_width,
        barcode_top=max(
            round(height * 0.225),
            metadata_bottom + round(height * 0.02),
        ),
    )
    barcode_box = (
        content_left,
        footer.barcode_top,
        content_right,
        footer.barcode_bottom,
    )
    resized_barcode = barcode.convert("RGB").resize(
        (barcode_box[2] - barcode_box[0], barcode_box[3] - barcode_box[1]),
        Image.Resampling.NEAREST,
    )
    poster.paste(resized_barcode, barcode_box[:2])

    if footer.plot_font is not None:
        for line_index, line in enumerate(footer.plot_lines):
            draw.text(
                (content_left, footer.top + line_index * _line_height(footer.plot_font)),
                line,
                fill=INK,
                font=footer.plot_font,
                anchor="lt",
            )
    if credits_text is not None and footer.credits_font is not None:
        draw.text(
            (content_left, footer.credits_top),
            credits_text.upper(),
            fill=INK,
            font=footer.credits_font,
            anchor="lt",
        )

    if subtitle_text is not None and footer.subtitle_font is not None:
        draw.text(
            (content_left, footer.subtitle_top),
            subtitle_text,
            fill=INK,
            font=footer.subtitle_font,
            anchor="lt",
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


def render_svg(
    barcode: Image.Image,
    *,
    title: str,
    runtime_seconds: float,
    year: int | None = None,
    director: str | None = None,
    writer: str | None = None,
    starring: str | None = None,
    runtime: str | None = None,
    rating: str | None = None,
    imdb_rating: str | None = None,
    plot: str | None = None,
    subtitle: str | None = None,
    credits: str | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    dpi: float = DEFAULT_DPI,
) -> str:
    """Render the poster as self-contained SVG with an embedded font."""
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

    runtime_label = _normalize_optional_text(runtime) or _format_runtime(runtime_seconds)
    title_text = _normalize_text(title).upper()
    director_text = _normalize_optional_text(director) or PLACEHOLDER
    writer_text = _normalize_optional_text(writer) or PLACEHOLDER
    starring_text = _normalize_optional_text(starring) or PLACEHOLDER
    rating_text = _normalize_optional_text(rating)
    imdb_rating_text = _normalize_optional_text(imdb_rating)
    plot_text = _normalize_optional_text(plot)
    subtitle_text = _normalize_optional_text(subtitle)
    credits_text = _normalize_optional_text(credits)

    elements: list[str] = [
        f'<rect width="{width}" height="{height}" fill="{_svg_color(PAPER)}"/>'
    ]
    content_left = round(width * 0.045)
    content_right = round(width * 0.955)
    content_width = content_right - content_left

    title_max_width = round(content_width * 0.75)
    title_initial_size = max(10, round(width * 0.040))
    title_minimum_size = max(9, round(width * 0.025))
    try:
        title_font = _fit_single_line(
            title_text,
            max_width=title_max_width,
            initial_size=title_initial_size,
            minimum_size=title_minimum_size,
            weight=700,
        )
        title_lines = [title_text]
    except ValueError:
        title_font, title_lines = _fit_wrapped_text(
            title_text,
            max_width=title_max_width,
            max_lines=2,
            initial_size=title_initial_size,
            minimum_size=title_minimum_size,
            weight=700,
        )
    title_line_height = _line_height(title_font)
    title_top = round(height * 0.055)
    for index, line in enumerate(title_lines):
        elements.append(
            _svg_text(
                line,
                x=content_left,
                top=title_top + index * title_line_height,
                font=title_font,
                weight=700,
            )
        )

    year_text = str(year) if year is not None else "YEAR N/A"
    year_font = _fit_single_line(
        year_text,
        max_width=round(content_width * 0.25),
        initial_size=max(10, round(width * 0.040)),
        minimum_size=max(9, round(width * 0.022)),
        weight=700,
    )
    elements.append(
        _svg_text(
            year_text,
            x=content_right,
            top=title_top,
            font=year_font,
            weight=700,
            anchor="end",
        )
    )
    metadata_fields = (
        ("DIRECTED BY", director_text),
        ("WRITTEN BY", writer_text),
        ("STARRING", starring_text),
        ("RUNTIME", runtime_label),
    )
    if rating_text is not None:
        metadata_fields += (("RATED", rating_text),)
    if imdb_rating_text is not None:
        metadata_fields += (("IMDB RATING", imdb_rating_text),)
    metadata_top = max(
        round(height * 0.135),
        title_top + len(title_lines) * title_line_height + round(height * 0.015),
    )
    metadata_layout, metadata_bottom = _layout_metadata_fields(
        metadata_fields,
        content_left=content_left,
        content_width=content_width,
        gap=round(width * 0.02),
        metadata_top=metadata_top,
        width=width,
        height=height,
    )
    for field in metadata_layout:
        elements.append(
            _svg_text(
                field.label,
                x=field.x,
                top=metadata_top,
                font=field.label_font,
                weight=700,
            )
        )
        for line_index, line in enumerate(field.lines):
            elements.append(
                _svg_text(
                    line,
                    x=field.x,
                    top=field.value_top + line_index * _line_height(field.value_font),
                    font=field.value_font,
                    weight=400,
                )
            )

    footer = _layout_footer(
        plot_text,
        credits_text,
        subtitle_text,
        width=width,
        height=height,
        content_width=content_width,
        barcode_top=max(
            round(height * 0.225),
            metadata_bottom + round(height * 0.02),
        ),
    )
    barcode_box = (
        content_left,
        footer.barcode_top,
        content_right,
        footer.barcode_bottom,
    )
    resized_barcode = barcode.convert("RGB").resize(
        (barcode_box[2] - barcode_box[0], barcode_box[3] - barcode_box[1]),
        Image.Resampling.NEAREST,
    )
    barcode_pixels = resized_barcode.load()
    run_start = 0
    run_color = barcode_pixels[0, 0]
    for x in range(1, resized_barcode.width):
        color = barcode_pixels[x, 0]
        if color == run_color:
            continue
        elements.append(
            f'<rect x="{barcode_box[0] + run_start}" y="{barcode_box[1]}" '
            f'width="{x - run_start}" height="{barcode_box[3] - barcode_box[1]}" '
            f'fill="{_svg_color(run_color)}"/>'
        )
        run_start = x
        run_color = color
    elements.append(
        f'<rect x="{barcode_box[0] + run_start}" y="{barcode_box[1]}" '
        f'width="{resized_barcode.width - run_start}" '
        f'height="{barcode_box[3] - barcode_box[1]}" '
        f'fill="{_svg_color(run_color)}"/>'
    )

    if footer.plot_font is not None:
        for line_index, line in enumerate(footer.plot_lines):
            elements.append(
                _svg_text(
                    line,
                    x=content_left,
                    top=footer.top + line_index * _line_height(footer.plot_font),
                    font=footer.plot_font,
                    weight=400,
                )
            )
    if credits_text is not None and footer.credits_font is not None:
        elements.append(
            _svg_text(
                credits_text.upper(),
                x=content_left,
                top=footer.credits_top,
                font=footer.credits_font,
                weight=400,
            )
        )

    if subtitle_text is not None and footer.subtitle_font is not None:
        elements.append(
            _svg_text(
                subtitle_text,
                x=content_left,
                top=footer.subtitle_top,
                font=footer.subtitle_font,
                weight=400,
            )
        )

    font_data = base64.b64encode(_FONT_PATH.read_bytes()).decode("ascii")
    font_license = escape(_FONT_LICENSE_PATH.read_text(encoding="utf-8"))
    physical_width = width / dpi * 25.4
    physical_height = height / dpi * 25.4
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{physical_width:.4f}mm" height="{physical_height:.4f}mm" '
        f'viewBox="0 0 {width} {height}" role="img">'
        f"<title>{escape(_normalize_text(title))}</title>"
        f"<metadata>{font_license}</metadata>"
        "<defs><style>"
        "@font-face{font-family:Montserrat;font-style:normal;"
        "font-weight:100 900;"
        f"src:url(data:font/ttf;base64,{font_data}) format('truetype');"
        "}"
        "</style></defs>"
        + "".join(elements)
        + "</svg>"
    )


def save_svg(
    svg: str,
    output_path: str | Path,
    *,
    overwrite: bool = False,
) -> None:
    """Save a rendered poster as SVG."""
    if not isinstance(svg, str) or not svg.startswith("<svg "):
        raise ValueError("svg must be a rendered poster document")
    path = Path(output_path)
    if path.suffix.lower() != ".svg":
        raise ValueError("poster output path must have a .svg extension")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {path.parent}")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {path}")
    path.write_text(svg, encoding="utf-8")


def _svg_color(color: tuple[int, int, int]) -> str:
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def _svg_text(
    text: str,
    *,
    x: int,
    top: int,
    font: ImageFont.FreeTypeFont,
    weight: int,
    anchor: str = "start",
) -> str:
    baseline = top + font.getmetrics()[0]
    return (
        f'<text x="{x}" y="{baseline}" text-anchor="{anchor}" '
        f'font-family="Montserrat" font-size="{font.size}" '
        f'font-weight="{weight}" fill="{_svg_color(INK)}">'
        f"{escape(text)}</text>"
    )


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
    if width <= height:
        raise ValueError("poster dimensions must be landscape (width greater than height)")


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


def _metadata_column_layout(
    fields: tuple[tuple[str, str], ...],
    *,
    content_left: int,
    content_width: int,
    gap: int,
    label_font: ImageFont.FreeTypeFont,
    value_font: ImageFont.FreeTypeFont,
) -> list[tuple[int, int]]:
    available_width = content_width - gap * (len(fields) - 1)
    minimum_widths = [math.ceil(label_font.getlength(label)) for label, _ in fields]
    preferred_widths = [
        max(minimum, math.ceil(value_font.getlength(value)))
        for minimum, (_, value) in zip(minimum_widths, fields)
    ]
    flexible_widths = [
        preferred - minimum
        for preferred, minimum in zip(preferred_widths, minimum_widths)
    ]
    flexible_total = sum(flexible_widths)
    remaining_width = max(0, available_width - sum(minimum_widths))
    scale = min(1.0, remaining_width / flexible_total) if flexible_total else 0.0
    widths = [
        minimum + math.floor(flexible * scale)
        for minimum, flexible in zip(minimum_widths, flexible_widths)
    ]
    leftover = available_width - sum(widths)
    if scale < 1 and leftover:
        for index, flexible in sorted(
            enumerate(flexible_widths),
            key=lambda item: item[1] * scale - math.floor(item[1] * scale),
            reverse=True,
        )[:leftover]:
            widths[index] += 1

    columns = []
    column_x = content_left
    for column_width in widths:
        columns.append((column_x, column_width))
        column_x += column_width + gap
    return columns


def _layout_footer(
    plot: str | None,
    credits: str | None,
    subtitle: str | None,
    *,
    width: int,
    height: int,
    content_width: int,
    barcode_top: int,
) -> _FooterLayout:
    plot_lines: list[str] = []
    plot_font: ImageFont.FreeTypeFont | None = None
    if plot is not None:
        plot_font, plot_lines = _fit_wrapped_text(
            plot,
            max_width=content_width,
            max_lines=2,
            initial_size=max(9, round(width * 0.012)),
            minimum_size=max(8, round(width * 0.008)),
            weight=400,
        )

    credits_font = (
        _fit_single_line(
            credits,
            max_width=round(content_width * 0.58),
            initial_size=max(9, round(width * 0.013)),
            minimum_size=max(8, round(width * 0.009)),
            weight=400,
        )
        if credits is not None
        else None
    )
    subtitle_font = (
        _fit_single_line(
            subtitle,
            max_width=round(content_width * 0.58),
            initial_size=max(9, round(width * 0.013)),
            minimum_size=max(8, round(width * 0.009)),
            weight=400,
        )
        if subtitle is not None
        else None
    )

    top = round(height * 0.91)
    gap = round(height * 0.006)
    plot_height = len(plot_lines) * _line_height(plot_font) if plot_font else 0
    credits_top = top + plot_height + (gap if plot_font else 0)
    if credits_font is not None:
        subtitle_top = credits_top + _line_height(credits_font) + gap
    elif plot_font is not None:
        subtitle_top = credits_top
    else:
        subtitle_top = top + round(height * 0.021)

    footer_bottom = top
    if plot_font is not None:
        footer_bottom = max(footer_bottom, top + plot_height)
    if credits_font is not None:
        footer_bottom = max(footer_bottom, credits_top + _line_height(credits_font))
    if subtitle_font is not None:
        footer_bottom = max(footer_bottom, subtitle_top + _line_height(subtitle_font))
    shift = max(0, footer_bottom - round(height * 0.98))
    barcode_bottom = round(height * 0.895) - shift
    if barcode_top >= barcode_bottom:
        raise ValueError("title and metadata leave no room for the barcode")

    return _FooterLayout(
        top=top - shift,
        barcode_top=barcode_top,
        barcode_bottom=barcode_bottom,
        plot_lines=plot_lines,
        plot_font=plot_font,
        credits_top=credits_top - shift,
        credits_font=credits_font,
        subtitle_top=subtitle_top - shift,
        subtitle_font=subtitle_font,
    )


def _layout_metadata_fields(
    fields: tuple[tuple[str, str], ...],
    *,
    content_left: int,
    content_width: int,
    gap: int,
    metadata_top: int,
    width: int,
    height: int,
) -> tuple[list[_MetadataFieldLayout], int]:
    label_font = _font(max(9, round(width * 0.010)), weight=700)
    value_font = _font(max(9, round(width * 0.010)), weight=400)
    columns = _metadata_column_layout(
        fields,
        content_left=content_left,
        content_width=content_width,
        gap=gap,
        label_font=label_font,
        value_font=value_font,
    )
    layout = []
    metadata_bottom = metadata_top + _line_height(label_font)
    value_top = metadata_top + round(height * 0.018)
    for (label, value), (column_x, column_width) in zip(fields, columns):
        body_font, lines = _fit_wrapped_text(
            value,
            max_width=column_width,
            max_lines=4,
            initial_size=value_font.size,
            minimum_size=max(8, round(width * 0.008)),
            weight=400,
        )
        layout.append(
            _MetadataFieldLayout(
                label=label,
                x=column_x,
                label_font=label_font,
                value_font=body_font,
                value_top=value_top,
                lines=lines,
            )
        )
        metadata_bottom = max(
            metadata_bottom,
            value_top + len(lines) * _line_height(body_font),
        )
    return layout, metadata_bottom


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
