"""Optional movie metadata lookup through the OMDb API."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

OMDB_URL = "https://www.omdbapi.com/"
LOOKUP_TIMEOUT = 10.0


class MetadataLookupError(Exception):
    """An expected credential, network, or response failure during lookup."""


@dataclass(frozen=True)
class MovieMetadata:
    """Movie details returned by OMDb."""

    title: str | None = None
    year: int | None = None
    director: str | None = None
    writer: str | None = None
    starring: str | None = None
    runtime: str | None = None
    rating: str | None = None
    imdb_rating: str | None = None
    plot: str | None = None


def lookup_movie(*, imdb_id: str, api_key: str | None) -> MovieMetadata:
    """Fetch metadata for a specific IMDb ID from OMDb."""
    if not api_key:
        raise MetadataLookupError(
            "OMDb lookup requires an API key; set the OMDB_API_KEY environment variable."
        )

    payload = _request({"i": imdb_id, "plot": "short", "apikey": api_key})
    if payload.get("Response") != "True":
        raise MetadataLookupError(_api_error(payload))

    year_text = _field(payload, "Year")
    year_match = re.match(r"\d{4}", year_text or "")
    ratings = payload.get("Ratings")
    imdb_rating = None
    if isinstance(ratings, list):
        for rating in ratings:
            if isinstance(rating, dict) and rating.get("Source") == "Internet Movie Database":
                value = rating.get("Value")
                if isinstance(value, str) and value.strip() and value != "N/A":
                    imdb_rating = " ".join(value.split())
                    break

    return MovieMetadata(
        title=_field(payload, "Title"),
        year=int(year_match.group()) if year_match else None,
        director=_field(payload, "Director"),
        writer=_field(payload, "Writer"),
        starring=_field(payload, "Actors"),
        runtime=_field(payload, "Runtime"),
        rating=_field(payload, "Rated"),
        imdb_rating=imdb_rating,
        plot=_field(payload, "Plot"),
    )


def _request(parameters: dict[str, str]) -> dict[str, object]:
    request = Request(f"{OMDB_URL}?{urlencode(parameters)}")
    try:
        with urlopen(request, timeout=LOOKUP_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, OSError) as exc:
        raise MetadataLookupError(f"Could not reach OMDb: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MetadataLookupError("OMDb returned an invalid JSON response.") from exc
    if not isinstance(payload, dict):
        raise MetadataLookupError("OMDb returned an invalid response.")
    return payload


def _field(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or value == "N/A":
        return None
    return " ".join(value.split())


def _api_error(payload: dict[str, object]) -> str:
    message = payload.get("Error")
    if isinstance(message, str) and message.strip():
        return f"OMDb lookup failed: {message}"
    return "OMDb returned an unsuccessful response."
