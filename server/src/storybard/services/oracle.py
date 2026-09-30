from __future__ import annotations

# A minimal oracle table (feature #18, "All 20 Features" plan) — a small, stripped-down
# pull-forward of the deferred Mythic GME hook-point (spec.md), used only as a concrete
# seed for the hard pacing floor (chain/service.py::_apply_hard_pacing_floor) rather than
# a general "ask the oracle" mechanic. Deliberately hardcoded, not LLM-generated: this
# fires specifically when the LLM-driven chain has gone quiet for too long, so it can't
# depend on another LLM call to break that silence.
ORACLE_EVENTS: list[str] = [
    "A stranger arrives, clearly searching for someone.",
    "The weather turns abruptly, forcing a change of plans.",
    "A distant sound — a bell, a horn, a scream — cuts through the quiet.",
    "Word spreads of trouble elsewhere in the region.",
    "Someone recognizes the party, for better or worse.",
    "A messenger arrives with news that changes the stakes.",
    "An old debt or promise comes due.",
    "A rival or competitor makes their move.",
    "Something valuable goes missing.",
    "An unexpected ally offers help, at a price.",
]
