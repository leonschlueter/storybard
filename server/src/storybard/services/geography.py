from __future__ import annotations

import math
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storybard.domain.world import WorldNode

# WorldNode x/y are local to their own parent's coordinate space, not global (see
# domain/world.py). Two nodes under different branches of the hierarchy can't be compared
# directly — "the inn" (local to "the village") and "the docks" (local to "the port town")
# have coordinates in two unrelated spaces. lca_distance() approximates cross-branch
# distance by walking both ancestor chains to their lowest common ancestor (LCA), then
# projecting each node down to whichever of its ancestors is a *direct child* of that LCA
# (that projected ancestor's local x/y is comparable, since both projections share the
# LCA's coordinate space) — an approximation (using the sibling settlement's position as a
# stand-in for anything inside it), not exact geometry, per the user's own proposal.


def ancestor_chain(node: WorldNode, by_id: dict[uuid.UUID, WorldNode]) -> list[WorldNode]:
    """Root-to-node order, inclusive of `node` itself."""
    chain = [node]
    current = node
    while current.parent_node_id is not None:
        parent = by_id.get(current.parent_node_id)
        if parent is None:
            break
        chain.append(parent)
        current = parent
    return list(reversed(chain))


def lca_distance(
    node: WorldNode, ancestors: list[WorldNode], other: WorldNode, other_ancestors: list[WorldNode]
) -> float:
    """`ancestors`/`other_ancestors` are each node's own root-to-node chain (see
    `ancestor_chain`), inclusive of the node itself. Returns 0.0 if the two chains share no
    common node (disconnected hierarchies) — callers should treat that as "unknown," not
    "adjacent."""
    if node.id == other.id:
        return 0.0

    common_ids = {a.id for a in ancestors} & {a.id for a in other_ancestors}
    if not common_ids:
        return 0.0

    # The LCA is the deepest node common to both chains — walk from the end (the node
    # itself) backward until hitting a shared id.
    lca_id: uuid.UUID | None = None
    for a in reversed(ancestors):
        if a.id in common_ids:
            lca_id = a.id
            break
    if lca_id is None:
        return 0.0

    # One node IS the LCA — i.e. it's a (possibly indirect) ancestor of the other. Treat
    # that as adjacent (0.0) rather than projecting: the ancestor has no "position within
    # itself" to compare against its descendant's branch.
    if lca_id == node.id or lca_id == other.id:
        return 0.0

    def _project(chain: list[WorldNode]) -> WorldNode:
        # The direct child of the LCA on this chain — same node if the node itself is that
        # child (or is the LCA, e.g. one node is an ancestor of the other).
        for i, a in enumerate(chain):
            if a.id == lca_id:
                return chain[i + 1] if i + 1 < len(chain) else chain[i]
        return chain[-1]

    projected_a = _project(ancestors)
    projected_b = _project(other_ancestors)

    if projected_a.id == projected_b.id:
        return 0.0

    ax, ay = projected_a.x or 0.0, projected_a.y or 0.0
    bx, by = projected_b.x or 0.0, projected_b.y or 0.0
    return math.hypot(ax - bx, ay - by)


async def nearby_locations(
    db: AsyncSession, *, campaign_id: uuid.UUID, node_id: uuid.UUID, max_distance: float
) -> list[WorldNode]:
    """All WorldNodes in the campaign within `max_distance` of `node_id`, via lca_distance.
    Fetches the campaign's full node set once — small enough that no pagination/spatial
    index is needed at this phase's scale."""
    nodes = (await db.execute(select(WorldNode).where(WorldNode.campaign_id == campaign_id))).scalars().all()
    by_id = {n.id: n for n in nodes}

    origin = by_id.get(node_id)
    if origin is None:
        return []

    origin_chain = ancestor_chain(origin, by_id)
    results = []
    for candidate in nodes:
        if candidate.id == origin.id:
            continue
        candidate_chain = ancestor_chain(candidate, by_id)
        if lca_distance(origin, origin_chain, candidate, candidate_chain) <= max_distance:
            results.append(candidate)
    return results
