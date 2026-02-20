from __future__ import annotations

def render_context_blocks(blocks: list[dict]) -> str:
    lines = []
    for b in sorted(blocks, key=lambda x: float(x.get("priority", 0.5)), reverse=True):
        lines.append(f"[{b.get('type')}] {b.get('title')} (scope={b.get('scope_type')}:{b.get('scope_id')})")
        if b.get("summary"):
            lines.append(b["summary"])
        if b.get("full_text"):
            lines.append(b["full_text"])
        lines.append("")
    return "\n".join(lines).strip()

def render_lore_pages(pages: list[dict]) -> str:
    lines = []
    for p in pages:
        lines.append(f"LORE: {p.get('title')} (id={p.get('id')})")
        if p.get("summary"):
            lines.append(f"Summary: {p['summary']}")
        if p.get("content"):
            lines.append(p["content"])
        lines.append("")
    return "\n".join(lines).strip()

def render_recent_history(events: list[dict]) -> str:
    lines = []
    for e in events:
        lines.append(f"PLAYER: {e.get('action_text')}")
        if e.get("narration"):
            lines.append(f"NARRATOR: {e.get('narration')}")
        if e.get("check") and e["check"].get("outcome"):
            lines.append(f"CHECK: {e['check']}")
        lines.append("")
    return "\n".join(lines).strip()


def render_current_scene(*, scene, fetched: dict) -> str:
    """Render a compact "Current Scene" block.

    This is the default context provided to the narrator every turn.
    """

    world_nodes = {w["id"]: w for w in fetched.get("world_nodes", [])}
    actors = {a["id"]: a for a in fetched.get("actors", [])}

    parts: list[str] = []
    parts.append(f"Title: {scene.title}")
    if scene.summary:
        parts.append(f"Summary: {scene.summary}")

    if scene.world_info:
        parts.append("\nWorld Information:\n" + scene.world_info.strip())
    if scene.nearby_info:
        parts.append("\nNearby Locations:\n" + scene.nearby_info.strip())

    if scene.current_node_id and scene.current_node_id in world_nodes:
        w = world_nodes[scene.current_node_id]
        coords = ""
        if w.get("x") is not None and w.get("y") is not None:
            coords = f" (x={w.get('x')}, y={w.get('y')})"
        parts.append(f"\nCurrent Location: {w.get('name')}{coords}")
        if w.get("description"):
            parts.append(w.get("description", ""))
        if w.get("description_long") and w.get("description_long") != w.get("description"):
            parts.append("\n" + w.get("description_long"))

    if scene.npc_ids:
        parts.append("\nKey Characters (Closest):")
        for aid in scene.npc_ids[:10]:
            a = actors.get(aid)
            if not a:
                continue
            prof = a.get("profile") or {}
            header = f"- {a.get('name')} ({a.get('kind','npc')})"
            if prof.get("pronouns"):
                header += f" | {prof['pronouns']}"
            if prof.get("faction"):
                header += f" | Faction: {prof['faction']}"
            parts.append(header)
            if a.get("bio"):
                parts.append(f"  Bio: {a['bio']}")
            for k in ("appearance", "personality", "mannerisms", "goals"):
                if prof.get(k):
                    parts.append(f"  {k.capitalize()}: {prof[k]}")

    return "\n".join([p for p in parts if p])
