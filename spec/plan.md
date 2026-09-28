# Plan

Direction confirmed: get a working single-player loop end-to-end (seed → take turns → see it
hold together), fixing the correctness bugs found in `spec/bugs.md` and wiring in the
currently-dead memory/thread/summary features rather than ripping them out.

**Status: Phases 1–3 below are implemented.** Not independently runtime-tested — this
sandbox has no Postgres/Ollama and no Python deps installed, so verification was static
(`py_compile` on every touched file + manual review), not a live smoke test. Recommend
running `docker compose up -d db ollama`, `pip install -r requirements.txt`, then hitting
`/ui` for a real seed→turn→roll pass before trusting this in anger.

## Phase 1 — Critical + related correctness fixes (done)

1. **Bug #1** — actor/profile read crash. Fix `_serialize_profile` (`read.py`) and
   `get_profile` (`profiles.py`) to read `age`/`species`/`occupation`/`alignment` out of
   `profile.extra`, matching `scene.py`'s existing correct pattern.
2. **Bug #2** — seeding never narrates the opening scene. Remove the bogus `gm_director`
   reference and rebuild the seeder's closing narrate-call payload to match
   `build_narrator_prompt`'s actual expected keys (reuse `render_current_scene` +
   `gm_out`/`gm_thoughts`, same shape `turn_pipeline.py` uses).
3. **Bug #3/#4** — `LoreChunk` metadata: fix `metadata=` → `meta=` in `indexer.py`, and
   `LoreChunk.metadata[...]` → `LoreChunk.meta[...]` in `retriever.py`.
4. **Bug #5** — roll resolution: use `resolve_skill_check` (crit success/fail) in
   `turn_pipeline.resolve_roll` instead of the inline success/fail-only comparison.
5. **Bug #7** — add `"location"`/`"npc"` entries to `Settings.model_for`'s role map so the
   existing `LLM_MODEL_LOCATION`/`LLM_MODEL_NPC` settings actually take effect.

Each is small and independent — fix and sanity-check (import/syntax) one at a time.

## Phase 2 — Wire in memory / thread / summary maintenance (done)

Currently `regress_memory` and `advance_threads` exist on `LLMRoles` with prompt builders
but are never called; `world_tick` is a no-op; the `campaign_summary` context block is
written once at seed and never refreshed. Per the README's intended cadence:

- **Every turn**: after narration, run a memory-regression pass (`llm.regress_memory`) fed
  the latest event + current active context blocks, apply its ops via `apply_ops` (creates
  short-TTL `memory`-type context blocks per the prompt's own rules).
- **Every 3 turns** (`camp.turn_count % 3 == 0`): run `advance_threads` fed active
  `StoryThread` rows + recent transcript, apply ops (create/update threads).
- **Every N turns** (`CONTEXT_SUMMARIZE_EVERY_N_TURNS`, default 6 — note README says 5,
  config says 6; reconcile to one number): regenerate the `campaign_summary` context block
  from recent events + the previous summary, so it stays a rolling summary instead of a
  frozen seed-time snapshot.

This adds 1-2 extra LLM calls to a subset of turns (not every turn gets all three), which is
a real latency/cost tradeoff worth flagging but consistent with the chosen direction.

**Implementation notes:**
- Added a `TurnPipeline._run_post_turn_maintenance()` helper (called from both `begin_turn`
  and `resolve_roll` right after the turn's `Event`/`turn_count` update) instead of
  duplicating the three passes in both methods.
- There was no existing LLM role for a periodic summary refresh (only a one-time
  `campaign_summary` field on the seed-time `CampaignSeedOut`) — added a small new
  `CampaignSummaryOut` schema, `prompts/campaign_summary.py`, and
  `LLMRoles.summarize_campaign()` following the existing role pattern, rather than
  repurposing the seeder's schema.
- Each of the three passes is wrapped in its own try/except so a failure (e.g. an LLM
  hiccup) never rolls back the turn's already-committed narration/world-state — it just
  skips that turn's maintenance and logs.
- Also fixed in passing: `world_tick(db, camp.id, 0)` was hardcoded to `0` minutes even
  though the real elapsed time was known — now passes `gm_out.time_passed_minutes` (moot
  today since `world_tick` is a no-op, but correct if it's implemented later).

## Phase 3 — Frontend: make the single-player loop actually playable end-to-end (done)

The backend loop works via raw HTTP once Phase 1 lands, but `/ui` (bug #8) doesn't drive it.
To call the loop "working end-to-end" this needs:

- Rewrite `app.js` against `index.html`'s actual element ids (`btnSeed`, `btnLoad`,
  `campaignId`, `actorId`, `thoughtsIntro/Pacing/Plan`, `sceneTitle/sceneSummary`, `nearby`,
  `npcsHere`, `contextBlocks`, `events`, `actionText`/`btnSend`, `status`), removing the
  hardcoded campaign id.
- Wire `btnSeed` → `POST /api/v1/seed`, populate `campaignId`/`actorId` from the response.
- Wire `btnSend` → `POST /api/v1/turns/{actorId}`; if the response has `pending_roll`, render
  a way to submit a d20 to `POST /api/v1/rolls/{id}` (there's currently no roll-submission UI
  at all — needs to be added, not just rewired).
- Wire tab switching (Thoughts/Scene/Context) and periodic/on-turn refresh of scene + context
  blocks + transcript.
- Delete the orphaned `style.css` (bug #9) — done.
- Fix the README's dangling `cli/play_campaign.sh` reference (bug #10) — replaced with
  pointing at `/ui`, since that's now an actual working entry point.

**Implementation notes:** `app.js` was fully rewritten against `index.html`'s real element
ids. Added seed/load/send/roll wiring, tab switching, and a small roll-submission widget
(`#rollPrompt` in `index.html`, driven by `showRollPrompt`/`submitRoll` in `app.js`) that
didn't exist before. Not browser-tested in this pass (no way to run the full stack here) —
worth a manual click-through once Postgres/Ollama are up.

## Explicitly deferred (not in this pass)

- Battle/combat mode is still a stub after this plan — out of scope for "get the loop
  working," in scope for a later "flesh out mechanics" pass if you want it next.
- No test suite exists; not adding one as part of this bug-fix pass unless you want it folded
  in.
