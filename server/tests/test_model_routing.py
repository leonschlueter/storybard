from __future__ import annotations

from storybard.chain.graph import CREATIVE_NODE_TYPES


def test_creative_node_types_are_exactly_the_judgment_heavy_ones():
    assert CREATIVE_NODE_TYPES == {
        "opportunity_spotting", "plan_synthesis", "world_update", "twist", "narrator",
    }
