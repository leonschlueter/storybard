from __future__ import annotations

from math import floor


def ability_mod(score: int) -> int:
    """Ruleset-agnostic: works for any attribute, not just 5e's six."""
    return floor((score - 10) / 2)


def proficiency_bonus(level: int) -> int:
    """5e-ish progression. Ruleset-specific; lives behind the pluggable Ruleset interface."""
    if level >= 17:
        return 6
    if level >= 13:
        return 5
    if level >= 9:
        return 4
    if level >= 5:
        return 3
    return 2


def encumbrance_max_weight(strength_score: int) -> float:
    """5e-ish: STR * 15. Ruleset-specific."""
    return float(strength_score * 15)


# Standard 5e point-buy: 27-point pool, 8-15 range. Enforced server-side in
# api/party.py::finalize_character — a client hint duplicates this curve for live UX
# feedback, but this is the actual guardrail (rejected with a reason, never a silent
# clamp), matching every other cap in this codebase being enforced in code, not trusted to
# the client. See spec.md Step 7: "pool size + cost curve also ruleset-configurable" —
# hardcoded here for now, hot-swappable ruleset config is Phase 5 territory.
POINT_BUY_POOL = 27
POINT_BUY_COST: dict[int, int] = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}


def point_buy_cost(scores: dict[str, int]) -> int:
    """Sums each score's point-buy cost. Scores outside the 8-15 curve are ignored (not
    charged) — this only validates the point-buy budget itself; out-of-range values are a
    separate, obvious-on-inspection problem, not this function's job to catch."""
    return sum(POINT_BUY_COST.get(score, 0) for score in scores.values())
