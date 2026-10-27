"""Tests for the Reelcard command-line interface."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from reelcard.cli import main
from reelcard.poster import DEFAULT_HEIGHT, DEFAULT_WIDTH
from reelcard.video import VideoMetadata


def test_cli_help_lists_supported_options(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])

    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    for option in (
        "--title",
        "--year",
        "--director",
        "--writer",
        "--starring",
        "--music",
        "--subtitle",
        "--credits",
        "--output",
        "--format",
        "--stripes",
        "--color-style",
        "--size",
        "--width",
        "--height",
        "--dpi",
        "--force",
    ):
        assert option in help_text


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["movie.mp4", "--year", "0"], "year must be between"),
        (["movie.mp4", "--stripes", "0"], "positive integer"),
        (["movie.mp4", "--dpi", "nan"], "positive finite number"),
    ],
)
def test_cli_rejects_invalid_argument_values(
    arguments: list[str],
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(arguments)

    assert exit_info.value.code == 2
    assert message in capsys.readouterr().err


def test_cli_requires_both_custom_dimensions_before_processing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "film.mp4"
    input_path.touch()
    with patch("reelcard.cli.probe_video") as probe:
        result = main([str(input_path), "--width", "620"])

    assert result == 2
    assert "--width and --height" in capsys.readouterr().err
    probe.assert_not_called()


def test_cli_rejects_portrait_dimensions_before_processing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "film.mp4"
    input_path.touch()
    with patch("reelcard.cli.probe_video") as probe:
        result = main(
            [str(input_path), "--width", "620", "--height", "874"]
        )

    assert result == 2
    assert "landscape" in capsys.readouterr().err
    probe.assert_not_called()


def test_cli_checks_missing_input_before_running_ffprobe(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("reelcard.cli.probe_video") as probe:
        result = main([str(tmp_path / "missing.mp4")])

    assert result == 2
    assert "does not exist" in capsys.readouterr().err
    probe.assert_not_called()


def test_cli_rejects_existing_output_without_force_before_processing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "film.mp4"
    output_path = tmp_path / "poster.png"
    input_path.touch()
    output_path.write_bytes(b"existing")

    with patch("reelcard.cli.probe_video") as probe:
        result = main([str(input_path), "--output", str(output_path)])

    assert result == 2
    assert "use --force" in capsys.readouterr().err
    assert output_path.read_bytes() == b"existing"
    probe.assert_not_called()


def test_cli_runs_pipeline_with_metadata_and_custom_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "custom.png"
    input_path.touch()
    monkeypatch.chdir(tmp_path)
    metadata = VideoMetadata(90.0, 1920, 1080, 0)
    barcode = Image.new("RGB", (3, 64), "red")
    poster = Image.new("RGB", (620, 874), "white")

    with (
        patch("reelcard.cli.probe_video", return_value=metadata) as probe,
        patch("reelcard.cli.iter_video_frames", return_value=iter(())) as frames,
        patch("reelcard.cli.make_barcode", return_value=barcode) as make_barcode,
        patch("reelcard.cli.render_poster", return_value=poster) as render,
        patch("reelcard.cli.save_poster") as save,
    ):
        result = main(
            [
                str(input_path),
                "--title",
                "Film Title",
                "--year",
                "1994",
                "--director",
                "Director",
                "--writer",
                "Writer",
                "--starring",
                "Lead Cast",
                "--music",
                "Composer",
                "--subtitle",
                "Subtitle",
                "--credits",
                "Credits",
                "--output",
                str(output_path),
                "--stripes",
                "3",
                "--color-style",
                "vivid",
                "--width",
                "874",
                "--height",
                "620",
                "--dpi",
                "150",
                "--force",
            ]
        )

    assert result == 0
    probe.assert_called_once_with(input_path)
    frames.assert_called_once_with(input_path, 3, metadata=metadata)
    make_barcode.assert_called_once()
    assert make_barcode.call_args.kwargs["color_style"] == "vivid"
    render.assert_called_once_with(
        barcode,
        title="Film Title",
        runtime_seconds=90.0,
        year=1994,
        director="Director",
        writer="Writer",
        starring="Lead Cast",
        music="Composer",
        subtitle="Subtitle",
        credits="Credits",
        width=874,
        height=620,
        dpi=150.0,
    )
    save.assert_called_once_with(poster, output_path, dpi=150.0, overwrite=True)
    assert f"Saved poster to {output_path}" in capsys.readouterr().out


def test_cli_default_output_uses_sanitized_title_and_preset_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "My Film.mp4"
    input_path.touch()
    monkeypatch.chdir(tmp_path)
    metadata = VideoMetadata(60.0, 640, 480, 0)

    with (
        patch("reelcard.cli.probe_video", return_value=metadata),
        patch("reelcard.cli.iter_video_frames", return_value=iter(())),
        patch("reelcard.cli.make_barcode", return_value=Image.new("RGB", (1, 64))) as make_barcode,
        patch("reelcard.cli.render_poster") as render,
        patch("reelcard.cli.save_poster") as save,
    ):
        assert main([str(input_path)]) == 0

    assert make_barcode.call_args.kwargs["color_style"] == "natural"
    render.assert_called_once()
    assert render.call_args.kwargs["width"] == DEFAULT_WIDTH
    assert render.call_args.kwargs["height"] == DEFAULT_HEIGHT
    assert save.call_args.args[1] == tmp_path / "My-Film.png"


def test_cli_svg_format_uses_svg_output_and_default_extension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "Film.mp4"
    input_path.touch()
    monkeypatch.chdir(tmp_path)
    metadata = VideoMetadata(60.0, 640, 480, 0)
    barcode = Image.new("RGB", (1, 64), "red")

    with (
        patch("reelcard.cli.probe_video", return_value=metadata),
        patch("reelcard.cli.iter_video_frames", return_value=iter(())),
        patch("reelcard.cli.make_barcode", return_value=barcode),
        patch("reelcard.cli.render_poster") as render_png,
        patch("reelcard.cli.render_svg", return_value="<svg rendered/>") as render_svg,
        patch("reelcard.cli.save_svg") as save_svg,
    ):
        assert main([str(input_path), "--format", "svg"]) == 0

    render_png.assert_not_called()
    render_svg.assert_called_once()
    save_svg.assert_called_once_with(
        "<svg rendered/>",
        tmp_path / "Film.svg",
        overwrite=False,
    )


def test_cli_svg_format_rejects_mismatched_output_extension(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_path = tmp_path / "film.mp4"
    input_path.touch()

    result = main(
        [
            str(input_path),
            "--format",
            "svg",
            "--output",
            str(tmp_path / "film.png"),
        ]
    )

    assert result == 2
    assert ".svg extension" in capsys.readouterr().err


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg and FFprobe are required for the CLI integration test",
)
def test_cli_generates_poster_from_synthetic_video(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_path = tmp_path / "Synthetic Film.mkv"
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
            str(input_path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    monkeypatch.chdir(tmp_path)

    result = main([str(input_path), "--stripes", "2"])
    output_path = tmp_path / "Synthetic-Film.png"

    assert result == 0
    assert output_path.is_file()
    with Image.open(output_path) as poster:
        assert poster.format == "PNG"
        assert poster.size == (DEFAULT_WIDTH, DEFAULT_HEIGHT)
        assert poster.info["dpi"] == pytest.approx((300, 300), abs=0.1)
