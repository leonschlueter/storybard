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
    scene: dict | None = None,
) -> tuple[str, str]:
    system = (
        "You are the GM judging PLAUSIBILITY. Decide whether the player's stated action is "
        "actually possible given the established scene AND the acting character's actual "
        "capabilities. Use who's actually present (below) to judge claims about other "
        "characters — an action aimed at someone not physically here is not feasible as "
        "stated. You do not narrate, you do not decide dice outcomes."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    actors_present = (scene or {}).get("actors_present", [])
    present_section = (
        f"\n## Who's actually here\n{json.dumps(actors_present, ensure_ascii=False)}\n"
        if actors_present
        else ""
    )
    user = f"""## Current scene
{scene_text}
{present_section}
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


def mechanical_check_prompt(
    *,
    player_text: str,
    plausibility: dict,
    turn_count: int,
    intent: dict | None = None,
    degrees_of_success: bool = True,
) -> tuple[str, str]:
    system = (
        "You are the CHECK ADVISOR. Decide whether the player's action needs a dice roll. "
        "You do NOT resolve the roll and you do NOT narrate. A meta/out-of-character "
        "message — asking what's going on, asking for a recap, addressing the GM directly "
        "rather than acting in the fiction — never needs a roll, no matter how confusing "
        "the situation is in-world; only an actual attempted action can require one."
    )
    degrees_note = (
        "\n- Write the reason with headroom for texture, not just pass/fail: note what a "
        "narrow success vs. a clean success vs. a costly failure would each look like, so "
        "the Narrator can render the actual roll with texture rather than a flat "
        "success/failure (feature #16, degrees of success)."
        if degrees_of_success
        else ""
    )
    user = f"""## Intent
{json.dumps(intent or {}, ensure_ascii=False)}

## Plausibility ruling
{json.dumps(plausibility, ensure_ascii=False)}

## Campaign turn count
{turn_count}

## Player message
{player_text}

Rules:
- If intent's primitive is "unknown," or the message otherwise isn't an attempted in-fiction
  action (a question, a meta comment, an OOC request), set roll_required to false — there is
  nothing being attempted that a roll could apply to.
- Only require a roll if the outcome is meaningfully uncertain AND failure would change
  what happens. Talking, looking around, and normal movement are usually no roll.
- If a roll is required, propose the ability it should be resolved against (skill: one of
  str/dex/con/int/wis/cha — whichever most directly governs the attempt) and a DC between 5
  and 30, with a one-sentence reason. Let stakes trend upward as the turn count grows — a
  deep-campaign challenge shouldn't feel as trivial as one at the very start, all else being
  equal.{degrees_note}
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
    scene: dict | None = None,
) -> tuple[str, str]:
    system = (
        "You are OPPORTUNITY SPOTTING. Notice when this moment suggests a new narrative "
        "development — especially when the player investigates something with no active "
        "thread attached (curiosity is a trigger: reward it), or when the scene itself "
        "(not just the player's specific action) is already dense with unresolved tension "
        "worth flagging. Check the due beats below first — if one already covers this "
        "moment, that's Plan Synthesis's job to surface, not a new idea to propose here. "
        "This is advisory — you are not committing anything, just proposing candidates. "
        "Prefer suggesting nothing when the scene is genuinely quiet; don't prefer "
        "suggesting nothing when it isn't. You do not narrate."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(none yet)"
    due_beats = (scene or {}).get("due_beats", [])
    beats_section = (
        f"\n## Already-planned beats due in this scene (don't duplicate these)\n"
        f"{json.dumps(due_beats, ensure_ascii=False)}\n"
        if due_beats
        else ""
    )
    user = f"""## Current scene
{scene_text}
{beats_section}
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
    roll_resolution: dict | None = None,
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
{f"## Roll result{chr(10)}{json.dumps(roll_resolution, ensure_ascii=False)}{chr(10)}" if roll_resolution else ""}
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
    roll_resolution: dict | None = None,
    active_threads: list[dict] | None = None,
    scene: dict | None = None,
    actor_context: dict | None = None,
) -> tuple[str, str]:
    system = (
        "You are PLAN SYNTHESIS. Combine everything decided so far into a short beat plan "
        "for the Narrator — what should happen in the next beat, and why. Write it as a "
        "director's note (\"X should happen, revealing Y, because Z\"), not as prose someone "
        "could mistake for finished narration — the Narrator dramatizes this into an actual "
        "scene with dialogue and sensory detail; your job is the instruction, not the "
        "performance. Root the beat in who the acting character actually is (below) — "
        "their motivation and stakes, not just the mechanics of the moment. You do not "
        "narrate; you write the plan the Narrator will follow. Prefer advancing one of the "
        "active threads below over inventing something unrelated — if a due beat is listed "
        "for the current scene, that is exactly the kind of thing this plan should push "
        "toward, not a coincidence to ignore. If it's been several turns since any thread, "
        "clock, or hook moved and the player isn't clearly pursuing an active goal, the "
        "scene is idling — this beat should push a complication rather than let it drift "
        "further. Stakes should feel like they're rising as the campaign goes on, not "
        "resetting cold every turn. If a roll happened this turn, the plan must be honest "
        "about its actual outcome — don't plan around success if the roll failed, or "
        "around failure if it succeeded."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    user = f"""## Campaign so far
{campaign_summary or "(early in the campaign)"}

## Acting character (root the beat in who they are, not just the mechanics)
{json.dumps(actor_context or {}, ensure_ascii=False)}

## Active threads (what's actually in motion in this campaign)
{json.dumps(active_threads or [], ensure_ascii=False)}

## Current scene (who's here, and which threads have a beat due here)
{json.dumps(scene or {}, ensure_ascii=False)}

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
{f"## Roll result{chr(10)}{json.dumps(roll_resolution, ensure_ascii=False)}{chr(10)}" if roll_resolution else ""}
## Thread tick suggestions
{json.dumps(thread_tick, ensure_ascii=False)}

## Opportunity spotting ideas
{json.dumps(opportunity_spotting, ensure_ascii=False)}

## Tone
{json.dumps(tone, ensure_ascii=False)}

## Player message
{player_text}

Write a short (2-4 sentence) plan for the next narration beat, as a director's note — not
prose the Narrator could mistake for a finished scene and copy verbatim.
"""
    return system, user


# Used by world_update_prompt (mid-play) — item/spell/faction defs are also available
# there. seed_content_prompt (campaign seeding's mechanical-content call) describes
# create_item_def/create_spell_def inline instead of sharing this block: it no longer
# offers create_faction (faction seeding moved to seed_narrative_prompt, feature #6), so
# reusing the exact same three-op block would misdescribe what's actually on offer there.
_SHARED_DEF_OPS_TEXT = """\
- create_item_def(key, name, description, item_type, properties): a brand-new kind of item
  (not an instance in someone's inventory — just the definition).
- create_spell_def(name, description, level, school, casting_time, range, duration,
  effect): a brand-new spell.
- create_faction(name, description, goals, reputation_baseline): a brand-new organized
  group with its own agenda."""


def npc_offscreen_prompt(
    *, npc_name: str, npc_goal: str | None, thread_title: str, thread_summary: str
) -> tuple[str, str]:
    """/world-tick's NPC simulation call (feature #11) — a short off-screen beat for an
    NPC who owns an active Thread, run while the player isn't watching. Its output is
    appended as a clause to Campaign.summary (api/turns.py::world_tick), reusing the
    rolling-summary plumbing every prompt that already reads campaign_summary picks up
    for free — no new context-threading needed."""
    system = (
        "You are simulating what an NPC does while unwatched by the player. Write ONE "
        "short, concrete beat describing what this character does to advance their own "
        "agenda — this happens off-screen, so it should feel like real progress, not "
        "empty flavor. You do not narrate a scene; this is a compressed summary of an "
        "event, not prose to be read aloud."
    )
    user = f"""## NPC
{npc_name} — current goal: {npc_goal or "(not specified)"}

## The thread they're pursuing
{thread_title}: {thread_summary}

Write one short (1-2 sentence) event describing what {npc_name} did.
"""
    return system, user


def twist_prompt(
    *,
    player_text: str,
    plan: str,
    campaign_summary: str,
    recent_turns: list[dict],
    active_threads: list[dict],
    actor_context: dict | None = None,
    scene: dict | None = None,
) -> tuple[str, str]:
    """A low-frequency complication, separate from Plan Synthesis's every-turn beat
    planning (feature #12) — only reached on a conditional edge
    (chain/graph.py::_route_after_plan_synthesis), gated by narration_twist_frequency, so
    it can afford to be bolder than routine pacing without every turn escalating."""
    system = (
        "You are the TWIST node. This is a rare beat, not a routine one — you only run "
        "every few turns. Introduce ONE genuine complication that recontextualizes the "
        "current situation: a reversal, a hidden cost, an unexpected consequence of "
        "something already established, or a new piece of information that changes the "
        "stakes. A complication that lands on the acting character's own stakes (below) "
        "cuts deeper than a generic one. This should feel earned from what's already in "
        "the campaign, not arbitrary or disconnected. You do not narrate — the Narrator "
        "will fold your complication into the actual prose."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    due_beats = (scene or {}).get("due_beats", [])
    beats_section = (
        f"\n## Planned beats due in this scene (a complication that touches one lands harder)\n"
        f"{json.dumps(due_beats, ensure_ascii=False)}\n"
        if due_beats
        else ""
    )
    user = f"""## Campaign so far
{campaign_summary or "(early in the campaign)"}

## Acting character
{json.dumps(actor_context or {}, ensure_ascii=False)}

## Active threads (a complication tied to one of these lands harder than one from nowhere)
{json.dumps(active_threads, ensure_ascii=False)}
{beats_section}
## Recent exchange
{recent}

## Plan Synthesis's beat plan for this turn (your complication augments this, doesn't replace it)
{plan}

## Player message
{player_text}

Write one short (1-3 sentence) complication.
"""
    return system, user


def world_update_prompt(
    *,
    player_text: str,
    plausibility: dict,
    mechanical_check: dict,
    active_threads: list[dict],
    active_clocks: list[dict],
    thread_tick_suggestions: list[dict],
    hook_ideas: list[dict],
    known_actors: list[dict],
    known_locations: list[dict],
    narration: str,
    recent_turns: list[dict],
    roll_resolution: dict | None = None,
    acting_actor_id: str | None = None,
    scene: dict | None = None,
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
        "structural existence. If a real roll happened this turn and it was a narrow or "
        "critical failure, the character should usually pay a concrete cost — apply_damage "
        "or apply_condition — not just a scarier sentence; a critical success can likewise "
        "warrant a genuine advantage, not only flavor text. You do not narrate."
    )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    roll_section = (
        f"\n## Roll result this turn (the acting character's id is {acting_actor_id})\n"
        f"{json.dumps(roll_resolution, ensure_ascii=False)}\n"
        if roll_resolution
        else ""
    )
    user = f"""## What the Narrator just wrote (the primary signal for what to commit)
{narration}
{roll_section}

## Recent exchange (for continuity — e.g. don't recreate something from a prior turn)
{recent}

## Active threads (reference by id — do not invent ids)
{json.dumps(active_threads, ensure_ascii=False)}

## Current scene (who's here, and which threads have a beat due right here — if the
## narration delivered one of these, fire it with fire_beat; if it was skipped, consider
## abandon_beat, and pair a real consequence op if one is warranted)
{json.dumps(scene or {}, ensure_ascii=False)}

## Active clocks (the ONLY valid clock_id values for tick_clock — do not invent one)
{json.dumps(active_clocks, ensure_ascii=False)}

## Known actors (campaign-wide, for dedup — reference by id if one of these fits, don't
## create a duplicate; present=true/false is about the current scene, not about whether
## they're eligible to reference here)
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
- create_major_thread(title, summary, owner_type, owner_id, initial_beats): a brand-new
  independent throughline with its own stakes. If the narration surfaced a genuine new
  mystery, threat, or goal (not just atmosphere — a real unresolved question the player
  could pursue), that needs a real thread here, not just prose. Still rare for an ordinary
  action — most things aren't this — but don't withhold one just written into existence.
  initial_beats: 0-4 concrete planned next steps (each: description, location_id — a real
  known location's id, or null to apply anywhere) when the thread already has enough shape
  to stage a few; an empty list is fine and often correct for a thread that's still just a
  premise.
- create_minor_thread(parent_thread_id, relation, title, summary, initial_beats): a
  concrete step under an existing thread. relation is "prerequisite" (blocks the parent),
  "alternative" (one of several ways to resolve the parent), or "optional_aid" (helps but
  isn't required). initial_beats same as above.
- fire_beat(beat_id, reason): a planned beat (see the current scene's due_beats above) was
  actually delivered by the narration just written — mark it fired so it stops being
  suggested again.
- abandon_beat(beat_id, reason): a due beat was clearly skipped, not delivered. Marks it so
  rather than leaving it to decay silently — pair with a real consequence op (propose_hook,
  apply_condition, tick_clock, ...) in this same batch if skipping it should cost something.
- add_clock(thread_id, name, segments_total, tick_source, visibility,
  real_time_per_segment): a progress clock on a thread. If tick_source is "time_elapsed",
  set real_time_per_segment to a plain-language duration per segment (e.g. "3 days");
  otherwise leave it null. For a Faction-owned or antagonist-driven thread, prefer
  "time_elapsed" with a real duration so it can keep advancing off-screen between the
  player's turns, not just when they're watching.
- tick_clock(clock_id, segments_delta, reason): advance (or reverse, with a negative delta)
  a clock. clock_id must be a real id from the active threads' clocks above — if the thing
  you want to advance doesn't have a real clock yet (it's only ever existed in prose),
  create it first with create_major_thread + add_clock instead of inventing an id; a
  made-up clock_id is silently rejected, not created.
- propose_hook(origin, proposed_text, touches_entity_id): a possible narrative development.
  If the narration surfaced unresolved tension worth remembering (a strange detail, an
  implied secret, something left hanging), propose it here — don't leave real narrative
  tension only in prose with no structural existence. Set touches_entity_id to an existing
  entity's id if this recontextualizes something already established (e.g. revealing a
  named NPC has a secret); leave it null if it only adds something new.
- create_actor(name, kind, bio, current_node_id, current_goal, speech_style): a brand-new
  NPC or companion the scene just introduced. kind is "npc" or "companion". bio: a real 2-4
  sentence sketch (not a one-line tag) — what the narration actually established about them
  plus enough texture (a physical/behavioral detail, their place here, a hint of something
  beneath the surface) that they read as a specific person, not a placeholder. current_goal
  is a short one-line note on what this character wants right now (null if unclear yet) —
  this is what lets them stay consistent across many future turns instead of being
  reinvented each time. speech_style: if the narration gave this character actual dialogue,
  capture how they talk (vocabulary, cadence, a verbal tic) in a short phrase so future
  turns keep them sounding like themselves; null if they haven't spoken yet. Check known
  actors first — reference an existing id instead of creating a near-duplicate.
- update_actor(actor_id, current_goal, bio, speech_style): the narration revealed or changed something
  DURABLE about an existing known actor — a new standing motivation, a fact about who
  they are that's now known. Only set the fields that actually changed; leave the other
  null. Do NOT use this to log what just happened in this scene ("is now confronting the
  player," "has just been told X") — that's transient and belongs in the narration/recent
  events, not in a field the Narrator will read as this character's standing state in
  every future scene. Write current_goal/bio as they'll still read true several turns
  from now, once this scene is over. IMPORTANT: if the known actors list below shows a
  character with speech_style still null who just spoke in the narration, this is the
  moment to fix that — set speech_style to how they actually talked, even if nothing else
  about them changed. Don't let a character keep talking turn after turn with no voice on
  record.
- create_world_node(name, description, parent_node_id, scale, x, y): a brand-new location.
  parent_node_id nests it under an existing location (e.g. a room inside an inn); leave it
  null for a top-level location. Check known locations first — reference an existing id
  instead of creating a near-duplicate.
- apply_damage(actor_id, amount, reason): a real mechanical cost to a character's HP.
  Positive amount damages, negative heals. Use the real actor id — the acting character's
  id is given above when a roll happened.
- apply_condition(actor_id, condition, active, note): apply (active=true) or clear
  (active=false) a short status tag (e.g. "shaken", "poisoned", "cursed") on a character.
{_SHARED_DEF_OPS_TEXT}

A linear sequence of steps (do A, then B, then C) is a single thread with a multi-stage
clock, not multiple threads — only give something its own thread when it has genuinely
independent weight (its own pacing, could be tackled out of order, or has its own stakes).
"""
    return system, user


def opening_scene_prompt(
    *, scene_text: str, actor_context: dict, personal_stakes: str | None = None
) -> tuple[str, str]:
    system = (
        "You are the NARRATOR opening a brand-new tabletop RPG campaign. Write a short "
        "scene-setting passage that establishes where the player character is and what's "
        "immediately around them — grounded, concrete, spoken-style prose, not purple. "
        "This is the very first thing the player reads; there is no prior action to react "
        "to, so don't wait for one — just open the scene. End on a concrete detail or "
        "sensation, not a question, so the player has something to act on."
    )
    stakes_section = (
        f"\n## Why this character is here\n{personal_stakes}\n" if personal_stakes else ""
    )
    user = f"""## Starting scene
{scene_text}

## Player character
{json.dumps(actor_context, ensure_ascii=False)}
{stakes_section}
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
- calendar_context: a short phrase for when the campaign opens (e.g. "early winter, three
  days before the harvest festival," "the night of a lunar eclipse"). Invent something
  fitting if the pitch doesn't specify a time — never leave this blank.
"""
    return system, user


def seed_content_prompt(
    *, world_description: str, inspiration_tags: list[str], must_include: list[str]
) -> tuple[str, str]:
    system = (
        "You are generating the starting mechanical content for a brand-new tabletop RPG "
        "campaign world. Propose a set of ops that create the playable races, classes, "
        "starting items, and spells for this world. You do not narrate."
    )
    user = f"""## World description
{world_description}

## Inspiration tags
{json.dumps(inspiration_tags, ensure_ascii=False)}

## Must-include elements (weave these in if relevant)
{json.dumps(must_include, ensure_ascii=False)}

Generate exactly 4 ancestries, 4 classes, 6 items (a mix of weapons/armor/gear), and 4
spells — tailored to this world's tone, not generic fantasy filler unless the world
description itself is generic fantasy. Every class's primary_attribute_key must be one
of: str, dex, con, int, wis, cha (this campaign's fixed attribute keys).

Naming and flavor text tailored to the setting isn't enough on its own — the mechanical
`features`/`proficiencies` underneath need to earn that flavor, not just relabel a generic
bonus (a reskinned "+1 to social checks" or "immune to poison" on every ancestry reads as
random no matter how evocative the name is). Push each ancestry/class toward a feature
that's actually specific to this world's premise and that the others don't have — if two
of the four classes would play almost identically with the names swapped, rework one of
them. At least one class should meaningfully diverge from "generic fighter/rogue/wizard
with a reskin" in what it actually lets a player do at the table.

Available ops — set "op" to exactly one of these and supply only that op's fields:
- create_ancestry_def(key, name, description, speed, features): a playable ancestry/race.
  features is a small freeform dict (e.g. darkvision, resistances) — make at least one
  feature per ancestry something distinctive to this world's premise, not a stock bonus.
- create_class_def(key, name, description, hit_die, primary_attribute_key, proficiencies,
  spellcasting, starting_equipment): a playable class.
- create_item_def(key, name, description, item_type, properties): a brand-new kind of item
  (not an instance in someone's inventory — just the definition).
- create_spell_def(name, description, level, school, casting_time, range, duration,
  effect): a brand-new spell.
"""
    return system, user


def seed_narrative_prompt(
    *,
    world_name: str,
    world_description: str,
    inspiration_tags: list[str],
    must_include: list[str],
    npc_count: int,
    hook_count: int,
    rumor_count: int,
    npc_relationships: bool,
    location_depth: int,
    include_faction: bool,
    include_planted_reveal: bool,
    player_actor_name: str,
) -> tuple[str, str]:
    """Campaign Seeding's narrative-content call — NPCs, Hooks, a rumor board, an optional
    background Faction, optional child locations, and an optional GM-only planted reveal.
    Always called (unlike seed_content_prompt's races/classes/items/spells, which only
    runs in "generate" mode) — narrative content isn't mechanical content. See
    chain/ops.py's SeedNarrativeOp/SeedNarrativeOut and the "All 20 Features" plan.
    """
    system = (
        "You are generating the starting narrative content for a brand-new tabletop RPG "
        "campaign. Propose NPCs, hooks, and other narrative seeds that make this world "
        "feel alive and lived-in from turn one — not a blank slate the player has to "
        "generate all the momentum for themselves. You do not narrate."
    )
    relationship_note = (
        "At least a couple of the NPCs should reference each other by name in their bio "
        "— a rivalry, a debt, an alliance, a shared history — so the cast feels "
        "interconnected, not like isolated character sheets."
        if npc_relationships
        else "NPC bios don't need to reference each other."
    )
    location_note = (
        f"Also propose {max(location_depth - 1, 1)} child location(s) nested under the "
        f"starting location (a couple of named landmarks or districts within "
        f"'{world_name}') — set their parent_node_id to exactly '{world_name}' (the "
        f"starting location's own name, used as a placeholder id at this stage)."
        if location_depth >= 2
        else "Do not propose any locations — the starting location already exists."
    )
    faction_note = (
        "Include exactly one create_faction op for a background organized group with its "
        "own agenda, distinct from any faction already implied by the world description."
        if include_faction
        else "Do not propose a faction."
    )
    reveal_note = (
        "Also propose one planted_reveal: a hidden connection between two of the things "
        "you're seeding here (e.g. two NPCs share a secret, or an NPC is secretly tied to "
        "a hook) that isn't stated anywhere in the public content above — something a GM "
        "could surface later as a twist. This is never shown to the player."
        if include_planted_reveal
        else "Set planted_reveal to null."
    )
    threads_note = (
        f"For EACH of the {len(must_include)} must-include elements above, propose one "
        "create_major_thread op — never copy the wish text verbatim into title/summary. "
        "Write a short, evocative title distinct from the summary, and a real 2-4 "
        "sentence summary that gives it actual shape (who's involved, what's at stake, "
        "why it matters now) — the wish is the seed of the idea, not the finished thread. "
        "Also stage 2-4 initial_beats: concrete planned steps this thread could take, "
        "each with a location_id (the starting location's name, or a child location's "
        "name if you proposed any, or null to apply anywhere). If more than one thread is "
        "being created, make them genuinely distinct from each other, not the same "
        "conflict wearing different flavor text — vary WHO drives each one (don't let "
        "every thread orbit the same one or two NPCs if you have more than a couple in "
        "the cast), vary the SHAPE of the stakes (a ticking clock, a hidden betrayal, a "
        "moral tradeoff, a rescue, a heist — not three copies of \"expose the corruption "
        "or let it stand\"), and vary the RESOURCE or domain each thread is actually about. "
        "A player should be able to summarize what makes each thread different in one "
        "sentence; if two threads would get the same sentence, that's a sign to rework one "
        "of them, not just its wording."
        if must_include
        else ""
    )
    user = f"""## World
{world_name}: {world_description}

## Inspiration tags
{json.dumps(inspiration_tags, ensure_ascii=False)}

## The player character's name (already taken — do not reuse it for any NPC)
{player_actor_name}

## Must-include elements (each becomes a real, elaborated thread — see below)
{json.dumps(must_include, ensure_ascii=False)}

Generate exactly {npc_count} NPCs (create_actor, kind="npc"), {hook_count} real hooks
(propose_hook, origin="seed") and {rumor_count} rumors (propose_hook, origin="rumor" —
some should be true, some misleading; rumors are lower-stakes gossip, distinct in tone
from a real hook). {relationship_note} {location_note} {faction_note} {reveal_note}
{threads_note}

Never give an NPC the same name as the player character ({player_actor_name}) — a name
collision means the Narrator ends up describing the same name as both "you" and a separate
third-person figure in the same scene.

For every create_actor, write bio as a real 3-5 sentence character sketch, not a one-line
tag — cover a concrete physical/behavioral detail (something you'd actually notice meeting
them), their place in this world (a trade, a role, a reason they're here), and something
that isn't obvious from the first sentence (a regret, a debt, a secret ambition, a
contradiction). A bio that could belong to any generic NPC in any generic setting is a
failure; it should only fit this specific character. Give current_goal a real one-line
motivation, speech_style a short concrete note on how they actually talk (vocabulary,
cadence, a verbal tic — not a restatement of their personality or backstory), and set
current_node_id to whichever location this character is actually described as being at —
'{world_name}' (the starting location) itself if their bio doesn't point anywhere more
specific, or the exact name of one of the child locations you're proposing above if it
does (e.g. someone whose bio says they operate from a hidden district belongs AT that
district, not at the top-level kingdom/city). Don't default every NPC to the starting
location out of convenience — spreading the cast across the real locations you just
created is what makes this world read as populated rather than a single named point.
Leave touches_entity_id null on every hook/rumor — nothing else seeded here has a real id
yet for them to reference.

Available ops — set "op" to exactly one of these and supply only that op's fields:
- create_actor(name, kind, bio, current_node_id, current_goal, speech_style): kind is
  always "npc" here.
- propose_hook(origin, proposed_text, touches_entity_id): origin is "seed" or "rumor" as
  described above; touches_entity_id always null.
- create_faction(name, description, goals, reputation_baseline): only if requested above.
- create_world_node(name, description, parent_node_id, scale, x, y): only if requested
  above; parent_node_id is the parent location's name (see above), scale is a short word
  like "district" or "landmark", x/y can be null.
- create_major_thread(title, summary, owner_type, owner_id, initial_beats): one per
  must-include element, per the instructions above. owner_type is "campaign" and
  owner_id is null unless it clearly belongs to an NPC or faction you're also proposing
  (in which case you still can't reference their id yet — leave owner_type "campaign").
"""
    return system, user


def memory_regression_prompt(
    *,
    player_text: str,
    narration: str,
    previous_summary: str,
    known_actors: list[dict] | None = None,
    track_npc_impressions: bool = False,
) -> tuple[str, str]:
    system = (
        "You are MEMORY REGRESSION. Extract durable facts the acting character would "
        "remember from what just happened, and rewrite the campaign's rolling summary to "
        "reflect where the story stands now. Prefer proposing no new memories; not every "
        "turn is memorable, but the summary should always be rewritten, even if only "
        "slightly, since it's the GM's main long-horizon memory of the campaign. You do "
        "not narrate."
    )
    npc_section = ""
    if track_npc_impressions:
        actors_json = json.dumps(known_actors or [], ensure_ascii=False)
        npc_section = f"""
## Known NPCs (reference by id — do not invent one)
{actors_json}

For each NPC who was actually present and formed or updated an impression of the acting
character this turn, add an entry to npc_impressions: npc_actor_id (a real id from the
list above) and a one-line text note on what that NPC now thinks. Leave npc_impressions
empty if no NPC present had reason to form a new impression.
"""
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
{npc_section}"""
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
    npc_impressions: list[dict] | None = None,
    mechanical_texture: bool = True,
    twist: str | None = None,
    roll_resolution: dict | None = None,
    active_threads: list[dict] | None = None,
    scene: dict | None = None,
) -> tuple[str, str]:
    system = (
        "You are the NARRATOR for a tabletop RPG campaign. Write short, spoken-style prose "
        "by default — concrete and grounded, not purple. You do not invent canon beyond "
        "what's provided. The plan below is a compressed director's note describing what "
        "should happen — it is NOT finished prose. Never copy it verbatim or near-verbatim "
        "into your narration, even when its wording already sounds scene-like; your job is "
        "to dramatize it: real sensory detail, real dialogue in quotation marks, the "
        "specific acting character's own actions and sensations — not a summary of events. "
        "If what you're about to write reads like a synopsis rather than a scene someone is "
        "standing inside, rewrite it. Follow the plan for pacing, and let the tone shape "
        "how sharp or gentle your language is — tone only ever affects prose, never "
        "mechanics. Stay consistent with the current scene, the acting character, and what "
        "just happened. "
        "When a character speaks, render it as actual dialogue in quotation marks — don't "
        "just describe that they spoke or evade with body language alone. Give each known "
        "NPC a distinct voice using their speech_style below (vocabulary, cadence, verbal "
        "tics) if it's set — two different NPCs should not sound interchangeable. If "
        "speech_style is null for a character who speaks, invent something consistent "
        "with their bio and keep it consistent turn to turn. If you introduce "
        "an NPC or location that isn't in the known lists below, that's fine — the World "
        "Builder will create it structurally right after you; you don't need to hold back. "
        "Each known actor below has a `present` flag — only actors with present=true are "
        "physically in this scene right now. An actor with present=false exists in the "
        "campaign but is NOT here; don't have them speak or act in this scene, and don't "
        "narrate them as having been quietly present all along — if the plan calls for "
        "them, give them a real entrance instead. If a recent world change hasn't been "
        "reflected in the story yet, look for a natural moment to surface it — "
        "consequences should eventually be felt, not stay invisible."
    )
    if mechanical_texture:
        system += (
            " When a roll happens, render the outcome with texture, not a flat pass/fail — "
            "a narrow success can cost something, a clean success can feel effortless, a "
            "failure can still move the story forward (fail-forward) rather than just "
            "stopping it; use the check advisor's reasoning below for what that looks like "
            "here."
        )
    if roll_resolution:
        system += (
            " A real roll happened this turn (see the roll result below) — you MUST narrate "
            "its actual outcome truthfully. Never describe a clean, guaranteed success if "
            "the roll failed, and never invent unnecessary struggle if it clearly succeeded."
        )
    recent = "\n".join(
        f"- Player: {t['player_text']}\n  Narrator: {t['narration']}" for t in recent_turns
    ) or "(this is the first turn)"
    memories = "\n".join(f"- {m['text']}" for m in relevant_memories) or "(none yet)"
    world_events = "\n".join(
        f"- {e['op']}: {e['reason']}" for e in recent_world_events
    ) or "(nothing recent)"
    impressions_section = ""
    if npc_impressions:
        impressions = "\n".join(f"- {i['npc_name']}: {i['text']}" for i in npc_impressions)
        impressions_section = f"\n## What NPCs remember about this character\n{impressions}\n"
    due_beats = (scene or {}).get("due_beats", [])
    beats_section = ""
    if due_beats:
        beats = "\n".join(f"- ({b['thread_title']}) {b['description']}" for b in due_beats)
        beats_section = f"\n## Planned beats due in this scene (weave one in if it fits naturally)\n{beats}\n"
    user = f"""## Style
{style_description or "Plain, direct, spoken-style."}
Target length: roughly {int(verbosity_words)} words.

## Current scene
{scene_text}

## Active threads (the campaign's real ongoing throughlines)
{json.dumps(active_threads or [], ensure_ascii=False)}
{beats_section}
## Campaign so far
{campaign_summary or "(early in the campaign)"}

## Acting character
{json.dumps(actor_context, ensure_ascii=False)}

## Known actors (present=true means physically here now; present=false means they exist
## in the campaign but are elsewhere — reference these by name if relevant, don't rename
## or duplicate them)
{json.dumps(known_actors, ensure_ascii=False)}

## Known locations (reference these by name if relevant — don't rename or duplicate them)
{json.dumps(known_locations, ensure_ascii=False)}

## What this character remembers
{memories}
{impressions_section}
## Recent world changes (things that happened — not necessarily narrated yet)
{world_events}

## Recent exchange
{recent}

## Plan for this beat
{plan}
{f"## A complication to fold in{chr(10)}{twist}{chr(10)}" if twist else ""}
## Tone
{json.dumps(tone, ensure_ascii=False)}

## Plausibility ruling
{json.dumps(plausibility, ensure_ascii=False)}

## Mechanical check
{json.dumps(mechanical_check, ensure_ascii=False)}
{f"## Roll result (narrate this truthfully){chr(10)}{json.dumps(roll_resolution, ensure_ascii=False)}{chr(10)}" if roll_resolution else ""}
## Player message
{player_text}

Narrate what happens next.
"""
    return system, user
