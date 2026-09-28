from __future__ import annotations

import re
from datetime import timedelta

# Best-effort parser for the free-text `time_passed` field Plausibility Check produces
# (e.g. "10 minutes", "a few hours", "3 weeks"). Falls back to zero on anything it can't
# parse rather than erroring the turn — advancing Campaign.current_datetime is bookkeeping,
# not narrative canon, so an unparseable phrase just means "no time advanced this turn,"
# not a failed turn. See spec.md "What a tick actually is, now."

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "single": 1,
    "couple": 2, "couple of": 2, "two": 2,
    "few": 3, "a few": 3, "three": 3,
    "several": 4, "four": 4,
    "five": 5, "some": 3,
}

_UNIT_SECONDS = {
    "second": 1, "sec": 1,
    "minute": 60, "min": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,  # 30 days
    "year": 31536000,  # 365 days
}

_PATTERN = re.compile(
    r"(?P<number>\d+(?:\.\d+)?|" + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True)) + r")"
    r"\s+"
    r"(?P<unit>" + "|".join(_UNIT_SECONDS) + r")s?",
    re.IGNORECASE,
)


def parse_duration(text: str | None) -> timedelta:
    if not text:
        return timedelta(0)

    match = _PATTERN.search(text.lower())
    if not match:
        return timedelta(0)

    number_raw = match.group("number")
    unit = match.group("unit").lower()

    if number_raw in _WORD_NUMBERS:
        number = _WORD_NUMBERS[number_raw]
    else:
        try:
            number = float(number_raw)
        except ValueError:
            return timedelta(0)

    return timedelta(seconds=number * _UNIT_SECONDS[unit])
