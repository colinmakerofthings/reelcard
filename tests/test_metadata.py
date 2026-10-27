"""Tests for optional OMDb metadata lookup."""

from __future__ import annotations

import io
import json
from urllib.parse import parse_qs, urlparse
from urllib.request import Request
from unittest.mock import patch

import pytest

from reelcard.metadata import MetadataLookupError, lookup_movie


def _response(payload: dict[str, object]) -> io.BytesIO:
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


def test_lookup_movie_fetches_details_by_imdb_id() -> None:
    detail_response = {
        "Response": "True",
        "Title": "Film",
        "Year": "1994",
        "Director": "A Director",
        "Writer": "A Writer",
        "Actors": "An Actor",
        "Music": "N/A",
    }

    with patch(
        "reelcard.metadata.urlopen",
        return_value=_response(detail_response),
    ) as urlopen:
        result = lookup_movie(
            imdb_id="tt0000001",
            api_key="test-key",
        )

    assert result is not None
    assert result.title == "Film"
    assert result.year == 1994
    assert result.director == "A Director"
    assert result.writer == "A Writer"
    assert result.starring == "An Actor"
    assert urlopen.call_count == 1
    request = urlopen.call_args.args[0]
    assert isinstance(request, Request)
    query = parse_qs(urlparse(request.full_url).query)
    assert query["i"] == ["tt0000001"]
    assert query["apikey"] == ["test-key"]


def test_lookup_movie_reports_missing_api_key() -> None:
    with pytest.raises(MetadataLookupError, match="OMDB_API_KEY"):
        lookup_movie(imdb_id="tt0000001", api_key=None)


def test_lookup_movie_reports_api_failure() -> None:
    with (
        patch(
            "reelcard.metadata.urlopen",
            return_value=_response(
                {"Response": "False", "Error": "Invalid API key!"}
            ),
        ),
        pytest.raises(MetadataLookupError, match="Invalid API key"),
    ):
        lookup_movie(imdb_id="tt0000001", api_key="bad-key")
