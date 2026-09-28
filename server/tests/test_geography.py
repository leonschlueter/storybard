from __future__ import annotations

import uuid

from storybard.domain.world import WorldNode
from storybard.services.geography import ancestor_chain, lca_distance


def _node(*, id=None, parent_id=None, depth=0, x=0.0, y=0.0) -> WorldNode:
    return WorldNode(
        id=id or uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        name="node",
        parent_node_id=parent_id,
        depth=depth,
        x=x,
        y=y,
    )


class TestLcaDistance:
    def test_same_node_is_zero(self):
        node = _node()
        assert lca_distance(node, [node], node, [node]) == 0.0

    def test_direct_siblings_under_one_parent(self):
        parent = _node(depth=0, x=0.0, y=0.0)
        by_id = {parent.id: parent}
        inn = _node(parent_id=parent.id, depth=1, x=3.0, y=0.0)
        market = _node(parent_id=parent.id, depth=1, x=0.0, y=4.0)
        inn_chain = ancestor_chain(inn, {**by_id, inn.id: inn})
        market_chain = ancestor_chain(market, {**by_id, market.id: market})
        assert lca_distance(inn, inn_chain, market, market_chain) == 5.0

    def test_cross_branch_via_lca_projects_to_direct_children(self):
        # world -> {village_a -> {inn}, village_b -> {tavern}}. inn/tavern live in different
        # local coordinate spaces (their own village's), so distance is approximated via
        # the LCA (world) using the villages' own positions, not the leaf nodes' local x/y.
        world = _node(depth=0, x=0.0, y=0.0)
        village_a = _node(parent_id=world.id, depth=1, x=10.0, y=0.0)
        village_b = _node(parent_id=world.id, depth=1, x=0.0, y=0.0)
        inn = _node(parent_id=village_a.id, depth=2, x=999.0, y=999.0)  # local to village_a
        tavern = _node(parent_id=village_b.id, depth=2, x=-999.0, y=-999.0)  # local to village_b

        by_id = {world.id: world, village_a.id: village_a, village_b.id: village_b, inn.id: inn, tavern.id: tavern}
        inn_chain = ancestor_chain(inn, by_id)
        tavern_chain = ancestor_chain(tavern, by_id)

        # Projected distance is village_a-to-village_b (10.0), NOT a function of inn/tavern's
        # own huge local coordinates — those are meaningless outside their own village.
        assert lca_distance(inn, inn_chain, tavern, tavern_chain) == 10.0

    def test_ancestor_of_each_other_is_zero(self):
        world = _node(depth=0)
        village = _node(parent_id=world.id, depth=1, x=5.0, y=0.0)
        by_id = {world.id: world, village.id: village}
        world_chain = ancestor_chain(world, by_id)
        village_chain = ancestor_chain(village, by_id)
        # world is village's own parent — the "direct child of LCA" for both sides resolves
        # to the same node (village), so distance is 0, not garbage from comparing world's
        # own coordinates (which are meaningless — it has no parent) against village's.
        assert lca_distance(world, world_chain, village, village_chain) == 0.0

    def test_disconnected_hierarchies_return_zero(self):
        a = _node()
        b = _node()
        assert lca_distance(a, [a], b, [b]) == 0.0
