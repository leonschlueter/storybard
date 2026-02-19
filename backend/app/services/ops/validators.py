from __future__ import annotations

def validate_item_effect(effect: dict) -> None:
    # Minimal guardrails; extend later.
    # Example constraints: if effect contains damage dice, cap them.
    if not isinstance(effect, dict):
        raise ValueError("effect must be an object")
    dmg = effect.get("damage")
    if dmg and isinstance(dmg, dict):
        dice = str(dmg.get("dice",""))
        # naive cap: disallow more than 4 dice of d12 at low level
        if any(x in dice for x in ["10d", "12d", "20d"]):
            raise ValueError("damage dice too large")

def validate_spell_effect(effect: dict, level: int) -> None:
    if not isinstance(effect, dict):
        raise ValueError("effect must be an object")
    # Simple cap: avoid absurd scaling at low levels
    dmg = effect.get("damage")
    if dmg and isinstance(dmg, dict):
        dice = str(dmg.get("dice",""))
        if level <= 3 and any(x in dice for x in ["10d", "12d", "20d"]):
            raise ValueError("spell damage too large for level")
