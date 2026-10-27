"""Representative frame colors and plain chronological barcode images."""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
from PIL import Image

from reelcard.video import VideoFrame

DEFAULT_TRIM_FRACTION = 0.1
DEFAULT_BARCODE_HEIGHT = 64
BRIGHT_PIXEL_FRACTION = 0.75


def representative_color(
    frame: VideoFrame,
    *,
    trim_fraction: float = DEFAULT_TRIM_FRACTION,
) -> tuple[int, int, int]:
    """Calculate a robust color from the brighter three-quarters of a frame.

    Keeping darker pixels out of the color estimate reduces shadow bias. A
    trimmed channel mean over the retained pixels limits the effect of
    highlights and isolated color noise.
    """
    if not isinstance(frame, VideoFrame):
        raise TypeError("frame must be a VideoFrame")
    if (
        isinstance(frame.width, bool)
        or not isinstance(frame.width, int)
        or frame.width <= 0
        or isinstance(frame.height, bool)
        or not isinstance(frame.height, int)
        or frame.height <= 0
    ):
        raise ValueError("frame dimensions must be positive integers")
    if len(frame.rgb) != frame.width * frame.height * 3:
        raise ValueError("frame RGB data length does not match its dimensions")
    if (
        isinstance(trim_fraction, bool)
        or not isinstance(trim_fraction, (int, float))
        or not math.isfinite(trim_fraction)
        or not 0 <= trim_fraction < 0.5
    ):
        raise ValueError("trim_fraction must be finite and in the range [0, 0.5)")

    pixels = np.frombuffer(frame.rgb, dtype=np.uint8).reshape(-1, 3)
    keep_count = max(1, math.ceil(len(pixels) * BRIGHT_PIXEL_FRACTION))
    brightness = pixels.max(axis=1)
    brightest_indices = np.argsort(brightness, kind="stable")[-keep_count:]
    members = pixels[brightest_indices]
    trim_count = int(len(members) * trim_fraction)
    sorted_channels = np.sort(members, axis=0)
    retained = sorted_channels[trim_count : len(members) - trim_count or None]
    means = retained.mean(axis=0, dtype=np.float64)
    rounded = np.floor(means + 0.5).astype(np.uint8)
    return int(rounded[0]), int(rounded[1]), int(rounded[2])


def make_barcode(
    frames: Iterable[VideoFrame],
    *,
    height: int = DEFAULT_BARCODE_HEIGHT,
) -> Image.Image:
    """Render sampled frames as one vertical stripe each, in input order."""
    if isinstance(height, bool) or not isinstance(height, int) or height <= 0:
        raise ValueError("barcode height must be a positive integer")

    colors: list[tuple[int, int, int]] = []
    previous_timestamp = -math.inf
    for frame in frames:
        if (
            isinstance(frame.timestamp, bool)
            or not isinstance(frame.timestamp, (int, float))
            or not math.isfinite(frame.timestamp)
            or frame.timestamp < 0
        ):
            raise ValueError("frame timestamps must be finite and non-negative")
        if frame.timestamp < previous_timestamp:
            raise ValueError("frames must be supplied in chronological order")
        previous_timestamp = frame.timestamp
        colors.append(representative_color(frame))

    if not colors:
        raise ValueError("at least one frame is required to make a barcode")

    row = bytes(channel for color in colors for channel in color)
    return Image.frombytes("RGB", (len(colors), height), row * height)
