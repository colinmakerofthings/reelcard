# Reelcard

[![Tests](https://github.com/colinmakerofthings/reelcard/actions/workflows/tests.yml/badge.svg)](https://github.com/colinmakerofthings/reelcard/actions/workflows/tests.yml)

Reelcard is a local command-line tool for turning a video into a postcard-sized
film-barcode print. It samples frames in chronological order, calculates a
representative colour for each, and arranges the colours as vertical stripes
within a carefully typeset poster.

> **Project status:** Early development. The command-line pipeline generates
> postcard PNGs from local videos.

## Planned features

- A chronological colour barcode generated from a local video.
- A landscape postcard design with title, optional year and credits, and runtime.
- PNG output sized for printing at 300 DPI.
- No accounts, hosted backend, telemetry, or network access during normal use.

## Requirements

- Python 3.11 or newer.
- FFmpeg and FFprobe available on your `PATH`.

FFmpeg and FFprobe are separate system programs; installing the Python package
will not install them. Install FFmpeg using a trusted package manager for your
operating system, then check that both `ffmpeg -version` and
`ffprobe -version` work in a new terminal. For example, Windows users can use
`winget install Gyan.FFmpeg` or `choco install ffmpeg`, macOS users can use
`brew install ffmpeg`, and Debian/Ubuntu users can use
`sudo apt install ffmpeg`.

## Installation

The package is not published yet. For development, clone the repository and
install it into a virtual environment:

```console
python -m venv .venv
```

Activate the environment, then run:

```console
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Usage

The intended interface is:

```console
reelcard "My Film.mp4"
reelcard "My Film.mp4" --title "My Film" --year 1994 --stripes 600
reelcard "My Film.mp4" --output "my-film-postcard.png" --director "A. Director"
```

The input filename supplies the title when `--title` is omitted. By default,
Reelcard writes a sanitized title-based PNG into the current directory and
refuses to replace an existing file. Use `--force` to replace it.

Run `reelcard --help` for all options:

| Option | Description |
| --- | --- |
| `--title TEXT` | Poster title; defaults to the video filename. |
| `--year YEAR` | Optional release year from 1 to 9999. |
| `--director TEXT` | Optional director credit. |
| `--writer TEXT` | Optional writer credit. |
| `--starring TEXT` | Optional lead cast. |
| `--music TEXT` | Optional music credit. |
| `--subtitle TEXT` | Optional subtitle below the barcode. |
| `--credits TEXT` | Optional footer credits. |
| `--output PATH` | PNG destination; parent directory must already exist. |
| `--stripes N` | Number of sampled frames/stripes (default 300; maximum 10000). |
| `--size postcard` | Named print-size preset (the default). |
| `--width PX --height PX` | Custom landscape output dimensions; specify both. |
| `--dpi DPI` | Print-resolution metadata (default 300). |
| `--force` | Allow replacing an existing output file. |

The postcard preset is approximately 148 × 105 mm at 300 DPI (1748 × 1240
pixels). FFmpeg and FFprobe process the video locally; Reelcard does not use an
online movie database or require network access. Barcode colors are calculated
from the brighter 75% of each sampled frame, reducing shadow bias without an
artificial brightness lift.

## Output

Reelcard exports a PNG with print-resolution metadata. Video metadata is read
locally using FFprobe, and selected frames are decoded by FFmpeg. PDF and
vector exports are possible future enhancements.

## Supported platforms and limitations

Windows, macOS, and Linux are the intended platforms. FFmpeg and FFprobe must
be installed separately. Exact codec support depends on the FFmpeg build and
the input video. Platform support and known limitations will be documented as
implementation and testing progress.

## Development

Install the development dependencies as described above. Run the test suite
from the repository root with:

```console
python -m pytest
```

The package uses a `src` layout. Tests will be separated between pure
algorithm/rendering checks and tests that need FFmpeg. Test videos should be
small synthetic fixtures rather than copyrighted films.

## Licence

Reelcard is distributed under the MIT License; see [LICENSE](LICENSE).
The bundled Montserrat font is licensed under the SIL Open Font License 1.1;
see [the font licence](src/reelcard/fonts/Montserrat-OFL.txt).
