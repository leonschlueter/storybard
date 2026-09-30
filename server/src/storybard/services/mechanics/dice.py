from __future__ import annotations

import random

from storybard.services.mechanics.formulas import ability_mod

# The dice-resolution layer mechanical_check has always been missing (see the "Real
# Mechanical Consequences" plan) — mechanical_check only ever decided *whether* a roll was
# needed; nothing anywhere actually rolled one, so the Narrator just narrated success
# regardless. This is the deterministic piece: never an LLM call, called directly by
# chain/graph.py::roll_resolution_generate and its retry-as-reroll path in
# chain/service.py::resolve_step.

_DEGREE_MARGIN = 5  # +5/-4 over/under the DC is "clean," within that band is "narrow."


def roll_d20() -> int:
    return random.randint(1, 20)


def resolve_check(*, ability_score: int, dc: int, ability: str) -> dict:
    """A natural 20/1 always critically succeeds/fails regardless of the total — standard
    5e-ish flavor, matching this codebase's existing "5e-ish, not strictly accurate" level
    of mechanical fidelity (see formulas.py)."""
    rolled = roll_d20()
    modifier = ability_mod(ability_score)
    total = rolled + modifier

    if rolled == 20:
        degree = "critical_success"
    elif rolled == 1:
        degree = "critical_failure"
    elif total >= dc + _DEGREE_MARGIN:
        degree = "clean_success"
    elif total >= dc:
        degree = "narrow_success"
    elif total >= dc - (_DEGREE_MARGIN - 1):
        degree = "narrow_failure"
    else:
        degree = "clean_failure"

    return {"rolled": rolled, "modifier": modifier, "total": total, "dc": dc, "ability": ability, "degree": degree}
