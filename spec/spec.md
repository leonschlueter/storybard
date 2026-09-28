# Storybard v2 — Narrative Engine & World Simulation

Design spec produced in a live architecture workshop, after running the v1 backend
end-to-end against a real local model and hitting real failure modes. This is a **full
rewrite**: new codebase, new data model, new LLM chain, new frontend. `architecture.md`,
`bugs.md`, and `plan.md` in this folder document the v1 system this replaces — kept as
historical reference and as the source of the "carries forward" section below, not as a
description of what exists now.

## Vision

An LLM-driven Gamemaster that runs a persistent, evolving campaign world — not a chatbot
that reacts to the player, but a **narrative engine and world simulation**: NPCs pursue
their own agendas, factions act, threads advance on their own clock whether or not the
player is paying attention, and the player's choices are one input among several rather
than the only thing that moves the story. Highly customizable (narrator persona, ruleset,
even an alternate oracle-driven "Mythic GME" mode) and built to be **inspectable and
steerable**: every step the LLM takes is visible and editable before it commits, not a
black box that occasionally shows its homework after the fact.

## Design principles (cross-cutting, apply everywhere below)

1. **Narrow, closed, default-biased LLM decisions, backed by deterministic guardrails.**
   We hit two silent bugs in v1 from the same root cause: a prompt's prose description of
   an output shape drifted from what the code actually implemented, and it failed silently
   instead of loudly. Lesson: never ask an LLM an open-ended question when a closed,
   ordered decision (with a cheap default) will do, and never trust prose alone to enforce
   a rule that the application can enforce structurally instead (rate caps, depth caps,
   canon-touch checks). The LLM's job is judgment calls that are genuinely subjective;
   everything else is code.
2. **Typed ops, not `dict[str, Any]`.** Every world-mutating action the LLM can emit is its
   own Pydantic model in a discriminated union, not a generic `{op, data}` pair. A
   malformed op fails validation loudly, at the schema layer, instead of silently
   no-op'ing deep in application code.
   **Refinement found during Phase 1 implementation**: the Pydantic model alone isn't
   enough — it must also produce a *strict* JSON schema (`model_config =
   ConfigDict(extra="forbid")`, every field required — nullable is fine, defaulted is not)
   for grammar-constrained decoding to actually have something to enforce. Confirmed
   empirically against `google/gemma-4-e4b`: a permissive schema (extra properties allowed,
   no required fields) let the model return `{"action": "move", "target_type": "place"}` for
   an intent-classification call — completely wrong keys — which still validated because
   nothing forbade it, silently defaulting the real field to "unknown". The identical prompt
   against a strict schema correctly produced `primitive: "move"`. Every LLM-output schema
   in the chain follows this now (`StrictOut` base in `services/llm/schemas.py`) — this
   applies to every schema Phase 2+ adds too, not just the four from Phase 1.
3. **Curiosity is a trigger.** The world isn't a fixed set of pre-seeded hidden threads
   waiting to be found. Investigating something un-threaded (talking to a background NPC,
   examining an odd detail) is itself a structural trigger that can spawn new content —
   this is how exploration gets rewarded, how neglect has consequences, and how
   foreshadowing, discovery, and world-building unify into one mechanism instead of three.
4. **Time drives the world, actions drive the chain.** Player actions trigger the per-turn
   LLM chain. Elapsed *in-game time* (which can jump by days in one player action, e.g.
   resting) independently drives the World Sim Tick, which advances every active thread
   regardless of player engagement.
5. **Everything the chain does is a structured, replayable trace**, not a flat log blob —
   this is what makes steerability, replay/branching, and debugging all possible from the
   same underlying data.
   **Architectural commitment made explicit during Phase 2 workshop**: the live DB tables
   (`Thread`, `Clock`, `Actor`, ...) are treated as a *materialized view* over the
   `TurnRun`/`ChainStep` log, not the source of truth themselves — every world-mutating
   change, no exception, happens as a typed op attached to a specific `ChainStep` (this was
   already true by construction; the commitment is to never add a mutation path that
   bypasses it). This is what makes real replay/branching (Platform features, below)
   buildable later as "replay the op log up to a branch point" rather than a retrofit — the
   alternative (branching only from points with no committed world mutations, or full DB
   snapshots per branch) was considered and rejected as too limiting or too heavy. The
   replay/fork mechanism itself is still Phase 5 scope; this is the constraint that keeps it
   possible.

## Stack

- **Backend**: Python, FastAPI, LangGraph for the chain (its human-in-the-loop
  interrupt/checkpoint model is a direct fit for "pause after a step, let a human edit,
  resume"). Checkpointer is `InMemorySaver` as of Phase 2B — a known, tracked gap, not a
  final choice: it means a server restart orphans any turn sitting mid-review (the
  `TurnRun`/`ChainStep` rows persist in Postgres, but the actual LangGraph checkpoint
  doesn't, so resuming that turn fails). Swapping to `AsyncPostgresSaver`
  (`langgraph.checkpoint.postgres.aio`, already a dependency) is contained, low-risk, and
  overdue — do it alongside the next Phase 3 work rather than waiting further.
- **DB**: Postgres + pgvector (kept from v1 — proven, and pgvector gives lore/RAG retrieval
  in the same database with no extra service).
- **Frontend**: React + Vite + a component library (shadcn/ui or similar) — a real "GM
  console," not a debug panel.
- **Real-time**: WebSocket streaming of chain steps to the frontend as they execute.
- **LLM provider**: LM Studio, OpenAI-compatible API. Structured outputs via
  `response_format: {"type": "json_schema", "json_schema": {...}}` — grammar-constrained
  at the llama.cpp level, so small local models are syntactically reliable but *not*
  reliable on field-naming/shape unless the schema forces it (principle #2 above exists
  because of this).
- **Auth**: real multi-user system, but **toggleable off** for local single-user no-auth
  use (matches how this is actually run today — LM Studio on the host, no login anywhere —
  while not closing the door on hosting it for others later).

## Domain model

### Campaign, settings, and the acting party
- `Campaign` — name, mode, calendar/in-game clock, turn counter, active `NarratorProfile`,
  active `Ruleset`, `mythic_mode_enabled`, rolling `summary` field (not a table — it's a
  singleton per campaign).
- `Settings` — a real, runtime-editable settings surface (not env-vars only): auth mode,
  model-comparison toggle, mythic mode, ruleset selection, narrator profile selection, and
  future toggles all live here, hot-swappable from one settings UI/API.
- `Actor` (`kind`: player/npc) + `ActorProfile` (narrative) + `CharacterSheet` (mechanical)
  — kept from v1, this split already worked well. `Actor.kind=player` already supports
  multiple rows, so **multi-PC party support is a data-model non-event** — ship with party
  size 1, but the chain/API always operate on "acting actor(s)" as a list, never a
  hardcoded singular, so turning on multi-PC later is a config change, not a rewrite.
  Includes a lightweight `companion` flag/kind — a recruited pet or sidekick travels with
  the party, has a simple sheet, and is a valid Hook target (the "recruit a cat" case) —
  without needing a whole separate object type.
- `User` — account/auth (toggleable). Each user owns their own campaigns; **not** shared
  live multiplayer for v1 (deferred — the data model doesn't block it later, but real-time
  session sync is a separate, bigger problem).

### World
- **`WorldNode` (location) is hierarchical**, mirroring `Thread`'s proven parent/depth
  shape but *uncapped* — unlike Thread's tight depth cap (which exists specifically to
  prevent unwanted fractal quest-sub-thread explosion), a rich nested world (world → region
  → settlement → building → room) is normal and wanted here, so there's no cap motivated by
  the same concern.
  - `parent_node_id` (self-FK, nullable) + `depth`.
  - Optional free-text `scale` label ("settlement," "deck," "floor" — whatever fits the
    setting), **not a hardcoded enum** — same reasoning as `AttributeDefinition`: a fixed
    `Literal["world","region","settlement","site"]` would bake in a fantasy-medieval-shaped
    ontology that breaks for a ship, a dungeon, a space station.
  - `x`/`y` are **local to the parent's coordinate space**, not global — a single global
    system can't meaningfully represent both a room and a continent in the same units.
  - **Cross-branch distance** (two locations that aren't siblings, e.g. an inn in village X
    vs. an inn in village Y): find the lowest common ancestor by walking both parent chains
    up (cheap with `parent_node_id`+`depth`), project each location down to whichever of its
    ancestors is a *direct child* of that LCA (those two share a parent, so their `x`/`y`
    are directly comparable), and compute distance there. This is an approximation at the
    scale where the branches diverge — appropriately so (you don't need room-level precision
    to know two inns are in different countries). Special cases: same node → distance 0; one
    node is an ancestor of the other → "contained within," not a numeric distance at all.
  - **"Nearby locations"** generalizes from v1's flat x/y-distance scan into "small computed
    distance via the above" — siblings naturally come back closest, but cross-branch
    comparisons now work too, unlike v1 where they were meaningless (single global
    coordinate system, no containment concept at all).
  - **Context budget for prompts**: full `description_long` for the current node, a short
    summary for its immediate parent, names only for anything further up — keeps prompts
    lean by default as the world gets deeper, rather than growing with world depth.
- Environmental simulation — weather, seasons, day/night as a real layer affecting danger
  levels and event odds (full depth, per your call — more world-sim ambition than v1 had).
- `ItemDef`/`InventoryItem`, `SpellDef`/`ActorSpell` — kept roughly as-is. Weapons are
  `ItemDef` rows with a weapon-specific mechanical profile (damage dice, properties) in the
  existing flexible `effect` JSON, not a separate table.
- `Ruleset` — pluggable interface built now, even though only the 5e-ish mechanics
  (ability mod, proficiency bonus, encumbrance formulas — ported directly from v1's
  `services/mechanics/`) are implemented behind it initially.
- **`AttributeDefinition`** (scoped to a `Ruleset`, campaign-overridable) — `key`,
  `display_name`, `abbreviation`, `description`, `sort_order`. No more hardcoded
  `STR`/`DEX`/`CON`/`INT`/`WIS`/`CHA` columns — `CharacterSheet.ability_scores` becomes
  `dict[key, int]` keyed by whatever the active ruleset defines. The default 5e-ish ruleset
  ships the standard six as *data*; a different ruleset or a thematic reskin
  ("Might/Grace/Wit/Spirit") is a data change, not a schema change.
- **`AncestryDef`** (internal name; campaign-configurable display label — "Race," "Species,"
  "Lineage") and **`ClassDef`** (label configurable too — "Class," "Path," "Vocation"):
  name, description, mechanical traits (attribute bonuses keyed by the ruleset's
  `AttributeDefinition` keys, speed/features for ancestry; hit die, proficiencies,
  spellcasting flag, starting-equipment suggestions for class).

### Entity creation — and why seeding is the same mechanism, not a separate one

A real gap noticed after Phase 2B: the typed-ops vocabulary (below) only covers Thread/
Clock/Hook — there was no way for the chain to create a new `Actor`, `WorldNode`,
`ItemDef`, `SpellDef`, or `Faction` at all. If the Narrator invents an NPC in prose, nothing
made that NPC structurally exist — it couldn't be referenced, remembered, or targeted by a
later Hook.

Fix: extend the same `WorldOp` discriminated union with `CreateActorOp`, `CreateWorldNodeOp`,
`CreateItemDefOp`, `CreateSpellDefOp`, `CreateFactionOp` — same `StrictOut` pattern, same
`World Update` review step, same trace. No new mechanism.

**This is also, deliberately, how the Campaign Seed Screen works.** v1's seeder had its own
bespoke entity-creation code, completely separate from its in-play world-update code, and
that duplication is exactly what caused two of the bugs found auditing v1 (the LLM's
understanding of "what does creating an NPC need" drifted between the two prompts over
time, because there were two sources of truth to keep in sync). In v2, seeding is *the same*
ops + `apply_op` pipeline, just run generatively across the wizard's steps (a big batch,
reviewed once at Step 6) instead of the single-turn "propose nothing unless warranted" bias
regular play's World Update uses. One mechanism, two calling contexts — never two
mechanisms.

**Guarding against near-duplicate entities** (the model creating a second "Elara" because it
didn't have her id handy) doesn't need Thread-style caps — entities don't have Thread's
fractal-explosion risk. Instead: feed a compact known-actors/known-locations catalog (id +
name only) into Opportunity Spotting and World Update, the same pattern `active_threads`
already uses — reference by id, don't reinvent. See "Context assembly" below for how this
catalog stays small as a campaign grows.

**Updates to an existing entity** (e.g. revealing an established NPC's secret) are a
different, riskier op than a create — mirrors the Hook gate exactly (new canon vs.
recontextualizing something established) rather than inventing a second rule for the same
underlying distinction.

### Narrative momentum: Thread, Clock, Hook
- **`Thread`** (replaces v1's `StoryThread` — and also replaces what would've been a
  separate "NPC agenda" or "faction goal" concept; they're all just Threads owned by
  different things): title, summary, status, `tier` (`major`/`minor`), `priority`
  (int, LLM/GM-settable — restores a field v1 had that Phase 2A's redesign dropped;
  needed so the world-update/context-assembly layers can surface "what matters most
  right now" without re-deriving it from scratch every turn), owner (nothing /
  Actor / Faction), `parent_thread_id` + `relation` (`prerequisite` / `alternative` /
  `optional_aid`), depth-capped (2-3 levels).
  - A **linear** sequence of steps (do A, then B, then C) is *not* three Threads — it's
    one Thread with a multi-stage `Clock`. A step only earns its own Thread row when it has
    genuinely independent weight (its own pacing, could be tackled out of order, has its
    own stakes/twist potential).
  - Creation is gated by **concurrent open count**, not per-turn creation count (a single
    narrative beat — an NPC recounting a whole quest chain — can legitimately spawn several
    connected stages/threads at once): major threads capped low (~2-3 active, tunable
    setting), minor threads capped per parent (~3-5 open at once, tunable).
  - New major thread → always requires approval (the single most expensive commitment the
    sim can make). New minor thread that only creates new canon → auto-accepted but logged,
    reversible. Anything that mutates *existing* canon (see Hook, below) → always requires
    approval regardless of tier.
- **`Clock`** — N segments on a Thread, can have multiple per thread (racing clocks, e.g.
  "players stop the ritual" vs. "ritual completes" — more interesting than one doom clock).
  Tick source is a typed enum (`time_elapsed` / `player_action` / `linked_thread_complete`),
  not "the LLM decides sometimes." `visibility` flag (hidden vs. player-visible — the witch
  curse ticks unseen until it manifests). Consequence-on-fill resolves through the same
  typed-ops system as everything else (spawn a thread, change a location's danger level,
  transform an NPC) — not a special-cased text field.
  - A `time_elapsed` clock also carries `real_time_per_segment` (e.g. "1 segment per 3
    in-game days") — this is what replaces Phase 2B's crude "+1 per call to `/world-tick`"
    placeholder. The real question raised mid-Phase-2B was "what if the player says 'I rest
    for three weeks' — is that one tick or seven?" The fix isn't a smarter tick, it's making
    time itself a first-class quantity: see `time_passed` below.

**What a "tick" actually is, now:** not a fixed unit ("one call = one tick"), but a quantity
of in-game time that clocks convert into segments at their own individual rate.
`Plausibility Check` gains a `time_passed` output (a duration — the LLM's read of how much
in-game time the player's stated action plausibly consumes: a conversation is minutes, a
short rest is hours, "I rest for three weeks" is exactly what it says). That duration
advances `Campaign.current_datetime` directly (a plain field addition, no new op needed —
this is bookkeeping, not narrative canon). World Sim Tick then converts elapsed real
game-time into segments *per clock*, using that clock's own `real_time_per_segment`
(`elapsed // real_time_per_segment`), instead of the flat +1 every clock got in the Phase 2B
placeholder. A three-week rest correctly fires several ticks on a clock with
`real_time_per_segment = 3 days`, and zero ticks on one paced in months — each clock reacts
to *how much time actually passed*, not to how many turns were taken.
- **`Hook`** — a proposed-but-not-committed narrative development (status:
  proposed/accepted/rejected). The gate for auto-accept vs. requiring approval is
  **structural, not LLM-self-judged severity**: does it only touch new entities (safe,
  auto-accept + log), or does it recontextualize something already established (always
  requires approval — e.g. "the party's cat is secretly a demon" mutates an existing
  Actor's nature, which is exactly the kind of silent retcon that breaks player trust if
  it isn't reviewed). Hooks are also the mechanism for curiosity-as-trigger (principle #3):
  investigating an un-threaded entity gives Opportunity Spotting an elevated, explicit
  chance to propose one.
- **`Faction`** — first-class object: goals, resources, reputation, relationships with
  other factions. Pursues its own agenda through the same Thread/Clock system as everything
  else — a faction's "war preparations" is a Thread owned by the Faction, no separate
  mechanism needed.
- **World Sim Tick** — separate process from the per-action chain, triggered by elapsed
  in-game time (via `Campaign.current_datetime` deltas, advanced by each turn's
  `time_passed` — see above; resting a week fires several ticks' worth of world movement at
  once on fast clocks, and none on slow ones, not a flat +1 regardless of duration).
  Evaluates every active Thread regardless of player engagement; consequences may surface
  immediately or later as something the player discovers.
  - Phase 2B's `POST /campaigns/{id}/world-tick` endpoint and its flat-+1-per-clock behavior
    was always scoped as a placeholder ("manually-triggered, real scheduling is Phase 5" —
    see that phase's plan note); the `real_time_per_segment` conversion above replaces the
    +1 arithmetic in that same endpoint without touching its trigger model (still manual
    for now, automatic scheduling is still Phase 5's job, not this one).

### Context assembly
Every generate node needs *some* slice of world state (active threads/clocks, known-entity
catalogs, the current `WorldNode` + budgeted parent chain, tone state, etc.), and right now
that's assembled ad hoc, inline, in `api/turns.py`. That's already the second time the
"known-entities catalog" pattern above has been reinvented (`active_threads` in 2A,
known-actors/known-locations for entity creation just above) — a sign it should be one
small service (`services/context_assembly.py` or similar), not copy-pasted per node.
Scope: pure read/shape functions (given a campaign + current turn state, return the trimmed
dicts each prompt builder needs), no new persistence or mutation. Not urgent enough to block
Phase 3, but worth doing *during* Phase 3 once the entity-creation catalogs and location
hierarchy context (full detail for current node, summary for parent, names above that) are
both real — better to write the budgeting logic once, in one place, than duplicate it a
third time.

### Memory, reputation, lore
- `Memory` — kept from v1 as the **single** source of truth for what an actor remembers
  (owner/subject/importance/text). v1 had this competing with `ContextBlock type=memory`;
  that duplication is gone.
- `Reputation` — new, real tracked mechanic: per-NPC (and per-Faction) standing toward the
  player that concretely affects dialogue tone, prices, and thread outcomes — not just
  narrative flavor inferred from Memory rows. Not needed for Phase 3's walking skeleton;
  targeted for Phase 4, where dialogue/pricing UI first has something to actually show.
- `LoreDocument`/`LoreChunk` — kept and consolidated (v1 had three overlapping lore
  representations — `LorePage`, `LoreDocument`/`LoreChunk`, and `ContextBlock` lore hints;
  this keeps only the chunked/embedded one, which is the one actually used for retrieval).
  Not in Phase 3 scope, but has a hard deadline: Phase 4's codex search UI (see roadmap)
  depends on the embed/retrieve pipeline existing, so this must land no later than early
  Phase 4, not drift further.
- **`ContextBlock` and `LorePage` are gone entirely.** Locations and actors render to the
  narrator straight from their real tables — always fresh, never a stale duplicate. What
  was genuinely ephemeral (retrieved lore clips for a specific turn) isn't persisted as
  world state at all; it becomes part of that turn's chain trace (see below), because it's
  a record of *how a turn was generated*, not canon.

### Narrator configuration and tone
- **`NarratorProfile`** — a saved, swappable persona: style description ("Shakespearean,"
  "terse and spoken"), verbosity target (short/spoken-style by default — v1's narrator was
  verbose by design, that's being reversed), tone-response rules. Data, not hardcoded
  prompt text — editable from the settings area.
- **`ToneState`** — evolving per-campaign tension (calm → building → tense → dangerous →
  climactic), computed each turn, drives narration sharpness on top of the base
  `NarratorProfile`. **Prose only** — it never touches DCs or mechanics, by design, so the
  world never feels like it's secretly cheating the player because the story got tense.

### The chain trace (this is what makes steerability real)
- **`TurnRun`** — one per player action (or per World Sim Tick), containing an ordered list
  of `ChainStep`s.
- **`ChainStep`** — node type, input snapshot, raw LLM (or oracle) output, status
  (pending/approved/edited/retried), final output actually used, timestamps. This replaces
  v1's flat `Event.result_data` JSON blob with something the frontend can render live via
  WebSocket and the player/GM can intervene on at any point before it feeds the next step.
  This same structure is what makes full git-like replay/branching possible later — since
  every turn's inputs and outputs are already structured and stored, rewinding to any past
  `TurnRun` and forking is a query, not a redesign.

## The LLM chain, per player action

Decomposed from v1's single monolithic `gm_plan` call (which is part of why its output was
long and unfocused) into small, single-purpose, independently steerable nodes — also more
reliable individually for a small local model than one call trying to reason about five
things at once:

1. **Intent Parse** — what is the player trying to do.
2. **Plausibility Check** — "is that actually possible?" given established fiction. Can
   output feasible / feasible-with-a-twist / not feasible (+ what happens instead).
3. **Thread Tick** (action-triggered slice of the same logic the time-driven World Sim Tick
   uses) — do any active threads move because of what the player just did or pointedly
   ignored.
4. **Opportunity Spotting** — proposes `Hook`s, including curiosity-triggered ones.
   Decision surface, cheapest first: *beat* (no object) → *stage* (extend an existing
   thread's clock) → *minor thread* (child, independent weight) → *major thread*
   (independent stakes) — capped and approval-gated per the Thread rules above.
5. **Mechanical Check** — roll needed? (runs after plausibility, so we don't roll for
   things that aren't actually possible).
6. **Tone Assessment** — updates `ToneState`.
7. **Plan Synthesis** — combines 2-6 into the actual beat-plan for the narrator.
8. **World Update** — commits typed ops.
9. **Narrator** — `NarratorProfile` + `ToneState` + explicit length target → prose. Short,
   spoken-style by default.
10. **Memory Regression** — schema-strict `create_memory` ops (v1 had this silently no-op
    for an entire session because of exactly the "prose drifted from schema" bug principle
    #2 exists to prevent).

**Mythic GME mode** (separate campaign-level toggle, later phase): replaces steps 2/4/6
with oracle mechanics — Fate Chart yes/no rolls against a Chaos Factor, Meaning Table
word-pair interpretation, Chaos-Factor-driven random events — instead of LLM judgment. Built
as a different *kind* of `ChainStep` (deterministic/oracle vs. LLM-generated) in the same
trace, so it doesn't need its own UI. Build the swap point now; build the actual Fate
Chart/Chaos Factor/Meaning Table content later.

## Battle mode

Phased, not narrative-abstraction-only as originally scoped:

- **v1 (this rewrite): structured action picker.** Click a spell/attack from your sheet,
  see **abstract range bands** (adjacent / near / far / out of range) to enemies rather than
  a coordinate grid. Still resolved underneath by rolls + narration, but gives real tactical
  choice without the cost of a positioning engine.
- **Future iteration: full tactical.** Real coordinates, generated battle maps,
  positioning/movement — explicitly deferred, tracked below so it isn't lost.

## Downtime mode

Currently a stub in v1 (a `Campaign.mode` that nothing branches on) — same problem battle
mode had, fixed the same way: real **structured activities** (crafting, research,
carousing, training, business/faction management) instead of falling through to generic
narration. Each activity type is its own small, focused chain path reusing the same
Plausibility/Mechanical-Check/Narrator nodes, not a separate system.

## Platform features

- **Replay/branching** — full git-like: rewind to any past `TurnRun`, fork an alternate
  timeline, keep multiple branches per campaign. Enabled directly by the `TurnRun`/
  `ChainStep` structure above.
- **Multi-campaign manager** — campaign list/switcher from the start, not bolted on later.
- **Causality log** — player-facing timeline ("this happened because you ignored that"),
  built from Thread/Clock/Hook history — part of the actual game experience, not a debug
  tool.
- **"While you were away" digest** — specifically surfaces what the *World Sim Tick* changed
  off-screen (a location's danger rose, a faction moved) when you return to a campaign.
  Distinct from the causality log: this is "what happened without you," not "why did this
  happen."
- **Out-of-character (OOC) instruction channel** — a first-class way to directly steer
  *future* chain output ("OOC: slow down," "OOC: introduce a character named X"), separate
  from editing a `ChainStep`'s output after the fact. Chain-level steering, forward-looking
  rather than corrective.
- **Settings page** — the runtime `Settings` hot-swap surface described above.
- **Model comparison** — toggleable, run the same turn through two models/configs
  side-by-side; lives in Settings.
- **Export/import** — backup/portability focus (move your own campaign between instances,
  restore a backup), not primarily a sharing mechanism.
- **Sessions** — implicit only, no `Session` entity; recap is computed on demand from the
  rolling campaign summary.
- **Auth** — real multi-user, toggleable off for local single-user no-auth use.
- **Observability** — Prometheus/OTel kept, now per-`ChainStep`-type instead of per-role,
  which is much more useful once the chain is this decomposed.
- **Testing** — chain nodes are independently unit-testable (mocked LLM responses, assert
  routing/caps/gating logic) — v1 had zero tests; this is a real gap being closed by the
  rewrite's shape, not a bolted-on effort.

## Frontend

Separate **Play** mode and **Editor** mode:
- **Play** — live session view: transcript, the steerable chain trace streaming in via
  WebSocket (approve/edit/retry any step), current scene/world-state panels, tone
  indicator. Also: a real character sheet UI (not raw JSON), inventory/equipment
  management, an animated dice roller instead of typing a number, an "ask the codex"
  semantic search bar over lore/NPCs/locations (reuses the same pgvector retrieval the
  narrator uses internally, exposed as a player tool), and a private player notes/journal
  separate from the sim-generated causality log.
- **Editor** — direct management of NPCs, lore, threads, factions, narrator profiles,
  ruleset config, outside of live play.
- Plus a lightweight campaign browser (multi-campaign manager), the Settings page, and the
  Campaign Seed screen (below).
- **Accessibility** is a baseline requirement, not a later pass: font size, contrast,
  reduced motion, and a dyslexia-friendly font option, built in from the start rather than
  retrofitted.

## Campaign Seed Screen

The first `TurnRun` in every campaign — a guided wizard that follows the same
propose→review→commit pattern as the rest of the chain: free text goes in, the LLM proposes
a structured interpretation, you review/edit it before any world-gen calls actually fire.

**Step 1 — World**: free-text world description; optional inspiration tags ("Dark Souls +
Redwall"); world size (small/medium/large); magic level; tech level; a "must include"
wishlist (seeds high-priority Threads/Hooks the sim actively tries to weave in, rather than
leaving it to chance); **races & classes** — "use the standard 5e set" vs. "generate
setting-specific ones for this world" (cheap convenience toggle so a default-fantasy
campaign doesn't burn LLM calls reinventing Elves and Fighters from scratch).

**Step 2 — GM persona**: free-text GM description, deriving a `NarratorProfile` (verbosity,
humor, formality) shown for editing; **player agency stance** (sandbox vs. guided story);
**system-talk transparency** (does the GM ever say "make a Perception check" out loud, or
stay fully diegetic); **narrative volatility** (how eagerly Opportunity Spotting proposes
twists — this is literally the "likes to randomize things" dial).

**Step 3 — Harshness & difficulty**: a single **brutality** slider (cozy → standard →
gritty → deadly) mapping to DC curve, lethality, consequence severity, and resource
scarcity, with an advanced expansion to break these apart. Explicitly a **deliberate,
static campaign setting** — unlike `ToneState`, which only ever affects prose, this is the
one place difficulty is allowed to touch mechanics, because the player chose it up front,
not because the story felt tense. Also: **content boundaries/safety tools** (hard limits,
soft limits/fade-to-black — standard "lines and veils").

**Step 4 — Make it feel alive** (optional, all skippable): the PC's **personal drive**
(distinct from the world premise — why is *my character* doing this, shapes which Hooks get
prioritized); a **player-known secret** (something true about the world your character
doesn't know yet — dramatic irony seeded with your buy-in); **starting relationships** (a
rival, a mentor, a debt); **1-3 starting rumors** circulating at session start; one or two
**pre-seeded named NPCs** you hand-place instead of leaving to generation; **starting world
temperature** (already mid-crisis vs. quiet-and-about-to-be-disturbed — sets the initial
`ToneState` baseline); explicit **start date/season/time-of-day**.

**Step 5 — Simulation & advanced** (collapsed by default): Mythic GME mode toggle; World Sim
Tick cadence (daily vs. weekly off-screen evaluation — trades "how alive the world feels"
against LLM-call volume); Thread concurrency caps; ruleset selection; party composition
(add more than 1 PC now if wanted).

**Step 6 — Review & generate**: everything above as an editable summary before the seeding
chain actually runs and starts spending LLM calls — including the generated
`AttributeDefinition`/`AncestryDef`/`ClassDef` set and starter spells/weapons, reviewed and
editable like everything else in the chain.

**Step 7 — Party creation**: for each PC (still scoped to 1), pick an Ancestry + Class from
the generated/seeded set, then **roll for stats** (dice formula is ruleset-configurable,
e.g. 4d6-drop-lowest — reuses the animated dice roller from Play mode) or **point buy**
(pool size + cost curve also ruleset-configurable, not hardcoded to 5e's 27-point curve),
assign to the ruleset's named attributes, and see computed derived stats (HP, proficiencies,
starting gear) before confirming.

## What carries forward from v1 regardless of any of the above

- **LM Studio request shapes** — `/v1/chat/completions` with
  `response_format.json_schema`, `/v1/embeddings` with a separate embedding model. Verified
  working against `google/gemma-4-e4b` + `text-embedding-nomic-embed-text-v1.5`. Reference:
  `backend/app/services/llm/lmstudio_client.py`.
- **Deterministic mechanics formulas** — ability mod `floor((score-10)/2)`, 5e-style
  proficiency bonus by level, encumbrance `STR * 15`. `backend/app/services/mechanics/`.
- **Docker networking for a host-run LM Studio** — `host.docker.internal` +
  `extra_hosts: ["host.docker.internal:host-gateway"]`. `backend/docker-compose.yml`.
- **pgAdmin auto-config pattern** — preloaded `servers.json` +
  `PGADMIN_CONFIG_SERVER_MODE=False` for a login-free local dev instance.
  `backend/pgadmin/servers.json`.

## Explicitly deferred (named so it doesn't get lost, not because it's unimportant)

- Mythic GME's actual content (Fate Chart, Chaos Factor tuning, Meaning Tables) — the chain
  hook-point is built now, the content comes later.
- Real shared multiplayer (multiple humans live in one campaign) — data model doesn't block
  it, real-time sync is a separate project.
- **Full tactical battle mode** — real coordinates, generated battle maps, positioning —
  v1 ships the structured action-picker version above instead.
- **Image generation** — NPC portraits, location art. Toggleable like everything else once
  it exists; needs its own generation pipeline, not something LM Studio's chat/embedding
  endpoints cover.
- **TTS narration readout** — needs a separate local TTS engine; accessibility- and
  immersion-flavored, worth doing but not blocking.
- **Adaptive difficulty assist** — opt-in "story mode" easing when a player is repeatedly
  struggling. Needs to be built carefully (transparent, never secret rubber-banding), so
  it's sequenced deliberately rather than bolted on early.
- **Campaign-health dashboard** (thread balance, faction dominance, pacing over time, for
  you as meta-GM) — needs real campaign history to be useful, so it's more valuable once
  there's actual usage data than it would be at launch.
- **Shareable highlight/quote-card export** of a cool moment — fun, low priority.
- **Discord/webhook notifications** for async or play-by-post style use — makes most sense
  once hosting/multi-user is actually in use, not before.

## Next step

This spec is the converged output of the workshop; implementation planning (repo scaffold,
migrations, LangGraph graph definition, FastAPI routes, React app structure) is a separate
concrete plan to build next, grounded in this document.
