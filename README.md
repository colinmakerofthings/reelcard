# Reelcard

[![Tests](https://github.com/colinmakerofthings/reelcard/actions/workflows/tests.yml/badge.svg)](https://github.com/colinmakerofthings/reelcard/actions/workflows/tests.yml)

Reelcard is a local command-line tool for turning a video into a postcard-sized
film-barcode print. It samples frames in chronological order, calculates a
representative colour for each, and arranges the colours as vertical stripes
within a carefully typeset poster.

> **Release:** 0.1.3 early release preview. The core workflow is usable, but
> features and command-line options may change as the project develops.

## Example output

![Example Reelcard poster for The Empire Strikes Back (1980)](assets/example-empire-strikes-back.png)

This landscape postcard was generated from a local video; the credits were
provided as command-line options.

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

Reelcard is not yet published on PyPI. Install the 0.1.3 preview from source:

```console
git clone https://github.com/colinmakerofthings/reelcard.git
cd reelcard
python -m venv .venv
```

Activate the environment, then run:

```console
python -m pip install --upgrade pip
python -m pip install .
```

## Usage

Examples:

```console
reelcard "My Film.mp4"
reelcard "My Film.mp4" --title "My Film" --year 1994 --stripes 600
reelcard "My Film.mp4" --output "my-film-postcard.png" --director "A. Director"
reelcard "My Film.mp4" --format svg
reelcard "My Film.mp4" --color-style brighter --force
reelcard "My Film.mp4" --color-style vivid --force
reelcard "My Film.mp4" --imdb-id tt0087182
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
| `--imdb-id ID` | Look up missing metadata for this movie via OMDb; requires an API key. |
| `--output PATH` | Output destination; extension must match the selected format. |
| `--format FORMAT` | Output format: `png` (default) or `svg`. |
| `--stripes N` | Number of sampled frames/stripes (default 300; maximum 10000). |
| `--color-style STYLE` | Barcode colors: `natural` (default), `brighter`, or `vivid`. |
| `--size postcard` | Named print-size preset (the default). |
| `--width PX --height PX` | Custom landscape output dimensions; specify both. |
| `--dpi DPI` | Print-resolution metadata (default 300). |
| `--force` | Allow replacing an existing output file. |

The postcard preset is approximately 148 × 105 mm at 300 DPI (1748 × 1240
pixels). FFmpeg and FFprobe process the video locally. Reelcard does not
contact an online movie database unless metadata lookup is explicitly enabled.
Barcode colors are calculated from the brighter 75% of each sampled frame,
reducing shadow bias without an artificial brightness lift.

Use `--color-style brighter` for a moderate brightness lift or `--color-style
vivid` to increase color saturation. The default `natural` style keeps the
original sampled colors. Use `--force` to replace the same output while
comparing styles.

## Optional metadata lookup

Manual mode is the default and does not make network requests. To look up
metadata for a specific movie, obtain an OMDb API key, set it in the
`OMDB_API_KEY` environment variable, and pass the movie's IMDb ID with
`--imdb-id`.

Lookup fills the title, year, director, writer, and starring fields only when
they were not supplied manually. OMDb does not provide every poster field, so
music, subtitle, and credits remain manual. Missing credentials, network
problems, and lookup failures produce a warning and Reelcard continues with
manual values and defaults.

## Output

Reelcard exports PNG images with print-resolution metadata by default. Choose
`--format svg` for an SVG with vector text and background; the barcode itself
is drawn as vector rectangles too. The SVG embeds the Montserrat font so the
typography remains consistent on computers without that font installed. Its
physical dimensions use the selected DPI. Video metadata is read locally using
FFprobe, and selected frames are decoded by FFmpeg.

## Supported platforms and limitations

Reelcard is designed for Windows, macOS, and Linux. FFmpeg and FFprobe must be
installed separately, and codec support depends on the FFmpeg build and input
video. Movie credits and other poster details must be entered manually; Reelcard
can optionally look up some fields through OMDb when requested. Frame sampling
decodes the video in a single FFmpeg process but can still take time for long
videos or high stripe counts.

## Development

Install the development dependencies instead of the runtime-only package:

```console
python -m pip install -e ".[dev]"
```

Run the test suite from the repository root with coverage reporting:

```console
python -m pytest --cov=reelcard --cov-report=term-missing
```

## Licence

Reelcard is distributed under the MIT License; see [LICENSE](LICENSE).
The bundled Montserrat font is licensed under the SIL Open Font License 1.1;
see [the font licence](src/reelcard/fonts/Montserrat-OFL.txt).
