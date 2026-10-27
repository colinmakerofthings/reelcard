"""Video metadata probing and bounded-memory frame sampling."""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from reelcard.errors import (
    FrameExtractionError,
    InvalidVideoError,
    VideoToolError,
)

DEFAULT_THUMBNAIL_SIZE = 64
MAX_STRIPES = 10_000
DEFAULT_PROBE_TIMEOUT = 30.0
DEFAULT_FRAME_TIMEOUT = 60.0


@dataclass(frozen=True)
class VideoMetadata:
    """Metadata needed to sample a video."""

    duration: float
    width: int
    height: int
    stream_index: int


@dataclass(frozen=True)
class VideoFrame:
    """A sampled RGB thumbnail and its timestamp in the source video."""

    timestamp: float
    width: int
    height: int
    rgb: bytes


def sample_timestamps(duration: float, count: int) -> tuple[float, ...]:
    """Return evenly spaced interval midpoints in chronological order."""
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        raise ValueError("duration must be a positive finite number")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be a positive finite number")
    _validate_stripe_count(count)
    return tuple(duration * (index + 0.5) / count for index in range(count))


def probe_video(
    input_path: str | Path,
    *,
    ffprobe: str = "ffprobe",
    timeout: float = DEFAULT_PROBE_TIMEOUT,
) -> VideoMetadata:
    """Read duration and dimensions for the first non-attached video stream."""
    path = Path(input_path)
    if not path.is_file():
        raise InvalidVideoError(f"Input video does not exist or is not a file: {path}")

    command = [
        ffprobe,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise VideoToolError(
            f"FFprobe was not found ({ffprobe!r}); install FFmpeg and ensure "
            "ffprobe is on PATH."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoToolError(f"FFprobe timed out while reading {path}.") from exc
    except subprocess.CalledProcessError as exc:
        detail = _stderr_detail(exc.stderr)
        raise InvalidVideoError(
            f"FFprobe could not read {path}" + (f": {detail}" if detail else ".")
        ) from exc

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        raise VideoToolError(f"FFprobe returned invalid metadata for {path}.") from exc

    if not isinstance(data, dict):
        raise VideoToolError(f"FFprobe returned invalid metadata for {path}.")
    streams = data.get("streams")
    if not isinstance(streams, list):
        raise VideoToolError(f"FFprobe returned no stream metadata for {path}.")
    video_stream = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict)
            and stream.get("codec_type") == "video"
            and not _is_attached_picture(stream)
        ),
        None,
    )
    if video_stream is None:
        raise InvalidVideoError(f"No video stream was found in {path}.")

    width = video_stream.get("width")
    height = video_stream.get("height")
    stream_index = video_stream.get("index")
    if (
        not isinstance(width, int)
        or isinstance(width, bool)
        or width <= 0
        or not isinstance(height, int)
        or isinstance(height, bool)
        or height <= 0
    ):
        raise InvalidVideoError(f"Video stream in {path} has invalid dimensions.")
    if (
        not isinstance(stream_index, int)
        or isinstance(stream_index, bool)
        or stream_index < 0
    ):
        raise VideoToolError(f"FFprobe returned an invalid video stream index for {path}.")

    format_info = data.get("format")
    format_duration = (
        format_info.get("duration") if isinstance(format_info, dict) else None
    )
    duration = _parse_duration(format_duration) or _parse_duration(
        video_stream.get("duration")
    )
    if duration is None:
        raise InvalidVideoError(f"Could not determine a valid video duration for {path}.")

    return VideoMetadata(
        duration=duration,
        width=width,
        height=height,
        stream_index=stream_index,
    )


def iter_video_frames(
    input_path: str | Path,
    count: int,
    *,
    metadata: VideoMetadata | None = None,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
    thumbnail_size: int = DEFAULT_THUMBNAIL_SIZE,
    probe_timeout: float = DEFAULT_PROBE_TIMEOUT,
    frame_timeout: float = DEFAULT_FRAME_TIMEOUT,
) -> Iterator[VideoFrame]:
    """Yield fixed-size RGB thumbnails sampled at interval midpoints."""
    _validate_stripe_count(count)
    if (
        isinstance(thumbnail_size, bool)
        or not isinstance(thumbnail_size, int)
        or thumbnail_size <= 0
    ):
        raise ValueError("thumbnail_size must be a positive integer")

    path = Path(input_path)
    if not path.is_file():
        raise InvalidVideoError(f"Input video does not exist or is not a file: {path}")
    video = metadata or probe_video(path, ffprobe=ffprobe, timeout=probe_timeout)
    timestamps = sample_timestamps(video.duration, count)
    expected_bytes = thumbnail_size * thumbnail_size * 3
    fps = count / video.duration
    start_time = timestamps[0]
    command = [
        ffmpeg,
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        f"0:{video.stream_index}",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        (
            f"setpts=PTS-{start_time:.9f}/TB,"
            f"fps=fps={fps:.12f}:start_time=0:round=near:eof_action=pass,"
            f"scale={thumbnail_size}:{thumbnail_size}"
        ),
        "-frames:v",
        str(count),
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "pipe:1",
    ]
    with tempfile.TemporaryFile() as output:
        try:
            subprocess.run(
                command,
                check=True,
                stdout=output,
                stderr=subprocess.PIPE,
                timeout=frame_timeout * count,
            )
        except FileNotFoundError as exc:
            raise VideoToolError(
                f"FFmpeg was not found ({ffmpeg!r}); install FFmpeg and ensure "
                "ffmpeg is on PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise FrameExtractionError(
                f"FFmpeg timed out extracting {count} samples from {path}."
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = _stderr_detail(exc.stderr)
            raise FrameExtractionError(
                f"FFmpeg could not extract {count} samples from {path}"
                + (f": {detail}" if detail else ".")
            ) from exc

        output.seek(0, 2)
        output_size = output.tell()
        frame_count, remainder = divmod(output_size, expected_bytes)
        if remainder or frame_count != count:
            index = min(frame_count + 1, count)
            timestamp = timestamps[index - 1]
            raise FrameExtractionError(
                f"FFmpeg returned {output_size} bytes while extracting "
                f"sample {index}/{count} at {timestamp:.3f}s; expected "
                f"{expected_bytes} bytes per frame and {count} frames."
            )

        output.seek(0)
        for timestamp in timestamps:
            yield VideoFrame(
                timestamp=timestamp,
                width=thumbnail_size,
                height=thumbnail_size,
                rgb=output.read(expected_bytes),
            )


def _validate_stripe_count(count: int) -> None:
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ValueError("stripe count must be a positive integer")
    if count > MAX_STRIPES:
        raise ValueError(f"stripe count must not exceed {MAX_STRIPES}")


def _is_attached_picture(stream: dict[str, object]) -> bool:
    disposition = stream.get("disposition")
    return isinstance(disposition, dict) and disposition.get("attached_pic") == 1


def _parse_duration(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        duration = float(value)
    except ValueError:
        return None
    return duration if math.isfinite(duration) and duration > 0 else None


def _stderr_detail(stderr: str | bytes | None) -> str:
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    if not isinstance(stderr, str):
        return ""
    return stderr.strip()[-1000:]
