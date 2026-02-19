from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.character_sheet import CharacterSheet
from app.services.mechanics.modifiers import ability_mod, proficiency_bonus, skill_ability

def skill_modifier(db: Session, actor_id: str, skill: str) -> tuple[int, dict]:
    sheet = db.execute(select(CharacterSheet).where(CharacterSheet.actor_id == actor_id)).scalar_one_or_none()
    if not sheet:
        return 0, {"reason": "no_sheet"}

    scores = sheet.ability_scores or {}
    abil = skill_ability(skill)
    abil_score = int(scores.get(abil, 10))
    abil_mod = ability_mod(abil_score)

    profs = sheet.proficiencies or {}
    skill_profs = set((profs.get("skills") or []))
    prof = proficiency_bonus(sheet.level) if skill.lower() in skill_profs else 0

    total = abil_mod + prof
    details = {"ability": abil, "ability_score": abil_score, "ability_mod": abil_mod, "proficient": skill.lower() in skill_profs, "proficiency_bonus": prof}
    return total, details

def resolve_skill_check(*, d20: int, modifier: int, dc: int) -> tuple[int, str]:
    total = int(d20) + int(modifier)
    if d20 == 20:
        return total, "crit_success"
    if d20 == 1:
        return total, "crit_fail"
    return total, ("success" if total >= dc else "fail")
