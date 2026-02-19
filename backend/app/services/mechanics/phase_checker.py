from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from app.utils.enums import Phase, RollType
from app.services.llm.schemas import IntentOut, CheckAdviceOut

@dataclass
class PhaseDecision:
    phase: Phase
    roll_type: RollType | None = None
    skill: str | None = None
    dc: int | None = None
    dc_reason: str | None = None
    time_passed_minutes: int = 0
    time_reason: str | None = None
    mode_change_to: str | None = None
    notes: list[str] | None = None

class PhaseChecker:
    """Deterministic coordinator: uses intent + (optionally) LLM check advice to decide the phase."""

    def decide(
        self,
        *,
        mode: str,
        intent: IntentOut,
        check_advice: CheckAdviceOut,
    ) -> PhaseDecision:

        # Mode command always wins
        if intent.requested_mode:
            return PhaseDecision(
                phase=Phase.mode_change,
                mode_change_to=intent.requested_mode,
                time_passed_minutes=0,
                notes=["mode_requested"],
            )

        # Default: trust the check advisor for now, but guardrails below
        phase = check_advice.phase
        if phase == Phase.skill_check_required:
            # Guardrails for DC
            dc = check_advice.dc
            if dc is None:
                dc = 15
            dc = max(5, min(30, int(dc)))
            return PhaseDecision(
                phase=Phase.skill_check_required,
                roll_type=RollType.skill_check,
                skill=(check_advice.skill or "perception"),
                dc=dc,
                dc_reason=(check_advice.dc_reason or "Uncertain outcome in this situation."),
                time_passed_minutes=max(0, min(240, int(check_advice.time_passed_minutes or 0))),
                time_reason=check_advice.time_reason,
                notes=check_advice.notes or [],
            )

        if phase == Phase.initiative_required:
            return PhaseDecision(
                phase=Phase.initiative_required,
                roll_type=RollType.initiative,
                time_passed_minutes=max(0, min(240, int(check_advice.time_passed_minutes or 0))),
                time_reason=check_advice.time_reason,
                notes=check_advice.notes or [],
            )

        # narrative fallback
        return PhaseDecision(
            phase=Phase.narrative,
            time_passed_minutes=max(0, min(240, int(check_advice.time_passed_minutes or 0))),
            time_reason=check_advice.time_reason,
            notes=check_advice.notes or [],
        )
