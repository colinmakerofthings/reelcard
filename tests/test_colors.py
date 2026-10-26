"""Tests for representative colors and barcode rendering."""

from __future__ import annotations

import pytest
from PIL import Image

from reelcard.colors import make_barcode, representative_color
from reelcard.errors import FrameExtractionError
from reelcard.video import VideoFrame


def _frame(
    color: tuple[int, int, int],
    *,
    timestamp: float = 0.0,
    pixels: list[tuple[int, int, int]] | None = None,
) -> VideoFrame:
    pixel_values = pixels if pixels is not None else [color]
    rgb = bytes(channel for pixel in pixel_values for channel in pixel)
    return VideoFrame(timestamp, len(pixel_values), 1, rgb)


def test_representative_color_returns_uniform_frame_color() -> None:
    frame = _frame((27, 128, 241), pixels=[(27, 128, 241)] * 25)

    assert representative_color(frame) == (27, 128, 241)


def test_representative_color_trims_isolated_extreme_pixels() -> None:
    pixels = [(100, 120, 140)] * 98 + [(0, 0, 0), (255, 255, 255)]

    assert representative_color(_frame((0, 0, 0), pixels=pixels)) == (
        100,
        120,
        140,
    )


def test_representative_color_rounds_channel_means_to_nearest_integer() -> None:
    pixels = [(0, 10, 20), (1, 11, 21)]

    assert representative_color(_frame((0, 0, 0), pixels=pixels)) == (1, 11, 21)


@pytest.mark.parametrize(
    ("frame", "message"),
    [
        (VideoFrame(0.0, 0, 1, b""), "dimensions"),
        (VideoFrame(0.0, 2, 1, b"\x00\x00\x00"), "data length"),
    ],
)
def test_representative_color_rejects_invalid_frames(
    frame: VideoFrame,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        representative_color(frame)


@pytest.mark.parametrize("trim_fraction", [-0.1, 0.5, float("nan"), float("inf")])
def test_representative_color_rejects_invalid_trim_fraction(
    trim_fraction: float,
) -> None:
    with pytest.raises(ValueError, match="trim_fraction"):
        representative_color(_frame((1, 2, 3)), trim_fraction=trim_fraction)


def test_make_barcode_preserves_frame_order_in_vertical_stripes() -> None:
    frames = [
        _frame((255, 0, 0), timestamp=1.0),
        _frame((0, 255, 0), timestamp=2.0),
        _frame((0, 0, 255), timestamp=3.0),
    ]

    barcode = make_barcode(frames, height=4)

    assert barcode.size == (3, 4)
    assert list(barcode.getdata()) == [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
    ] * 4
    assert barcode.getpixel((0, 3)) == (255, 0, 0)
    assert barcode.getpixel((2, 0)) == (0, 0, 255)


def test_make_barcode_rejects_empty_frames() -> None:
    with pytest.raises(ValueError, match="at least one frame"):
        make_barcode([])


def test_make_barcode_rejects_out_of_order_frames() -> None:
    frames = [
        _frame((1, 2, 3), timestamp=2.0),
        _frame((4, 5, 6), timestamp=1.0),
    ]

    with pytest.raises(ValueError, match="chronological order"):
        make_barcode(frames)


def test_make_barcode_propagates_frame_extraction_failures() -> None:
    def failed_frames():
        yield _frame((1, 2, 3))
        raise FrameExtractionError("decode failed")

    with pytest.raises(FrameExtractionError, match="decode failed"):
        make_barcode(failed_frames())


@pytest.mark.parametrize("height", [0, -1, True, 1.5])
def test_make_barcode_rejects_invalid_height(height: int) -> None:
    with pytest.raises(ValueError, match="barcode height"):
        make_barcode([_frame((1, 2, 3))], height=height)


def test_make_barcode_is_deterministic() -> None:
    frames = [
        _frame((12, 34, 56), timestamp=1.0),
        _frame((78, 90, 123), timestamp=2.0),
    ]

    first = make_barcode(frames, height=8)
    second = make_barcode(frames, height=8)

    assert isinstance(first, Image.Image)
    assert first.tobytes() == second.tobytes()
