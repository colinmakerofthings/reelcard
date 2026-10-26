"""Tests for the postcard poster renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from reelcard.poster import (
    DEFAULT_DPI,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    PAPER,
    render_poster,
    save_poster,
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
    assert poster.mode == "RGB"
    assert poster.getpixel((0, 0)) == PAPER


def test_render_poster_scales_to_custom_portrait_dimensions() -> None:
    poster = render_poster(
        _barcode(),
        title="My Film",
        runtime_seconds=5_520,
        width=620,
        height=874,
    )

    assert poster.size == (620, 874)


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
    left = poster.getpixel((124, round(DEFAULT_HEIGHT * 0.5)))
    right = poster.getpixel((1115, round(DEFAULT_HEIGHT * 0.5)))

    assert left == (250, 10, 20)
    assert right == (10, 30, 240)
    assert len(set(poster.getdata())) > 4


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
        ({"width": 900, "height": 800}, "portrait"),
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
        width=620,
        height=874,
    )

    save_poster(poster, path, dpi=DEFAULT_DPI)

    with Image.open(path) as saved:
        assert saved.format == "PNG"
        assert saved.size == (620, 874)
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
