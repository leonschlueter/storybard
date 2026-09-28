from __future__ import annotations

from datetime import timedelta

import pytest

from storybard.services.duration import parse_duration


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10 minutes", timedelta(minutes=10)),
        ("3 weeks", timedelta(weeks=3)),
        ("a few hours", timedelta(hours=3)),
        ("an hour", timedelta(hours=1)),
        ("several days", timedelta(days=4)),
        ("a couple of minutes", timedelta(minutes=2)),
        (None, timedelta(0)),
        ("", timedelta(0)),
        ("in the blink of an eye", timedelta(0)),
        ("instantly", timedelta(0)),
    ],
)
def test_parse_duration(text, expected):
    assert parse_duration(text) == expected
