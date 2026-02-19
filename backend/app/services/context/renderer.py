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
