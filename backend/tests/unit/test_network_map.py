"""Coordinate validation tests for the optional distribution network map."""

import math

import pandas as pd
import pytest

from backend.services.network_map import _coordinate


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"latitude": 90, "longitude": -180}, (90.0, -180.0, "valid")),
        ({"lat": -90, "lon": 180}, (-90.0, 180.0, "valid")),
        ({"name": "No coordinates"}, (None, None, "missing")),
        ({"latitude": 91, "longitude": 0}, (None, None, "invalid")),
        ({"latitude": 0, "longitude": math.inf}, (None, None, "invalid")),
        ({"latitude": 0}, (None, None, "invalid")),
        ({"latitude": "", "longitude": 0}, (None, None, "invalid")),
    ],
)
def test_map_coordinates_are_validated(row, expected):
    assert _coordinate(pd.Series(row)) == expected
