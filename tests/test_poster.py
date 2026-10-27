"""Tests for the postcard poster renderer."""

from __future__ import annotations

import base64
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from reelcard import poster as poster_module
from reelcard.poster import (
    DEFAULT_DPI,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    PAPER,
    render_poster,
    render_svg,
    save_poster,
    save_svg,
)


def _barcode() -> Image.Image:
    return Image.new("RGB", (4, 2), "red")


def test_render_poster_has_default_postcard_dimensions_and_paper_background() -> None:
    poster = render_poster(
        _barcode(),
        title="My Film",
        runtime_seconds=5_520,
    )

    assert poster.size == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    assert DEFAULT_WIDTH > DEFAULT_HEIGHT
    assert poster.mode == "RGB"
    assert poster.getpixel((0, 0)) == PAPER
    assert poster.getpixel((round(DEFAULT_WIDTH * 0.035), round(DEFAULT_HEIGHT * 0.065))) == PAPER


def test_render_poster_scales_to_custom_landscape_dimensions() -> None:
    poster = render_poster(
        _barcode(),
        title="My Film",
        runtime_seconds=5_520,
        width=874,
        height=620,
    )

    assert poster.size == (874, 620)


def test_default_postcard_dimensions_are_landscape() -> None:
    assert DEFAULT_WIDTH == 1748
    assert DEFAULT_HEIGHT == 1240


def test_render_poster_draws_barcode_and_optional_metadata() -> None:
    barcode = Image.new("RGB", (2, 1))
    barcode.putdata([(250, 10, 20), (10, 30, 240)])

    poster = render_poster(
        barcode,
        title="A Film",
        year=1994,
        runtime_seconds=5_520,
        director="A Director",
        subtitle="A thoughtful subtitle",
        credits="Written by Someone",
    )
    left = poster.getpixel((round(DEFAULT_WIDTH * 0.10), round(DEFAULT_HEIGHT * 0.5)))
    right = poster.getpixel(
        (round(DEFAULT_WIDTH * 0.90) - 1, round(DEFAULT_HEIGHT * 0.5))
    )

    assert left == (250, 10, 20)
    assert right == (10, 30, 240)
    assert len(set(poster.getdata())) > 4


def test_render_poster_fills_missing_metadata_with_clear_placeholders() -> None:
    poster = render_poster(
        _barcode(),
        title="Film",
        runtime_seconds=60,
    )
    metadata_y = round(DEFAULT_HEIGHT * 0.135)
    column_width = round(DEFAULT_WIDTH * 0.91 / 4)
    for index in range(4):
        region = poster.crop(
            (
                round(DEFAULT_WIDTH * 0.045) + index * column_width,
                metadata_y,
                round(DEFAULT_WIDTH * 0.045) + (index + 1) * column_width,
                metadata_y + 55,
            )
        )
        assert len(set(region.getdata())) > 1


def test_render_poster_wraps_long_titles_and_normalizes_whitespace() -> None:
    poster = render_poster(
        _barcode(),
        title="  The   Long   and   Winding   Film  ",
        runtime_seconds=2_400,
        year=2024,
    )

    assert poster.size == (DEFAULT_WIDTH, DEFAULT_HEIGHT)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"title": " "}, "title"),
        ({"runtime_seconds": 0}, "runtime_seconds"),
        ({"year": 0}, "year"),
        ({"width": 800, "height": 900}, "landscape"),
        ({"width": 200, "height": 300}, "dimensions"),
        ({"dpi": 0}, "dpi"),
        ({"dpi": float("nan")}, "dpi"),
    ],
)
def test_render_poster_rejects_invalid_options(
    kwargs: dict[str, object],
    message: str,
) -> None:
    options: dict[str, object] = {
        "title": "Film",
        "runtime_seconds": 60,
    }
    options.update(kwargs)
    with pytest.raises(ValueError, match=message):
        render_poster(_barcode(), **options)  # type: ignore[arg-type]


def test_render_poster_rejects_too_long_unbreakable_title() -> None:
    with pytest.raises(ValueError, match="too long"):
        render_poster(
            _barcode(),
            title="W" * 1000,
            runtime_seconds=60,
        )


def test_save_poster_writes_png_dimensions_and_dpi_metadata(tmp_path: Path) -> None:
    path = tmp_path / "film.png"
    poster = render_poster(
        _barcode(),
        title="Film",
        runtime_seconds=60,
        width=874,
        height=620,
    )

    save_poster(poster, path, dpi=DEFAULT_DPI)

    with Image.open(path) as saved:
        assert saved.format == "PNG"
        assert saved.size == (874, 620)
        assert saved.info["dpi"] == pytest.approx((300, 300), abs=0.1)


def test_save_poster_refuses_to_overwrite_by_default(tmp_path: Path) -> None:
    path = tmp_path / "existing.png"
    path.write_bytes(b"preserve this")
    poster = render_poster(_barcode(), title="Film", runtime_seconds=60)

    with pytest.raises(FileExistsError, match="already exists"):
        save_poster(poster, path)

    assert path.read_bytes() == b"preserve this"


def test_save_poster_can_explicitly_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "existing.png"
    path.write_bytes(b"old image")
    poster = render_poster(_barcode(), title="Film", runtime_seconds=60)

    save_poster(poster, path, overwrite=True)

    with Image.open(path) as saved:
        assert saved.format == "PNG"


def test_save_poster_validates_extension_and_directory(tmp_path: Path) -> None:
    poster = render_poster(_barcode(), title="Film", runtime_seconds=60)

    with pytest.raises(ValueError, match="\\.png"):
        save_poster(poster, tmp_path / "film.jpg")
    with pytest.raises(FileNotFoundError, match="directory"):
        save_poster(poster, tmp_path / "missing" / "film.png")


def test_render_svg_embeds_font_and_barcode_and_preserves_layout() -> None:
    barcode = Image.new("RGB", (2, 1))
    barcode.putdata([(255, 0, 0), (0, 0, 255)])
    svg = render_svg(
        barcode,
        title="A Film & a Story",
        year=1994,
        runtime_seconds=5_520,
        director="A Director",
        subtitle="A thoughtful subtitle",
        credits="Written by Someone",
        width=874,
        height=620,
    )
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    texts = [element.text for element in root.findall(".//svg:text", namespace)]
    barcode_rects = [
        element
        for element in root.findall(".//svg:rect", namespace)
        if element.attrib.get("y") == str(round(620 * 0.225))
    ]
    style = root.find(".//svg:style", namespace)
    metadata = root.find(".//svg:metadata", namespace)
    font_match = re.search(r"base64,([^)]*)", style.text if style is not None else "")

    assert root.attrib["viewBox"] == "0 0 874 620"
    assert root.attrib["width"] == "73.9987mm"
    assert "A FILM & A STORY" in texts
    assert "1994" in texts
    assert [element.attrib["fill"] for element in barcode_rects] == [
        "#ff0000",
        "#0000ff",
    ]
    assert sum(int(element.attrib["width"]) for element in barcode_rects) == (
        round(874 * 0.955) - round(874 * 0.045)
    )
    assert all(
        element.attrib["height"]
        == str(round(620 * 0.895) - round(620 * 0.225))
        for element in barcode_rects
    )
    assert root.find(".//svg:image", namespace) is None
    assert style is not None and "font-family:Montserrat" in style.text
    assert font_match is not None
    assert base64.b64decode(font_match.group(1)) == poster_module._FONT_PATH.read_bytes()
    assert metadata is not None and "SIL OPEN FONT LICENSE" in metadata.text


def test_save_svg_writes_utf8_and_refuses_to_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "film.svg"
    svg = render_svg(_barcode(), title="Film", runtime_seconds=60, width=874, height=620)

    save_svg(svg, path)

    assert path.read_text(encoding="utf-8") == svg
    with pytest.raises(FileExistsError, match="already exists"):
        save_svg(svg, path)


def test_save_svg_validates_extension_and_directory(tmp_path: Path) -> None:
    svg = render_svg(_barcode(), title="Film", runtime_seconds=60, width=874, height=620)

    with pytest.raises(ValueError, match="\\.svg"):
        save_svg(svg, tmp_path / "film.png")
    with pytest.raises(FileNotFoundError, match="directory"):
        save_svg(svg, tmp_path / "missing" / "film.svg")
