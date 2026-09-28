# Storybard — Architecture Spec

Reverse-engineered from the current codebase (no prior design docs existed). This describes
what the system *actually does today*, as a baseline for planning next steps.

## What this is

An LLM-driven, GM-less tabletop RPG (TTRPG) engine. A single "campaign" is a persistent
world (locations, NPCs, lore, items, spells, story threads) that a player advances by
submitting free-text actions. The backend orchestrates a chain of small, structured LLM
calls (via LM Studio's local server) to interpret the action, decide if a dice roll is
needed, plan the scene, optionally mutate world state, and finally narrate the outcome.
Deterministic D&D-5e-ish mechanics (ability mods, proficiency, encumbrance, DCs) sit
alongside the LLM calls so the LLM never has to do arithmetic or hold canon in its head —
it's fed a rendered snapshot of state each turn.

Stack: FastAPI + SQLAlchemy 2.0 + Postgres/pgvector, LM Studio (OpenAI-compatible local
server, `LMStudioClient` in `app/services/llm/lmstudio_client.py`) for both chat (structured
outputs via `response_format.json_schema`) and embeddings, Prometheus + OpenTelemetry for
observability, a static HTML/JS "prototype" UI served at `/ui`, no auth, dev-only CORS.
The backend itself runs either directly on the host or containerized via the repo's
`Dockerfile` + `docker-compose.yml` (`backend` service); LM Studio is a desktop app and
always runs on the host, reached from the container via `host.docker.internal`.

## Request flow: a turn

`POST /api/v1/turns/{actor_id}` (`app/api/v1/turns.py` → `TurnPipeline.begin_turn`,
`app/services/pipeline/turn_pipeline.py`):

1. Load actor, campaign, current location.
2. `decay_ttl_blocks` — ages down TTL'd `ContextBlock`s, deactivates expired ones.
3. `encumbrance_snapshot` — deterministic STR×15 carry capacity + speed penalty.
4. **Intent LLM call** (`parse_intent`) — classifies the free-text action into a primitive
   (move/speak/attack/...) and optional mode-change request.
5. **Check Advisor LLM call** (`advise_check`) — decides if a roll is needed and proposes a
   DC.
6. `PhaseChecker.decide` — deterministic guardrails on top of the LLM's check advice (clamps
   DC to 5–30, clamps time to 0–240 min, mode-change always wins).
7. **If a roll is required**: a `PendingRoll` row is created and returned to the client;
   nothing else in this list runs until the roll is submitted.
8. **If not**: build the "Current Scene" render (`render_current_scene`) + last-40-events
   transcript (`build_transcript`), then:
   - **GM Planner LLM call** (`gm_plan`) — produces hidden "Thoughts" (introspection/pacing/
     plan) fed to the narrator, plus optional lore `retrieval_queries`.
   - **World Update LLM call** (`world_update`) — proposes a bounded list of `ops` (create
     NPC, move actor, create context block, grant item, etc.), applied via `apply_ops`.
   - Optional lore retrieval (pgvector cosine search) if the GM asked for it; hits are
     stashed as short-TTL `ContextBlock`s of type `lore_clip`.
   - **Narrator LLM call** (`narrate`) — the only LLM output actually shown to the player.
   - An `Event` row is persisted (action, narration, GM thoughts, world-update notes).
9. `POST /api/v1/rolls/{pending_roll_id}` (`resolve_roll`) resolves a pending roll (success/
   fail vs DC) and repeats steps 8's GM/world/narrate chain with the roll's outcome folded
   in.

Six LLM calls can fire in the worst case (intent, check, gm_plan, world_update, narrate,
+lore embed calls) — there is no caching/batching, so latency scales with LM Studio's
per-call overhead (small local models add up quickly across a 5-6 call turn).

## Data model (`app/models/`)

- **Campaign** — mode (explore/downtime/battle), calendar/in-game clock, turn counter, tone/
  reskin profile. `CampaignSettings` holds ruleset knobs (mostly unused by mechanics today).
- **Actor** (player or npc) + **ActorProfile** (narrative flavor: appearance, personality,
  backstory, faction, pronouns, voice — plus a catch-all `extra` JSON dict) +
  **CharacterSheet** (mechanical: ability scores, HP, AC, proficiencies, gold, conditions).
- **WorldNode** — locations, with x/y coordinates used for "nearby locations" distance calc.
- **ItemDef**/**InventoryItem**, **SpellDef**/**ActorSpell** — defs are campaign-scoped
  templates; the join tables grant them to actors.
- **Event** — the turn-by-turn transcript (action, intent, check result, narration,
  `result_data` grab-bag holding GM thoughts).
- **PendingRoll** — an in-flight skill check/initiative request awaiting a d20 from the
  client.
- **ContextBlock** — the generic "context card" primitive: locations, NPC summaries, lore
  hints, retrieved lore clips, the campaign summary, the plot summary — all the same table,
  distinguished by `type`. Has an optional `ttl_turns` for ephemeral cards (memories, lore
  clips) vs `ttl_turns=None` for permanent canon (locations, NPCs, plot summary).
- **LoreDocument**/**LoreChunk** — long-form markdown canon, chunked and embedded
  (pgvector) for RAG-style retrieval.
- **StoryThread** — quest/plot threads with a priority and freeform `state` JSON.
- **Memory** — short text snippets owned by an actor, optionally about another actor.
- **Scene** — the single "current scene" (title, current location, NPCs present, nearby
  info) — effectively a materialized view the narrator reads every turn.

## Where "the world" gets written

All world mutation goes through one small op-interpreter: `apply_ops`
(`app/services/ops/apply_ops.py`). LLM calls that are allowed to mutate state (world_update,
in principle memory/thread passes) emit a list of `{op, data}` objects from a closed set
(`OpType` in `schemas.py`): create/move actors, create locations, create/update context
blocks and story threads, create item/spell defs, grant item/spell, create actor profile,
create memory, update scene. `validate_item_effect`/`validate_spell_effect` apply light
guardrails against absurd damage dice. This keeps the LLM from ever running raw SQL — it can
only compose from op templates the engine controls.

## Campaign seeding

`POST /api/v1/seed` (`app/services/world/campaign_seeder.py`) is the only way to create a
campaign. One `seed_campaign` LLM call produces the campaign skeleton (locations, lore
facts, NPC stubs, threads, starter items/spells, start date). Each location and NPC stub is
then *individually* re-generated with its own dedicated LLM call (`write_location`,
`write_npc`) to get a richer writeup than the skeleton pass would produce cheaply — this is
the "custom NPC seeder" from the most recent commit. Finally a player Actor is created with
a fixed default Fighter sheet, and an opening-scene narration is attempted (see Bugs — this
last step currently fails silently every time).

## Context assembly for the LLM

Three cooperating pieces feed the narrator/GM calls:
- `services/context/catalog.py` — cheap id+name listings of everything in a campaign, used
  by the (currently unwired) Knowledge Selector role to let an LLM pick relevant ids.
- `services/context/fetch.py` — hydrates a selection of ids into full records.
- `services/context/renderer.py` — turns fetched records into the markdown-ish text blocks
  actually pasted into prompts (`render_current_scene`, `render_context_blocks`, etc).

In practice, turns don't use the Knowledge Selector today — the "selection" fed to
`fetch_selected` is just whatever's already pinned on the current `Scene`
(`current_node_id` + `npc_ids`), so the world doesn't get bigger context than what's
manually/LLM-pinned to the scene.

## Frontend

`backend/frontend/` is a static prototype mounted at `/ui`. It is not wired to the pipeline
in any working way today (see Bugs) and should be treated as throwaway/reference, not a real
client.

## Explicitly out of scope today

No auth/multi-tenancy, no websockets/streaming (every LLM call is synchronous request/
response), no combat resolution beyond "initiative_required" (battle mode is a stub — mode
exists on Campaign but nothing branches on it), no image/asset generation, no test suite.
