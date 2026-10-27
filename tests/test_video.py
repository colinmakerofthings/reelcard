"""Tests for metadata probing and frame sampling."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from reelcard.errors import (
    FrameExtractionError,
    InvalidVideoError,
    VideoToolError,
)
from reelcard.video import (
    MAX_STRIPES,
    VideoMetadata,
    iter_video_frames,
    probe_video,
    sample_timestamps,
)


def _probe_payload(
    *,
    streams: list[dict[str, Any]] | None = None,
    duration: str = "12.5",
) -> str:
    return json.dumps(
        {
            "format": {"duration": duration},
            "streams": streams
            or [
                {
                    "codec_type": "video",
                    "index": 0,
                    "width": 1920,
                    "height": 1080,
                    "duration": duration,
                }
            ],
        }
    )


def test_sample_timestamps_are_interval_midpoints() -> None:
    assert sample_timestamps(12.0, 4) == (1.5, 4.5, 7.5, 10.5)


@pytest.mark.parametrize("duration", [0, -1, float("inf"), float("nan"), True])
def test_sample_timestamps_reject_invalid_duration(duration: float) -> None:
    with pytest.raises(ValueError, match="duration"):
        sample_timestamps(duration, 2)


@pytest.mark.parametrize("count", [0, -1, True, 1.5, MAX_STRIPES + 1])
def test_sample_timestamps_reject_invalid_count(count: int) -> None:
    with pytest.raises(ValueError, match="stripe count"):
        sample_timestamps(10.0, count)


def test_probe_video_returns_metadata_and_ignores_attached_picture(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "movie.mkv"
    video_path.touch()
    payload = _probe_payload(
        streams=[
            {
                "codec_type": "video",
                "index": 0,
                "width": 600,
                "height": 600,
                "disposition": {"attached_pic": 1},
            },
            {
                "codec_type": "video",
                "index": 1,
                "width": 1920,
                "height": 1080,
                "disposition": {"attached_pic": 0},
            },
        ]
    )

    with patch(
        "reelcard.video.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, payload, ""),
    ) as run:
        metadata = probe_video(video_path)

    assert metadata == VideoMetadata(12.5, 1920, 1080, 1)
    assert run.call_args.args[0][-1] == str(video_path)
    assert run.call_args.kwargs["check"] is True
    assert run.call_args.kwargs["timeout"] > 0


def test_probe_video_uses_stream_duration_when_format_duration_is_unavailable(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "movie.mkv"
    video_path.touch()
    payload = json.dumps(
        {
            "format": {"duration": "N/A"},
            "streams": [
                {
                    "codec_type": "video",
                    "index": 0,
                    "width": 1920,
                    "height": 1080,
                    "duration": "8.25",
                }
            ],
        }
    )

    with patch(
        "reelcard.video.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, payload, ""),
    ):
        metadata = probe_video(video_path)

    assert metadata.duration == 8.25


def test_probe_video_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidVideoError, match="does not exist"):
        probe_video(tmp_path / "missing.mp4")


def test_probe_video_rejects_input_without_video_stream(tmp_path: Path) -> None:
    video_path = tmp_path / "audio.m4a"
    video_path.touch()
    payload = _probe_payload(streams=[{"codec_type": "audio", "index": 0}])

    with (
        patch(
            "reelcard.video.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, payload, ""),
        ),
        pytest.raises(InvalidVideoError, match="No video stream"),
    ):
        probe_video(video_path)


def test_probe_video_reports_missing_ffprobe(tmp_path: Path) -> None:
    video_path = tmp_path / "movie.mkv"
    video_path.touch()
    with (
        patch(
            "reelcard.video.subprocess.run",
            side_effect=FileNotFoundError,
        ),
        pytest.raises(VideoToolError, match="FFprobe was not found"),
    ):
        probe_video(video_path)


def test_probe_video_surfaces_ffprobe_diagnostic(tmp_path: Path) -> None:
    video_path = tmp_path / "broken.mkv"
    video_path.touch()
    failure = subprocess.CalledProcessError(1, "ffprobe", stderr="invalid data")

    with (
        patch("reelcard.video.subprocess.run", side_effect=failure),
        pytest.raises(InvalidVideoError, match="invalid data"),
    ):
        probe_video(video_path)


def test_iter_video_frames_extracts_only_small_rgb_thumbnails(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "movie.mkv"
    video_path.touch()
    output = bytes(range(12))
    metadata = VideoMetadata(8.0, 1920, 1080, 2)

    with patch(
        "reelcard.video.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, output, b""),
    ) as run:
        frames = list(
            iter_video_frames(
                video_path,
                2,
                metadata=metadata,
                thumbnail_size=2,
            )
        )

    assert [frame.timestamp for frame in frames] == [2.0, 6.0]
    assert all(frame.rgb == output for frame in frames)
    assert all((frame.width, frame.height) == (2, 2) for frame in frames)
    assert run.call_count == 2
    command = run.call_args_list[0].args[0]
    assert command[command.index("-map") + 1] == "0:2"
    assert command[-1] == "pipe:1"


def test_iter_video_frames_fails_if_ffmpeg_returns_no_frame(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "movie.mkv"
    video_path.touch()
    metadata = VideoMetadata(8.0, 1920, 1080, 0)

    with (
        patch(
            "reelcard.video.subprocess.run",
            return_value=subprocess.CompletedProcess([], 0, b"", b""),
        ),
        pytest.raises(FrameExtractionError, match="expected 12288"),
    ):
        next(iter_video_frames(video_path, 1, metadata=metadata))


def test_iter_video_frames_reports_decode_error_with_sample_context(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "movie.mkv"
    video_path.touch()
    metadata = VideoMetadata(8.0, 1920, 1080, 0)
    failure = subprocess.CalledProcessError(1, "ffmpeg", stderr=b"decode failed")

    with (
        patch("reelcard.video.subprocess.run", side_effect=failure),
        pytest.raises(FrameExtractionError, match="sample 1/1 at 4.000s.*decode failed"),
    ):
        next(iter_video_frames(video_path, 1, metadata=metadata))


def test_iter_video_frames_checks_stripe_limit_before_running_ffmpeg(
    tmp_path: Path,
) -> None:
    video_path = tmp_path / "movie.mkv"
    video_path.touch()
    with (
        patch("reelcard.video.subprocess.run") as run,
        pytest.raises(ValueError, match="must not exceed"),
    ):
        list(iter_video_frames(video_path, MAX_STRIPES + 1))
    run.assert_not_called()


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required for the integration test",
)
def test_probe_and_extract_from_synthetic_video(tmp_path: Path) -> None:
    video_path = tmp_path / "synthetic.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=96x64:rate=2:duration=2",
            "-c:v",
            "ffv1",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )

    metadata = probe_video(video_path)
    frames = list(iter_video_frames(video_path, 2, metadata=metadata))

    assert metadata.width == 96
    assert metadata.height == 64
    assert len(frames) == 2
    assert [frame.timestamp for frame in frames] == [0.5, 1.5]
    assert all(len(frame.rgb) == 64 * 64 * 3 for frame in frames)


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required for the integration test",
)
def test_frame_sampling_does_not_add_black_bars_to_wide_video(
    tmp_path: Path,
) -> None:
    from reelcard.colors import representative_color

    video_path = tmp_path / "wide-red.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=96x64:r=2:d=2",
            "-c:v",
            "ffv1",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )

    metadata = probe_video(video_path)
    frame = next(iter_video_frames(video_path, 1, metadata=metadata))

    color = representative_color(frame)
    assert color[0] > 245
    assert color[1] < 5
    assert color[2] < 5
