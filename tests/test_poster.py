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
    fields = (
        ("DIRECTED BY", "NOT PROVIDED"),
        ("WRITTEN BY", "NOT PROVIDED"),
        ("STARRING", "NOT PROVIDED"),
        ("RUNTIME", "1 MIN"),
    )
    label_font = poster_module._font(max(9, round(DEFAULT_WIDTH * 0.010)), weight=700)
    value_font = poster_module._font(max(9, round(DEFAULT_WIDTH * 0.010)), weight=400)
    columns = poster_module._metadata_column_layout(
        fields,
        content_left=round(DEFAULT_WIDTH * 0.045),
        content_width=round(DEFAULT_WIDTH * 0.955) - round(DEFAULT_WIDTH * 0.045),
        gap=round(DEFAULT_WIDTH * 0.02),
        label_font=label_font,
        value_font=value_font,
    )
    for column_x, column_width in columns:
        region = poster.crop(
            (
                column_x,
                metadata_y,
                column_x + column_width,
                metadata_y + 55,
            )
        )
        assert len(set(region.getdata())) > 1


def test_render_svg_sizes_metadata_columns_to_content() -> None:
    svg = render_svg(
        _barcode(),
        title="Film",
        runtime_seconds=60,
        director="A Director",
        writer="A considerably longer writer credit",
        starring="Lead Cast",
        runtime="122 min",
        width=874,
        height=620,
    )
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    labels = {
        element.text: int(element.attrib["x"])
        for element in root.findall(".//svg:text", namespace)
        if element.text in {"DIRECTED BY", "WRITTEN BY", "STARRING", "RUNTIME"}
    }
    positions = [
        labels[label]
        for label in ("DIRECTED BY", "WRITTEN BY", "STARRING", "RUNTIME")
    ]
    gaps = [right - left for left, right in zip(positions, positions[1:])]

    assert positions == sorted(positions)
    assert len(set(gaps)) > 1
    assert positions[0] == round(874 * 0.045)
    assert positions[-1] < round(874 * 0.75)


def test_render_svg_moves_metadata_and_barcode_below_wrapped_title() -> None:
    svg = render_svg(
        _barcode(),
        title="Star Wars: Episode V - The Empire Strikes Back",
        year=1980,
        runtime_seconds=7_440,
        director="Irvin Kershner",
        writer="Leigh Brackett, Lawrence Kasdan, George Lucas",
        starring="Mark Hamill, Harrison Ford, Carrie Fisher",
        rating="PG",
    )
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    texts = root.findall(".//svg:text", namespace)
    title_lines = [
        element
        for element in texts
        if int(element.attrib["x"]) == round(DEFAULT_WIDTH * 0.045)
        and int(element.attrib["font-size"]) > round(DEFAULT_WIDTH * 0.02)
    ]
    metadata_labels = [
        element
        for element in texts
        if element.text in {
            "DIRECTED BY",
            "WRITTEN BY",
            "STARRING",
            "RUNTIME",
            "RATED",
            "IMDB RATING",
        }
    ]
    barcode_top = min(
        int(element.attrib["y"])
        for element in root.findall(".//svg:rect", namespace)
        if "y" in element.attrib
    )
    title_bottom = max(int(element.attrib["y"]) for element in title_lines)
    metadata_top = min(int(element.attrib["y"]) for element in metadata_labels)

    assert len(title_lines) == 2
    assert metadata_top > title_bottom
    assert barcode_top > max(
        int(element.attrib["y"])
        for element in texts
        if int(element.attrib["y"]) >= metadata_top
    )


def test_render_svg_uses_consistent_title_font_size_for_wrapped_titles() -> None:
    short_svg = render_svg(
        _barcode(),
        title="Interstellar",
        runtime_seconds=60,
        width=874,
        height=620,
    )
    long_svg = render_svg(
        _barcode(),
        title="Star Wars: Episode V - The Empire Strikes Back",
        runtime_seconds=60,
        width=874,
        height=620,
    )
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    short_root = ET.fromstring(short_svg)
    long_root = ET.fromstring(long_svg)
    short_title = next(
        element
        for element in short_root.findall(".//svg:text", namespace)
        if element.text == "INTERSTELLAR"
    )
    long_titles = [
        element
        for element in long_root.findall(".//svg:text", namespace)
        if element.text in {
            "STAR WARS: EPISODE V - THE",
            "EMPIRE STRIKES BACK",
        }
    ]

    assert len(long_titles) == 2
    assert all(
        element.attrib["font-size"] == short_title.attrib["font-size"]
        for element in long_titles
    )


def test_render_svg_does_not_include_music_credit_section() -> None:
    svg = render_svg(
        _barcode(),
        title="Film",
        runtime_seconds=60,
        runtime="122 min",
        rating="R",
        imdb_rating="8.0/10",
        plot=(
            "Violence and mayhem ensue after a hunter stumbles upon the aftermath "
            "of a drug deal gone wrong and over two million dollars in cash near "
            "the Rio Grande."
        ),
        width=874,
        height=620,
    )
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    text_elements = root.findall(".//svg:text", namespace)
    texts = [element.text for element in text_elements]
    barcode = next(
        element
        for element in root.findall(".//svg:rect", namespace)
        if element.attrib.get("y") == str(round(620 * 0.225))
    )
    barcode_bottom = int(barcode.attrib["y"]) + int(barcode.attrib["height"])

    assert "MUSIC BY" not in texts
    assert "RUNTIME" in texts
    assert "122 min" in texts
    rating_label = next(element for element in text_elements if element.text == "RATED")
    rating_value = next(element for element in text_elements if element.text == "R")
    imdb_rating_label = next(
        element for element in text_elements if element.text == "IMDB RATING"
    )
    imdb_rating_value = next(
        element for element in text_elements if element.text == "8.0/10"
    )
    runtime_label = next(element for element in text_elements if element.text == "RUNTIME")
    runtime_value = next(element for element in text_elements if element.text == "122 min")
    assert rating_label.attrib["y"] == runtime_label.attrib["y"]
    assert rating_value.attrib["y"] == runtime_value.attrib["y"]
    assert rating_label.attrib["x"] == rating_value.attrib["x"]
    assert imdb_rating_label.attrib["y"] == runtime_label.attrib["y"]
    assert imdb_rating_value.attrib["y"] == runtime_value.attrib["y"]
    plot_elements = [
        element
        for element in text_elements
        if int(element.attrib["y"]) >= barcode_bottom
    ]
    assert " ".join(element.text or "" for element in plot_elements) == (
        "Violence and mayhem ensue after a hunter stumbles upon the aftermath "
        "of a drug deal gone wrong and over two million dollars in cash near "
        "the Rio Grande."
    )


def test_plot_and_footer_text_fit_small_landscape_canvas() -> None:
    svg = render_svg(
        _barcode(),
        title="Film",
        runtime_seconds=60,
        plot=(
            "Violence and mayhem ensue after a hunter stumbles upon the aftermath "
            "of a drug deal gone wrong and over two million dollars in cash near "
            "the Rio Grande."
        ),
        credits="Some credits",
        subtitle="A subtitle",
        width=500,
        height=400,
    )
    root = ET.fromstring(svg)
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    footer_text = [
        element
        for element in root.findall(".//svg:text", namespace)
        if int(element.attrib["y"]) >= round(400 * 0.8)
    ]

    assert "SOME CREDITS" in [element.text for element in footer_text]
    assert "A subtitle" in [element.text for element in footer_text]
    assert all(
        int(element.attrib["y"]) + int(element.attrib["font-size"]) <= 400
        for element in footer_text
    )


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
    assert "RUNTIME" in texts
    assert "1H 32M" in texts
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
