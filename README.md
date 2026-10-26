# Reelcard

Reelcard is a local command-line tool for turning a video into a postcard-sized
film-barcode print. It samples frames in chronological order, calculates a
representative colour for each, and arranges the colours as vertical stripes
within a carefully typeset poster.

> **Project status:** Early development. Video processing and poster generation
> are not implemented yet.

## Planned features

- A chronological colour barcode generated from a local video.
- A portrait postcard design with title, optional year and credits, and runtime.
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
reelcard "My Film.mp4" --title "My Film" --year 1994
```

The command-line interface is a placeholder while the poster pipeline is being
implemented. Run `reelcard --help` to see the current arguments. The video
metadata and sampling components are available as package internals but are not
connected to the CLI yet.

Planned options include the film title and year, director, subtitle, credits,
output path, stripe count, postcard or custom output dimensions, and print DPI.
The default print size is planned to be approximately 105 × 148 mm at 300 DPI
(about 1240 × 1748 pixels).

## Output

The initial release is planned to export a deterministic PNG. Video metadata
will be read locally using FFprobe, and selected frames will be decoded by
FFmpeg. PDF and vector exports are possible future enhancements.

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
