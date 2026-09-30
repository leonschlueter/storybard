# Storybard v2 — Codebase Overview

A from-scratch LLM-driven tabletop RPG (TTRPG) narrative engine: a solo player takes
actions in free text, an LLM-driven "GM" pipeline decides what's plausible, resolves
mechanics, plans a narrative beat, writes prose, and mutates persistent world state — all
through a human-reviewable, steerable chain rather than a single opaque LLM call.

This document is a from-scratch orientation for someone (or some agent) who hasn't seen
the code before. It describes what exists and how it fits together; it is not a list of
known issues or a verdict on quality — form your own opinion by reading the code and
running it.

## Tech stack

- **Backend**: Python, FastAPI, SQLAlchemy 2.0 (async), Postgres + pgvector, Alembic
  migrations, LangGraph (the chain/pipeline orchestration), `uv` for dependency management.
- **LLM**: [LM Studio](https://lmstudio.ai) running locally, OpenAI-compatible API
  (`/chat/completions`, `/embeddings`), accessed via a small hand-rolled client
  (`services/llm/lmstudio_client.py`) — no LangChain/LlamaIndex, no agent framework beyond
  LangGraph's graph/checkpoint primitives.
- **Frontend**: React + TypeScript + Vite, Tailwind CSS, `lucide-react` icons, no state
  management library beyond React hooks + a WebSocket for live turn events.
- **Infra**: Docker Compose (`db`, `server`, `web`, `pgadmin`), each service a separate
  container. `server`'s source is baked into its image at build time (**not** bind-mounted
  — a code change requires `docker compose up -d --build server`, not just `restart`).
  `web`'s source is bind-mounted with Vite HMR.

## Running it

```
docker compose up -d --build     # first run / after any server code change
docker compose up -d             # web/db only need a plain restart to pick up changes
uv run alembic upgrade head      # from server/, after pulling new migrations
```

- Backend: `http://localhost:8000` (routes under `/api/v1`, see `main.py`)
- Frontend: `http://localhost:5173`
- Postgres: exposed on host port 5432 (`postgres`/`postgres`/`storybard`)
- pgAdmin: `http://localhost:5050`
- LM Studio must be running on the host at `http://localhost:1234` (the server container
  reaches it via `host.docker.internal`) with two models loaded: a default model
  (`LLM_MODEL_DEFAULT`, currently `google/gemma-4-e4b`) and a "creative" model
  (`LLM_MODEL_CREATIVE`, currently `qwen/qwen3.8-27b`), plus an embedding model
  (`LM_STUDIO_EMBED_MODEL`, `text-embedding-nomic-embed-text-v1.5`, 768 dims).

Backend tests: `cd server && uv run pytest tests/ -q` (188+ tests, all unit-level —
prompt builders, op handlers, context-assembly queries, dice math — no FastAPI
`TestClient`/route-level tests exist in this codebase).

Frontend: `cd web && pnpm build && pnpm lint` (`tsc -b && vite build`, `oxlint`).

## Directory layout

```
server/src/storybard/
  api/            FastAPI routers
    campaigns.py    campaign CRUD, seeding (pitch/propose/commit), settings
    party.py        character creation (ancestries/classes catalog, finalize-character, sheet)
    turns.py        the turn loop: create_turn, chain-step resolve, turn history,
                     current-turn recovery/abandon, opening scene, scene endpoint, world-tick
    explore.py      read-only /world-state (campaign-wide codex: actors, locations,
                     threads, items, spells, factions, hooks, recent events)
    ws.py           WebSocket stream (broadcasts paused/completed turn events per campaign)
  chain/          the LangGraph pipeline
    graph.py         ChainState, all *_generate node functions, graph topology, model routing
    prompts.py       every prompt builder (system+user strings) — one function per node
    ops.py           the WorldOp union (every world-mutating operation) + apply_op handlers
    service.py       turn advance/resolve, retry-a-step, direct-write appliers
                      (tone, plausibility-time, memory regression), hard pacing floor
    seed_service.py  campaign seeding: pitch->SeedInput, propose->SeedProposal, commit
  domain/         SQLAlchemy models (see below)
  services/
    context_assembly.py   pure read/shape functions feeding chain prompts (the
                           "what does each node see" layer)
    llm/lmstudio_client.py   thin OpenAI-compatible client (chat + embeddings), structured
                              output via JSON-schema response_format
    llm/schemas.py           Pydantic output models for every chain node
    mechanics/dice.py, formulas.py   roll resolution, degrees of success
    geography.py             location-hierarchy distance (lowest-common-ancestor)
    duration.py               free-text "3 weeks" -> timedelta parsing
    oracle.py                  small hardcoded event table for the hard pacing floor
  core/
    config.py        Settings (env-driven: DB URL, LM Studio URL/models, caps)
    db.py             async engine/session, declarative Base
    logging.py         structlog configuration
    ws_hub.py           per-campaign WebSocket broadcast hub
  main.py           FastAPI app factory, lifespan (builds the compiled graph once, holds
                     it + the LLM client as app.state — see "State & persistence" below)

web/src/
  PlayScreen.tsx           the main three-pane play UI (see "Frontend" below)
  SeedWizard.tsx           campaign-seeding wizard (pitch -> propose -> review -> commit)
  PartyCreation.tsx        character creation flow
  components/
    CharacterRail.tsx        persistent left rail: HP/AC/conditions/abilities/inventory
    SceneWorldRail.tsx        persistent right rail: current scene, NPC cast, world codex
    ChatBubble.tsx, Badge.tsx, Button.tsx, Card.tsx   shared UI primitives
    SettingsPanel.tsx          campaign settings modal
  lib/api.ts                typed fetch wrappers + WebSocket helper, mirrors every backend
                             response shape 1:1 (see file header comments for exact mapping)
```

## Domain model

All tables are UUID-keyed, campaign-scoped via a plain `campaign_id` column (deliberately
no FK constraint on `campaign_id` anywhere — tests construct entities against synthetic
campaign ids with no real `Campaign` row).

- **Campaign** — name, mode, `turn_count`, `current_datetime`/`calendar_name` (advanced by
  Plausibility's `time_passed` estimate), rolling `summary` (rewritten every turn by Memory
  Regression), one-time `opening_narration` (distinct from `summary`), `tone_state`,
  session-zero fields (`calendar_context`, `safety_tools`, `personal_stakes`).
- **CampaignSettings** — one row per campaign, one boolean/int field per configurable
  feature (seeding enrichment + narration liveliness toggles, ~20 fields). Read live every
  turn via `context_assembly.get_campaign_settings`; auto-created on first read if missing.
- **Actor** — `kind` (player/npc/companion), `bio`, `current_goal`, `speech_style`,
  `current_node_id` (location FK). `ActorProfile` (1:1, optional) carries
  `appearance`/`personality`/`backstory` — populated only for the player character via
  Party Creation, never for NPCs. `CharacterSheet` (1:1, optional) carries ability scores
  (a `dict[key, int]`, keyed against campaign-scoped `AttributeDefinition` rows — no
  hardcoded STR/DEX/... columns anywhere), HP/AC/speed/conditions/level/ancestry/class.
- **AttributeDefinition / AncestryDef / ClassDef** — campaign-scoped ruleset content.
  Nothing about the ability keys or playable ancestries/classes is hardcoded; a fresh
  campaign either reuses `DEFAULT_5E_*` constants (`domain/ruleset.py`) or gets bespoke
  LLM-generated ones at seed time.
- **WorldNode** — a location at any scale (world/region/room), uncapped hierarchy via
  `parent_node_id`, local `(x, y)` coordinates (meaningful only relative to the node's own
  parent — `services/geography.py` handles cross-branch distance).
- **Thread** — the single unit of narrative momentum (quests, NPC agendas, faction goals
  are all just Threads owned by different things). `tier` (major/minor), `depth` (capped at
  1 — major + one minor tier, no deeper nesting), `parent_thread_id`/`relation`
  (prerequisite/alternative/optional_aid), `owner_type`/`owner_id`.
- **ThreadBeat** — a staged, addressable planned step under a Thread (`status`:
  pending/fired/abandoned, optional `location_id`). Computed into a per-turn `Scene` object
  (`context_assembly.build_scene`) — not itself persisted as "current."
- **Clock** — an N-segment progress clock on a Thread, `tick_source`
  (time_elapsed/player_action/linked_thread_complete), `visibility`,
  `real_time_per_segment` (for time-elapsed clocks). Has a `consequence_op` JSON field
  (intended to fire when the clock fills) — defined and read, but nothing in the codebase
  currently sets it; consequences are expressed as a sibling op in the same World Update
  batch instead.
- **Hook** — a proposed-but-not-committed narrative development. `touches_entity_id` set
  means it recontextualizes something already established (requires review); null means
  it only adds new canon (auto-accepted). `status`: proposed/accepted/rejected — no
  endpoint currently exists for a human to move a "proposed" hook to
  accepted/rejected.
- **Memory** — a short per-actor recollection (`owner_actor_id`, optional
  `subject_actor_id` for NPC-impressions-of-player rows), `importance` (1-5), and an
  `embedding` (pgvector, 768-dim, nullable) used for similarity retrieval.
- **Faction, ItemDef, SpellDef, InventoryItem, PlantedReveal** — faction agendas;
  item/spell definitions (templates) vs. `InventoryItem` (an actual instance an actor
  carries); a GM-only hidden connection seeded at campaign start, never shown to the
  player directly.
- **ChainStep / TurnRun** — the audit trail. One `TurnRun` per player action
  (`status`: running/paused/completed/abandoned); `TurnRun.id` doubles as the LangGraph
  checkpoint thread id. One `ChainStep` per node per turn (`node_type`, `sequence`,
  `input_snapshot`, `raw_output`, `final_output`, `status`: pending/approved/edited/retried).

## The chain (LangGraph pipeline)

One player action runs through a fixed sequence of nodes. Every conceptual step is **two**
graph nodes — `X_generate` (calls the LLM, fully completes) and `X_review` (calls
`interrupt()` as its first action) — because LangGraph re-runs a node's code from the top
on resume; splitting this way means resuming only re-enters the review half, never
re-calls the LLM.

**Node order** (linear, except two conditional detours):

1. `intent_parse` — classify the player's message into a primitive action
2. `plausibility_check` — is the stated action actually possible, given scene + character?
3. `thread_tick` — should any active Clock advance?
4. `opportunity_spotting` — does this moment suggest a new Thread/Hook?
5. `mechanical_check` — does this need a dice roll, and against what DC?
6. `roll_resolution` *(conditional — only if a roll was required)* — deterministic, no LLM
7. `tone_assessment` — a short free-text mood/tension read
8. `plan_synthesis` — a short beat plan for the Narrator (a director's note, not prose)
9. `twist` *(conditional — every `narration_twist_frequency`-th turn)* — one complication
10. `narrator` — the actual prose the player reads
11. `world_update` — turns the narration into real WorldOp mutations (runs *after* the
    Narrator, deliberately, so it can see what the prose actually introduced)
12. `memory_regression` — extracts durable memories, rewrites `Campaign.summary`, records
    NPC impressions

Every `_generate` node's exact inputs are visible in `graph.py`'s function bodies and
mirrored in `chain/service.py`'s `_RETRY_PROMPT_BUILDERS` (used by the "retry this step"
action). `ChainState` (a `TypedDict`) is the single source of truth for what's available to
which node.

**Model routing**: `CREATIVE_NODE_TYPES` (`graph.py`) — currently
`{opportunity_spotting, plan_synthesis, world_update, twist, narrator}` — run on
`LLM_MODEL_CREATIVE` at a higher temperature (0.7 vs. the 0.2 default); everything else
runs on `LLM_MODEL_DEFAULT` at 0.2. This is a real, measured latency tradeoff (the creative
model takes ~15-30s per call vs. ~1-2s for the default model) traded for reliability on
"should something structural happen here" judgment calls.

**Per-turn context** (`context_assembly.py`, assembled once in `api/turns.py::create_turn`,
then read selectively by each node): `scene` (current location + who's physically present
+ due beats, via `build_scene`), `active_threads`, `active_clocks`, `known_actors` (the
full campaign-wide actor catalog — bio/personality/speech_style/current_goal/`present`
flag — used both for dedup in World Update and, filtered, for "who's actually here" in the
Narrator), `known_locations` (full detail for the current node, summary for its parent,
names-only elsewhere — a context-budget rule), `recent_turns` (last 5, oldest-first),
`relevant_memories` (cosine-similarity search against an embedding of the player's
message, falling back to importance/recency ordering if the embedding call fails or the
memory predates the embedding column), `recent_world_events`, `npc_impressions`,
`actor_context` (the acting character's own sheet + `personal_stakes` when they're the
player), `campaign_summary`, `turns_since_thread_activity`.

**Structured output**: every LLM call uses `response_format: json_schema` against a
Pydantic model (`services/llm/schemas.py`) — grammar-constrained at the llama.cpp level, so
outputs are syntactically valid JSON even from small local models, though field-naming and
shape reliability still depend on the schema itself, not just the grammar. Every op/output
model in the system extends a `StrictOut` base with `extra="forbid"`.

**Observability**: every LLM call logs `lmstudio.request_started`/`completed`/`failed`
with model, output schema name, prompt char count, and duration
(`services/llm/lmstudio_client.py`). Route-level events (`seed.propose_started`, etc.) are
logged separately in `api/campaigns.py`.

## World mutation: the ops vocabulary

`chain/ops.py` defines a single discriminated union, `WorldOp`, covering every way the
system can mutate persistent state: `create_major_thread`/`create_minor_thread` (with
`initial_beats`), `fire_beat`/`abandon_beat`, `add_clock`/`tick_clock`, `propose_hook`,
`create_actor`/`update_actor`, `create_world_node`, `apply_damage`/`apply_condition`,
`create_item_def`/`create_spell_def`/`create_faction`. `apply_op` dispatches on the
discriminator and is the **only** place any of these tables get written outside of seeding
— every op does its own structural validation (e.g. `actor_id` must resolve to a real
`Actor` in this campaign, or the op is rejected with a reason, never silently dropped).

Two deterministic, code-level caps sit outside the LLM's control entirely:
`MAX_MAJOR_THREADS`/`MAX_MINOR_THREADS_PER_PARENT` (env-configured) and the thread depth
cap (`MAX_THREAD_DEPTH = 1`, `domain/thread.py`).

`chain/service.py::_apply_hard_pacing_floor` is a deterministic backstop, not an LLM call:
if `turns_since_thread_activity` crosses `narration_hard_stagnation_threshold`, it forces a
pacing event from the hardcoded `ORACLE_EVENTS` table (`services/oracle.py`) rather than
relying on the LLM to notice stagnation on its own.

## Campaign seeding

`chain/seed_service.py`, a three-step flow mirrored 1:1 by `SeedWizard.tsx`:

1. **pitch** (optional) — a free-text campaign pitch -> a filled `SeedInput` (name, world
   description, tags, races/classes mode, must-include elements, etc.)
2. **propose** — generates a `SeedProposal`: a batch of `WorldOp`s, never committed yet.
   Two LLM calls: `seed_content_prompt` (mechanical content — ancestries/classes/items/
   spells; skipped in `standard_5e` mode, which reuses `DEFAULT_5E_*` constants instead)
   and `seed_narrative_prompt` (narrative content — NPCs, hooks, rumors, optional
   faction/child-locations/planted-reveal, and one elaborated `create_major_thread` per
   must-include element).
3. **commit** — applies the full op batch inside one transaction, resolving the
   name-based location placeholders every `create_actor`/`create_world_node` op uses
   (locations don't have real ids until they're actually created, so the seeding prompts
   reference them by their proposed name; `commit_seed` builds a `name -> id` map as it
   applies `create_world_node` ops in order, then resolves every `current_node_id`/
   `parent_node_id` placeholder against it).

## Frontend

`PlayScreen.tsx` is a persistent three-pane layout (not tabs): `CharacterRail` (left),
chat transcript + step badges + input (center), `SceneWorldRail` (right) — collapsing to
drawers below the `lg` breakpoint. Settings is the one deliberate modal (an occasional
action, not something you want on screen while playing).

- Turn submission (`POST /campaigns/{id}/turns`) kicks off the chain; step-by-step
  progress arrives over a per-campaign WebSocket (`connectCampaignStream`) as
  `{status: "paused", step}` or `{status: "completed", narration}` events. A "paused" step
  either auto-resolves (if the auto-approve toggle is on) or renders a review card
  (approve/edit/retry/abandon) — `chain-steps/{id}/resolve`.
- Every step badge is clickable to expand that node's full JSON output inline (not just a
  one-line summary) — works for both the live turn and, since `get_turn_history` now
  returns each turn's full step trail, for past turns after a page refresh.
- `create_turn` rejects (409) a second turn while one is already running/paused for that
  actor; `GET .../current-turn` lets the client recover a turn stuck on a pending review
  step after a refresh (re-seeding it into the transcript exactly like a live one);
  `POST .../current-turn/abandon` is the explicit way to discard one.
- `SceneWorldRail` shows the current scene (location, who's physically present, a
  collapsed "GM notes" disclosure for due beats — spoiler content, closed by default) plus
  a browsable World section: a full NPC "Cast" roster (bio/personality/speech_style/
  current-goal, "here"/"elsewhere" badge from the `present` flag), threads (with summary),
  hooks/rumors, locations, items, spells, factions.

## State & persistence — one architectural note worth knowing up front

The compiled LangGraph graph is built **once** at app startup
(`main.py::lifespan`) with an `InMemorySaver` checkpointer, stored on `app.state`. This
means:
- A paused turn's in-progress chain state lives in the server process's memory, not in
  Postgres. `ChainStep`/`TurnRun` rows in Postgres are the durable audit trail of what's
  happened so far, but resuming a paused turn (`Command(resume=...)`) depends on the
  checkpointer still holding that turn's state.
- A server restart while a turn is paused mid-review orphans it at the LangGraph level
  even though its Postgres rows still exist — this is exactly the class of problem the
  `current-turn`/abandon endpoints (see above) exist to let a human recover from or
  explicitly discard.

## Testing

`server/tests/` — unit-level only, no FastAPI `TestClient`/route-level integration tests.
Structure: one file roughly per module (`test_prompts.py`, `test_ops.py`,
`test_context_assembly.py`, `test_chain_nodes.py`, `test_full_chain.py`,
`test_seed_service.py`, `test_direct_writes.py`, `test_model_routing.py`, `test_dice.py`,
`test_mechanics.py`, `test_duration.py`, `test_geography.py`, `test_party.py`,
`test_campaign_settings.py`, `test_opening_scene.py`, `test_lmstudio_client.py`).
`conftest.py` provides a real Postgres session fixture (rolled back per test, not SQLite —
needed for pgvector/UUID/FK types) and fake-LLM-client fixtures (`lm_client_with`: mocks
the HTTP layer with a canned JSON payload; `lm_client_by_model`: mocks `structured_chat`
directly, keyed by output-schema class name, for tests that chain several different calls).

Frontend has no test suite — `pnpm build` (TypeScript compile + Vite build) and
`pnpm lint` (`oxlint`) are the only automated checks.
