from __future__ import annotations
from math import floor

def ability_mod(score: int) -> int:
    return floor((score - 10) / 2)

def proficiency_bonus(level: int) -> int:
    # 5e-like progression
    if level >= 17:
        return 6
    if level >= 13:
        return 5
    if level >= 9:
        return 4
    if level >= 5:
        return 3
    return 2

def skill_ability(skill: str) -> str:
    mapping = {
        "athletics": "STR",
        "acrobatics": "DEX",
        "sleight_of_hand": "DEX",
        "stealth": "DEX",
        "arcana": "INT",
        "history": "INT",
        "investigation": "INT",
        "nature": "INT",
        "religion": "INT",
        "animal_handling": "WIS",
        "insight": "WIS",
        "medicine": "WIS",
        "perception": "WIS",
        "survival": "WIS",
        "deception": "CHA",
        "intimidation": "CHA",
        "performance": "CHA",
        "persuasion": "CHA",
    }
    return mapping.get(skill.lower(), "DEX")
