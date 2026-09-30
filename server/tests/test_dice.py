from __future__ import annotations

from unittest.mock import patch

from storybard.services.mechanics.dice import resolve_check


def _rolled(value: int):
    return patch("storybard.services.mechanics.dice.roll_d20", return_value=value)


class TestResolveCheckDegrees:
    def test_natural_20_is_critical_success_even_against_a_huge_dc(self):
        with _rolled(20):
            result = resolve_check(ability_score=8, dc=30, ability="str")
        assert result["degree"] == "critical_success"
        assert result["rolled"] == 20

    def test_natural_1_is_critical_failure_even_against_a_trivial_dc(self):
        with _rolled(1):
            result = resolve_check(ability_score=20, dc=5, ability="str")
        assert result["degree"] == "critical_failure"

    def test_clean_success_five_or_more_over_dc(self):
        # score 16 -> mod +3; rolled 12 -> total 15; dc 10 -> margin 5
        with _rolled(12):
            result = resolve_check(ability_score=16, dc=10, ability="str")
        assert result["total"] == 15
        assert result["degree"] == "clean_success"

    def test_narrow_success_meets_dc_but_not_by_five(self):
        with _rolled(11):
            result = resolve_check(ability_score=16, dc=10, ability="str")
        assert result["total"] == 14
        assert result["degree"] == "narrow_success"

    def test_narrow_failure_within_four_under_dc(self):
        with _rolled(8):
            result = resolve_check(ability_score=16, dc=15, ability="str")
        assert result["total"] == 11
        assert result["degree"] == "narrow_failure"

    def test_clean_failure_five_or_more_under_dc(self):
        with _rolled(2):
            result = resolve_check(ability_score=10, dc=20, ability="str")
        assert result["total"] == 2
        assert result["degree"] == "clean_failure"

    def test_modifier_uses_ability_mod_formula(self):
        with _rolled(10):
            result = resolve_check(ability_score=14, dc=10, ability="dex")
        assert result["modifier"] == 2  # (14-10)//2
        assert result["total"] == 12
        assert result["ability"] == "dex"
