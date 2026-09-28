# Bugs found during full read-through

Ordered roughly by severity/impact. Line numbers as of commit `48d62b8` (pre-fix).

**Status: #1–#7 and #9–#10 fixed in this pass; see `spec/plan.md` for what changed.
#8 (frontend) rewritten. Read on for the original diagnosis of each.**

## 1. `ActorProfile.age/species/occupation/alignment` don't exist as columns — crashes actor reads

- **Where:** `app/api/v1/read.py:35-38` (`_serialize_profile`), `app/api/v1/profiles.py:52-55`
  (`get_profile`)
- **Model:** `app/models/actor_profile.py` has no `age`, `species`, `occupation`, or
  `alignment` columns — those live inside the `extra: dict` JSON field.
- **Confirmed by:** `app/services/world/campaign_seeder.py:218-225` and
  `app/api/v1/scene.py:57-60` both correctly read/write these via `profile.extra.get(...)`.
  The read-side code in `read.py`/`profiles.py` instead does `p.age`, `p.species`, etc.
  directly on the ORM object.
- **Impact:** `GET /api/v1/actors/{id}`, `GET /api/v1/campaigns/{id}/actors`, and
  `GET /api/v1/profiles/{actor_id}` raise `AttributeError` and 500 for **any** actor that has
  a profile — which is every NPC created by the seeder, and the player actor. These are core
  read endpoints; the app is effectively unable to display actor info today.
- **Fix:** read from `profile.extra.get("age")` etc. (matching `scene.py`), or add real
  columns to `ActorProfile` and migrate the seeder/`apply_ops` to populate them instead of
  stuffing them in `extra`. Prefer the latter for a cleaner data model, but either fixes the
  crash.

## 2. Campaign seeding never produces an opening narration (silently)

- **Where:** `app/services/world/campaign_seeder.py:452-494`
- The code builds a dict containing
  `"gm_director": (gm_out.gm_director.model_dump() if gm_out and gm_out.gm_director else None)`.
  `GMPlannerOut` (`app/services/llm/schemas.py:79-96`) has no `gm_director` field — this
  raises `AttributeError` while constructing the dict, before the narrate call ever fires.
  It's caught by the bare `except Exception: pass` wrapping that block.
- **Impact:** every seeded campaign silently ends up with zero `Event` rows and no opening
  scene narration, even though the seeder is designed to produce one (see the tooltip in
  `frontend/index.html:40`: "click Seed Campaign to ... get an opening scene narration").
  First thing the player sees is an empty transcript.
- **Secondary issue in the same block:** even if `gm_director` didn't crash, the payload
  passed to `llm.narrate(...)` doesn't match what `build_narrator_prompt` reads. It sends
  `"campaign_summary"`/`"current_scene"` keys; the prompt builder
  (`app/services/llm/prompts/narrator.py`) reads `"scene_text"`, `"gm_thoughts"`,
  `"context_blocks_text"`, `"transcript_text"`. It wouldn't crash (dict.get returns None) but
  would produce a degraded, mostly-empty prompt.
- **Fix:** drop the `gm_director` reference, and rebuild the narrate payload using the same
  shape used in `turn_pipeline.py` (`scene_text` via `render_current_scene`, `gm_thoughts`
  from the already-computed `gm_out`, etc.) instead of ad-hoc keys.

## 3. Lore chunk metadata silently never saved (`metadata=` vs `meta=`)

- **Where:** `app/services/lore/indexer.py:33`
- `LoreChunk(...)` is constructed with `metadata={"doc_type": ..., "tags": ..., "title": ...}`,
  but the mapped column on `LoreChunk` (`app/models/lore_chunk.py:26`) is named `meta`, not
  `metadata`. `metadata` is also a reserved attribute on SQLAlchemy `DeclarativeBase`
  subclasses (the table's `MetaData` registry), so this doesn't raise — it just silently sets
  a throwaway instance attribute that's never persisted. Every `LoreChunk` row ends up with
  `meta={}` (the column default).
- **Impact:** `retriever.py`'s `retrieve_lore_chunks` reads `meta.get("title")` /
  `meta.get("doc_type")` — both always come back `None` for every retrieved lore hit. Lore
  clips injected into context (`turn_pipeline.py:239` `h.get("title") or "Lore"`) always
  render as generic "Lore" with no doc_type, and doc_type filtering silently can't work.
- **Fix:** `meta={...}` instead of `metadata={...}`.

## 4. `LoreChunk.metadata[...]` filter is dead and would crash if ever used

- **Where:** `app/services/lore/retriever.py:32`
- `stmt.where(LoreChunk.metadata["doc_type"].as_string() == doc_type)` — `LoreChunk.metadata`
  at the class level is SQLAlchemy's `MetaData` registry object, not the JSON column (which
  is `meta`). This isn't hit today because no caller passes `doc_type` to
  `retrieve_lore_chunks`, but if anyone wires that parameter up it will throw immediately.
- **Fix:** `LoreChunk.meta["doc_type"]`.

## 5. Roll resolution bypasses the crit success/fail logic that already exists

- **Where:** `app/services/pipeline/turn_pipeline.py:359-372` (`resolve_roll`)
- `mechanics/rolls.py` has `resolve_skill_check(d20, modifier, dc)` which returns
  `crit_success`/`crit_fail` on natural 20/1. `resolve_roll` reimplements the comparison
  inline (`"success" if total >= dc else "fail"`) without ever calling
  `resolve_skill_check`, so nat-20/nat-1 outcomes are indistinguishable from an ordinary
  success/fail. `PendingRoll.outcome`'s docstring/comment (`pending_roll.py:32`) explicitly
  documents `crit_success`/`crit_fail` as valid values that never actually occur.
- **Fix:** call `resolve_skill_check` instead of the inline comparison.

## 6. Memory regression, thread advancement, and campaign-summary refresh are all dead code

- **Where:** `LLMRoles.regress_memory` / `LLMRoles.advance_threads`
  (`app/services/llm/roles.py:230-266`) are fully implemented (prompt builders exist too:
  `prompts/memory.py`, `prompts/thread.py`) but are **never called** from
  `turn_pipeline.py` or anywhere else. `world_tick()` (`services/world/world_tick.py`) is
  called every turn but is a literal no-op placeholder. The `campaign_summary` context block
  is written once at seed time and never refreshed.
- **Impact:** the README's advertised behavior — "Memory regression every turn", "Story
  threads checked every 3 turns", "campaign summary every 5 turns" — does not happen. Story
  threads created at seed time are static forever; nothing ever marks them completed/failed
  or advances their `state`. This isn't a crash, but it's a real gap between documented and
  actual behavior worth deciding on: wire them in, or update the README/plan to reflect
  where things actually stand.

## 7. `settings.model_for("location")` / `model_for("npc")` are not wired

- **Where:** `app/core/config.py:51-63` (`model_for`)
- `LLM_MODEL_LOCATION` and `LLM_MODEL_NPC` are declared settings
  (`config.py:24-25`), and `LLMRoles.write_location`/`write_npc` call
  `settings.model_for("location")` / `model_for("npc")` (`roles.py:293, 309`), but the
  `role_map` dict inside `model_for` only has entries for intent/check/knowledge/gm/world/
  narrator/memory/thread/seeder. `model_for("location")` and `model_for("npc")` always fall
  through to `LLM_MODEL_DEFAULT`, silently ignoring any override.
- **Fix:** add `"location": self.LLM_MODEL_LOCATION, "npc": self.LLM_MODEL_NPC` to the map.

## 8. Frontend prototype (`/ui`) is non-functional / mismatched with its own markup

- **Where:** `backend/frontend/app.js` vs `backend/frontend/index.html`
- `app.js` hardcodes a stale campaign id (`const campaignId = "8c822428-..."`) instead of
  reading the `#campaignId` input; it looks up `document.getElementById("scene")`,
  `"context"`, `"threads"`, `"events")` — none of these ids exist in `index.html` (which has
  `sceneTitle`, `sceneSummary`, `nearby`, `npcsHere`, `contextBlocks`, `events`, no `threads`
  element at all, and a `btnSeed`/`btnSend`/tab-switching UI with no matching JS). `app.js`
  also never calls `loadGameState()` or attaches any event listeners — nothing runs on page
  load, and no button does anything.
- **Impact:** opening `/ui` today does nothing beyond rendering static HTML. This looks like
  an in-progress rewrite where the HTML moved on to a tabbed layout but `app.js` was never
  updated to match (or vice versa).
- **Fix:** rewrite `app.js` against the current `index.html` ids, wire up the seed/send/tab
  interactions, and stop hardcoding the campaign id.

## 9. Duplicate/orphaned CSS file

- **Where:** `backend/frontend/style.css` (169 lines) vs `styles.css` (36 lines, minified) —
  `index.html` only links `styles.css`. `style.css` is unreferenced dead weight (looks like
  an earlier, more verbose draft of the same stylesheet).
- **Fix:** delete `style.css`, or if it's actually the intended one, repoint `index.html` and
  delete `styles.css`.

## 10. README references a CLI script that doesn't exist in the repo

- **Where:** `backend/README.md:52-55` — `bash cli/play_campaign.sh`. There is no `cli/`
  directory anywhere in the repository.
- **Fix:** either add the script back or remove the instruction from the README.

## Minor / worth a look, not confirmed as behavior-changing

- `turn_pipeline.py` never calls `db.commit()` itself — it relies on `get_db`'s
  request-scoped commit (`app/db/session.py:15`). That's fine as-is, but it means a partial
  failure mid-pipeline (e.g. an `OllamaError` on the narrate call, *after* `apply_ops` already
  ran) rolls back world-state ops too, since it's all one transaction — e.g. an NPC created by
  `world_update` in a turn that then fails on `narrate` disappears. This may be desired
  (all-or-nothing turns) or may be surprising; worth confirming intent.
- `world_tick(db, camp.id, 0)` is called with a hardcoded `0` for `minutes_passed` even
  though `gm_out.time_passed_minutes` is known at that point in `begin_turn` — moot today
  since `world_tick` is a no-op, but if it's implemented later this call site needs the real
  elapsed minutes.
