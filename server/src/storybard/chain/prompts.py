from __future__ import annotations

import json


def intent_prompt(*, player_text: str, mode: str, recent_turns: list[dict]) -> tuple[str, str]:
    system = (
        "You are the INTENT PARSER for a tabletop RPG engine. Classify the player's "
        "message into a primitive action. You do not narrate, you do not decide outcomes."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(none yet)"
    user = (
        f"MODE: {mode}\n\n"
        f"## Recent exchange (for disambiguating short follow-ups like \"do it again\")\n{recent}\n\n"
        f"PLAYER MESSAGE:\n{player_text}\n\n"
        "primitive is one of: move, speak, interact, inspect, use_item, cast_spell, rest, "
        "wait, attack, unknown. target should be short (a person/place/object), or null if "
        "there isn't one. notes can be an empty list."
    )
    return system, user


def plausibility_prompt(
    *,
    player_text: str,
    intent: dict,
    scene_text: str,
    actor_context: dict,
    campaign_summary: str,
    recent_turns: list[dict],
) -> tuple[str, str]:
    system = (
        "You are the GM judging PLAUSIBILITY. Decide whether the player's stated action is "
        "actually possible given the established scene AND the acting character's actual "
        "capabilities. You do not narrate, you do not decide dice outcomes."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    user = f"""## Current scene
{scene_text}

## Acting character
{json.dumps(actor_context, ensure_ascii=False)}

## Campaign so far
{campaign_summary or "(early in the campaign)"}

## Recent exchange
{recent}

## Player's intent
{json.dumps(intent, ensure_ascii=False)}

## Player message
{player_text}

Rules:
- feasibility=feasible: the action is straightforwardly possible.
- feasibility=feasible_with_twist: possible, but not exactly as stated — say what actually
  happens instead in `twist` (e.g. "you can't fly, but you could climb").
- feasibility=not_feasible: genuinely impossible given the scene; explain why in `reason`.
- time_passed: a short, plain-language estimate of how much in-game time this action takes
  (e.g. "a few seconds," "10 minutes," "3 weeks"). Be honest about it — a short rest is
  hours, "I rest for three weeks" is exactly what it says. Use your best judgment; it
  doesn't need to be precise.
"""
    return system, user


def mechanical_check_prompt(*, player_text: str, plausibility: dict, turn_count: int) -> tuple[str, str]:
    system = (
        "You are the CHECK ADVISOR. Decide whether the player's action needs a dice roll. "
        "You do NOT resolve the roll and you do NOT narrate."
    )
    user = f"""## Plausibility ruling
{json.dumps(plausibility, ensure_ascii=False)}

## Campaign turn count
{turn_count}

## Player message
{player_text}

Rules:
- Only require a roll if the outcome is meaningfully uncertain AND failure would change
  what happens. Talking, looking around, and normal movement are usually no roll.
- If a roll is required, propose a skill and a DC between 5 and 30, with a one-sentence
  reason. Let stakes trend upward as the turn count grows — a deep-campaign challenge
  shouldn't feel as trivial as one at the very start, all else being equal.
"""
    return system, user


def thread_tick_prompt(*, player_text: str, active_clocks: list[dict], recent_turns: list[dict]) -> tuple[str, str]:
    system = (
        "You are THREAD TICK. Given what the player just did (or pointedly ignored), "
        "suggest whether any active clocks should advance. This is advisory — you are not "
        "committing anything, just proposing candidates. Prefer suggesting nothing; most "
        "actions don't move any clock. You do not narrate."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    user = f"""## Active clocks (reference by id — do not invent ids)
{json.dumps(active_clocks, ensure_ascii=False)}

## Recent exchange
{recent}

## Player message
{player_text}

For each clock genuinely affected by this action (or by time passing while it was
ignored), suggest a delta (usually 1, can be negative if this action set the clock back)
and a one-sentence reason. Leave tick_suggestions empty if nothing is affected.
"""
    return system, user


def opportunity_spotting_prompt(
    *,
    player_text: str,
    plausibility: dict,
    active_threads: list[dict],
    scene_text: str,
    actor_context: dict,
    recent_turns: list[dict],
) -> tuple[str, str]:
    system = (
        "You are OPPORTUNITY SPOTTING. Notice when this moment suggests a new narrative "
        "development — especially when the player investigates something with no active "
        "thread attached (curiosity is a trigger: reward it), or when the scene itself "
        "(not just the player's specific action) is already dense with unresolved tension "
        "worth flagging. This is advisory — you are not committing anything, just "
        "proposing candidates. Prefer suggesting nothing when the scene is genuinely "
        "quiet; don't prefer suggesting nothing when it isn't. You do not narrate."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(none yet)"
    user = f"""## Current scene
{scene_text}

## Acting character
{json.dumps(actor_context, ensure_ascii=False)}

## Active threads (reference by id — do not invent ids)
{json.dumps(active_threads, ensure_ascii=False)}

## Plausibility ruling
{json.dumps(plausibility, ensure_ascii=False)}

## Recent exchange
{recent}

## Player message
{player_text}

For each idea, set touches_entity_id to an existing entity's id if it recontextualizes
something already established, or leave it null if it only adds something new. Leave
hook_ideas empty if nothing genuinely warrants it.
"""
    return system, user


def tone_assessment_prompt(
    *,
    player_text: str,
    plausibility: dict,
    mechanical_check: dict,
    previous_tone: dict,
    recent_turns: list[dict],
) -> tuple[str, str]:
    system = (
        "You are TONE ASSESSMENT. Describe the current mood/tension of the scene in your "
        "own words — a short, evocative phrase, not a fixed category (e.g. \"quietly "
        "unsettling,\" \"grim but darkly comic,\" \"triumphant with an undercurrent of "
        "dread\"). This affects narration style only — it never touches mechanics or DCs. "
        "You do not narrate."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    user = f"""## Previous tone
{json.dumps(previous_tone, ensure_ascii=False)}

## Recent exchange
{recent}

## Plausibility ruling
{json.dumps(plausibility, ensure_ascii=False)}

## Mechanical check
{json.dumps(mechanical_check, ensure_ascii=False)}

## Player message
{player_text}

tension is a short free-text phrase describing the mood, not a fixed label. drivers is a
short list of what's driving that assessment (can be empty).
"""
    return system, user


def plan_synthesis_prompt(
    *,
    player_text: str,
    plausibility: dict,
    mechanical_check: dict,
    thread_tick: dict,
    opportunity_spotting: dict,
    tone: dict,
    campaign_summary: str,
    recent_turns: list[dict],
    turns_since_thread_activity: int,
    turn_count: int,
) -> tuple[str, str]:
    system = (
        "You are PLAN SYNTHESIS. Combine everything decided so far into a short beat plan "
        "for the Narrator — what should happen in the next beat, and why. You do not "
        "narrate; you write the plan the Narrator will follow. If it's been several turns "
        "since any thread, clock, or hook moved and the player isn't clearly pursuing an "
        "active goal, the scene is idling — this beat should push a complication rather "
        "than let it drift further. Stakes should feel like they're rising as the campaign "
        "goes on, not resetting cold every turn."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    user = f"""## Campaign so far
{campaign_summary or "(early in the campaign)"}

## Recent exchange
{recent}

## Turns since any thread/clock/hook last moved
{turns_since_thread_activity} (3+ means the scene is idling — consider pushing something)

## Campaign turn count (stakes should trend upward as this grows)
{turn_count}

## Plausibility ruling
{json.dumps(plausibility, ensure_ascii=False)}

## Mechanical check
{json.dumps(mechanical_check, ensure_ascii=False)}

## Thread tick suggestions
{json.dumps(thread_tick, ensure_ascii=False)}

## Opportunity spotting ideas
{json.dumps(opportunity_spotting, ensure_ascii=False)}

## Tone
{json.dumps(tone, ensure_ascii=False)}

## Player message
{player_text}

Write a short (2-4 sentence) plan for the next narration beat.
"""
    return system, user


# Shared between world_update_prompt (mid-play) and seed_content_prompt (campaign
# seeding) — both need the LLM to know exactly what these three ops require. Kept as one
# copy so they can't drift apart, the exact duplication pattern that caused a real bug in
# v1 (a seeder and a world-update prompt independently described "what does creating an
# NPC need" and fell out of sync over time).
_SHARED_DEF_OPS_TEXT = """\
- create_item_def(key, name, description, item_type, properties): a brand-new kind of item
  (not an instance in someone's inventory — just the definition).
- create_spell_def(name, description, level, school, casting_time, range, duration,
  effect): a brand-new spell.
- create_faction(name, description, goals, reputation_baseline): a brand-new organized
  group with its own agenda."""


def world_update_prompt(
    *,
    player_text: str,
    plausibility: dict,
    mechanical_check: dict,
    active_threads: list[dict],
    thread_tick_suggestions: list[dict],
    hook_ideas: list[dict],
    known_actors: list[dict],
    known_locations: list[dict],
    narration: str,
    recent_turns: list[dict],
) -> tuple[str, str]:
    system = (
        "You are the WORLD BUILDER. The Narrator has just written what happened this turn "
        "— read it below. Propose zero or more ops that mutate persistent world state to "
        "match what was actually narrated. \"Prefer nothing\" means don't invent structural "
        "changes an ordinary action doesn't warrant — it does NOT mean defaulting to an "
        "empty list whenever a hook is genuinely there. If Opportunity Spotting proposed a "
        "hook idea below and the narration is consistent with it, that combination is "
        "exactly the signal to act on — turn it into a real propose_hook or "
        "create_major_thread op rather than leaving it as prose alone. Likewise if the "
        "narration introduced a new named NPC, location, item, spell, or faction, that "
        "needs a real op too. Don't leave something that only exists in prose with no "
        "structural existence. You do not narrate."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    user = f"""## What the Narrator just wrote (the primary signal for what to commit)
{narration}

## Recent exchange (for continuity — e.g. don't recreate something from a prior turn)
{recent}

## Active threads (reference by id — do not invent ids)
{json.dumps(active_threads, ensure_ascii=False)}

## Known actors (reference by id — if one of these fits, don't create a duplicate)
{json.dumps(known_actors, ensure_ascii=False)}

## Known locations (reference by id — if one of these fits, don't create a duplicate)
{json.dumps(known_locations, ensure_ascii=False)}

## Plausibility ruling
{json.dumps(plausibility, ensure_ascii=False)}

## Mechanical check
{json.dumps(mechanical_check, ensure_ascii=False)}

## Candidate clock ticks (advisory — from Thread Tick; turn into tick_clock ops if you agree)
{json.dumps(thread_tick_suggestions, ensure_ascii=False)}

## Candidate hooks (advisory — from Opportunity Spotting; turn into propose_hook ops if you agree)
{json.dumps(hook_ideas, ensure_ascii=False)}

## Player message
{player_text}

Available ops — set "op" to exactly one of these and supply only that op's fields:
- create_major_thread(title, summary, owner_type, owner_id): a brand-new independent
  throughline with its own stakes. If the narration surfaced a genuine new mystery,
  threat, or goal (not just atmosphere — a real unresolved question the player could
  pursue), that needs a real thread here, not just prose. Still rare for an ordinary
  action — most things aren't this — but don't withhold one just written into existence.
- create_minor_thread(parent_thread_id, relation, title, summary): a concrete step under
  an existing thread. relation is "prerequisite" (blocks the parent), "alternative" (one of
  several ways to resolve the parent), or "optional_aid" (helps but isn't required).
- add_clock(thread_id, name, segments_total, tick_source, visibility,
  real_time_per_segment): a progress clock on a thread. If tick_source is "time_elapsed",
  set real_time_per_segment to a plain-language duration per segment (e.g. "3 days");
  otherwise leave it null. For a Faction-owned or antagonist-driven thread, prefer
  "time_elapsed" with a real duration so it can keep advancing off-screen between the
  player's turns, not just when they're watching.
- tick_clock(clock_id, segments_delta, reason): advance (or reverse, with a negative delta)
  a clock.
- propose_hook(origin, proposed_text, touches_entity_id): a possible narrative development.
  If the narration surfaced unresolved tension worth remembering (a strange detail, an
  implied secret, something left hanging), propose it here — don't leave real narrative
  tension only in prose with no structural existence. Set touches_entity_id to an existing
  entity's id if this recontextualizes something already established (e.g. revealing a
  named NPC has a secret); leave it null if it only adds something new.
- create_actor(name, kind, bio, current_node_id, current_goal): a brand-new NPC or
  companion the scene just introduced. kind is "npc" or "companion". current_goal is a
  short one-line note on what this character wants right now (null if unclear yet) — this
  is what lets them stay consistent across many future turns instead of being reinvented
  each time. Check known actors first — reference an existing id instead of creating a
  near-duplicate.
- update_actor(actor_id, current_goal, bio): the narration revealed or changed what an
  existing known actor wants, or added to what's known about them. Only set the fields
  that actually changed; leave the other null.
- create_world_node(name, description, parent_node_id, scale, x, y): a brand-new location.
  parent_node_id nests it under an existing location (e.g. a room inside an inn); leave it
  null for a top-level location. Check known locations first — reference an existing id
  instead of creating a near-duplicate.
{_SHARED_DEF_OPS_TEXT}

A linear sequence of steps (do A, then B, then C) is a single thread with a multi-stage
clock, not multiple threads — only give something its own thread when it has genuinely
independent weight (its own pacing, could be tackled out of order, or has its own stakes).
"""
    return system, user


def opening_scene_prompt(*, scene_text: str, actor_context: dict) -> tuple[str, str]:
    system = (
        "You are the NARRATOR opening a brand-new tabletop RPG campaign. Write a short "
        "scene-setting passage that establishes where the player character is and what's "
        "immediately around them — grounded, concrete, spoken-style prose, not purple. "
        "This is the very first thing the player reads; there is no prior action to react "
        "to, so don't wait for one — just open the scene. End on a concrete detail or "
        "sensation, not a question, so the player has something to act on."
    )
    user = f"""## Starting scene
{scene_text}

## Player character
{json.dumps(actor_context, ensure_ascii=False)}

Write the opening passage (roughly 100-150 words).
"""
    return system, user


def campaign_pitch_prompt(*, pitch: str) -> tuple[str, str]:
    system = (
        "You are helping someone start a new tabletop RPG campaign from a short, informal "
        "description of what they want to play. Turn their pitch into concrete campaign "
        "setup fields. You do not narrate."
    )
    user = f"""## Player's pitch
{pitch}

Fill in every field based on this pitch:
- campaign_name: a short, evocative name for the campaign itself.
- world_name: a name for the starting location/region.
- world_description: 2-4 sentences expanding the pitch into a concrete starting scene.
- inspiration_tags: 2-4 short tags capturing the pitch's influences/tone.
- races_classes_mode: "standard_5e" if the pitch reads as generic/classic fantasy (so the
  campaign can reuse the standard races and classes with no extra generation needed);
  "generate" if the pitch's setting is distinctive enough to warrant bespoke ones (sci-fi,
  a strong theme, an unusual world).
- narrator_style_description: a short phrase describing a narration style that matches the
  pitch's tone (e.g. "grim and spare," "warm and whimsical").
- player_actor_name: a fitting name for the player's starting character.
- must_include: 1-3 short story hooks or elements implied by the pitch that the campaign
  should weave in early. Leave empty if the pitch doesn't clearly imply any.
"""
    return system, user


def seed_content_prompt(
    *, world_description: str, inspiration_tags: list[str], must_include: list[str]
) -> tuple[str, str]:
    system = (
        "You are generating the starting content for a brand-new tabletop RPG campaign "
        "world. Propose a set of ops that create the playable races, classes, starting "
        "items, spells, and (at most) one faction for this world. You do not narrate."
    )
    user = f"""## World description
{world_description}

## Inspiration tags
{json.dumps(inspiration_tags, ensure_ascii=False)}

## Must-include elements (weave these in if relevant)
{json.dumps(must_include, ensure_ascii=False)}

Generate exactly 4 ancestries, 4 classes, 6 items (a mix of weapons/armor/gear), 4 spells,
and at most 1 faction — tailored to this world's tone, not generic fantasy filler unless
the world description itself is generic fantasy. Every class's primary_attribute_key must
be one of: str, dex, con, int, wis, cha (this campaign's fixed attribute keys).

Available ops — set "op" to exactly one of these and supply only that op's fields:
- create_ancestry_def(key, name, description, speed, features): a playable ancestry/race.
  features is a small freeform dict (e.g. darkvision, resistances).
- create_class_def(key, name, description, hit_die, primary_attribute_key, proficiencies,
  spellcasting, starting_equipment): a playable class.
{_SHARED_DEF_OPS_TEXT}
"""
    return system, user


def memory_regression_prompt(*, player_text: str, narration: str, previous_summary: str) -> tuple[str, str]:
    system = (
        "You are MEMORY REGRESSION. Extract durable facts the acting character would "
        "remember from what just happened, and rewrite the campaign's rolling summary to "
        "reflect where the story stands now. Prefer proposing no new memories; not every "
        "turn is memorable, but the summary should always be rewritten, even if only "
        "slightly, since it's the GM's main long-horizon memory of the campaign. You do "
        "not narrate."
    )
    user = f"""## Previous campaign summary
{previous_summary or "(none yet — this is early in the campaign)"}

## Player message
{player_text}

## What happened
{narration}

For each memory worth keeping, give a short title (or null), the memory text, and
importance 1-5 (5 = pivotal, 1 = trivial). Leave memories empty if nothing is worth
remembering.

campaign_summary_update: a fresh 2-4 sentence rewrite of the previous summary, folding in
what just happened. Keep it compressed — this is a standing "story so far," not a
turn-by-turn log. If nothing changed the overall picture, the rewrite can be very close to
the previous summary.
"""
    return system, user


def narrator_prompt(
    *,
    player_text: str,
    plausibility: dict,
    mechanical_check: dict,
    plan: str,
    tone: dict,
    style_description: str,
    verbosity_words: float,
    scene_text: str,
    actor_context: dict,
    recent_turns: list[dict],
    relevant_memories: list[dict],
    known_actors: list[dict],
    known_locations: list[dict],
    recent_world_events: list[dict],
    campaign_summary: str,
) -> tuple[str, str]:
    system = (
        "You are the NARRATOR for a tabletop RPG campaign. Write short, spoken-style prose "
        "by default — concrete and grounded, not purple. You do not invent canon beyond "
        "what's provided. Follow the plan for pacing, and let the tone shape how sharp or "
        "gentle your language is — tone only ever affects prose, never mechanics. Stay "
        "consistent with the current scene, the acting character, and what just happened. "
        "When a character speaks, render it as actual dialogue in quotation marks — don't "
        "just describe that they spoke or evade with body language alone. If you introduce "
        "an NPC or location that isn't in the known lists below, that's fine — the World "
        "Builder will create it structurally right after you; you don't need to hold back. "
        "If a recent world change hasn't been reflected in the story yet, look for a "
        "natural moment to surface it — consequences should eventually be felt, not stay "
        "invisible."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    memories = "\n".join(f"- {m['text']}" for m in relevant_memories) or "(none yet)"
    world_events = "\n".join(
        f"- {e['op']}: {e['reason']}" for e in recent_world_events
    ) or "(nothing recent)"
    user = f"""## Style
{style_description or "Plain, direct, spoken-style."}
Target length: roughly {int(verbosity_words)} words.

## Current scene
{scene_text}

## Campaign so far
{campaign_summary or "(early in the campaign)"}

## Acting character
{json.dumps(actor_context, ensure_ascii=False)}

## Known actors (reference these by name if relevant — don't rename or duplicate them)
{json.dumps(known_actors, ensure_ascii=False)}

## Known locations (reference these by name if relevant — don't rename or duplicate them)
{json.dumps(known_locations, ensure_ascii=False)}

## What this character remembers
{memories}

## Recent world changes (things that happened — not necessarily narrated yet)
{world_events}

## Recent exchange
{recent}

## Plan for this beat
{plan}

## Tone
{json.dumps(tone, ensure_ascii=False)}

## Plausibility ruling
{json.dumps(plausibility, ensure_ascii=False)}

## Mechanical check
{json.dumps(mechanical_check, ensure_ascii=False)}

## Player message
{player_text}

Narrate what happens next.
"""
    return system, user
