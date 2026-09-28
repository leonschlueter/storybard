from __future__ import annotations

from storybard.services.mechanics.formulas import POINT_BUY_POOL, point_buy_cost


class TestPointBuyCost:
    def test_all_default_scores_cost_nothing(self):
        assert point_buy_cost({"str": 8, "dex": 8, "con": 8, "int": 8, "wis": 8, "cha": 8}) == 0

    def test_under_budget(self):
        cost = point_buy_cost({"str": 15, "dex": 8, "con": 8, "int": 8, "wis": 8, "cha": 8})
        assert cost == 9
        assert cost <= POINT_BUY_POOL

    def test_at_budget_exactly(self):
        # 15,15,15,8,8,8 -> 9+9+9+0+0+0 = 27, exactly the pool.
        exact = {"str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8, "cha": 8}
        assert point_buy_cost(exact) == POINT_BUY_POOL

    def test_over_budget(self):
        # One point over the exact-budget combination above.
        cost = point_buy_cost({"str": 15, "dex": 15, "con": 15, "int": 9, "wis": 8, "cha": 8})
        assert cost > POINT_BUY_POOL

    def test_out_of_range_scores_ignored_by_pure_cost_function(self):
        # This function only sums the curve — range validation (8-15) is the caller's job
        # (api/party.py::_finalize_character), documented explicitly in its docstring.
        assert point_buy_cost({"str": 20}) == 0
