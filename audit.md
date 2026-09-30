# Storybard v2 — Audit & Playtest Findings

Produced by reading the current codebase (commit `36355b7` + the uncommitted working-tree
diff on top of it) and live-playtesting against the running stack (Docker Compose + LM
Studio, `google/gemma-4-e4b` default / `qwen/qwen3.8-27b` creative / `text-embedding-nomic-
embed-text-v1.5`). Not a list of everything reviewed — see `CODEBASE_OVERVIEW.md` for the
architecture description this builds on. This is findings only.

**Overall gut-check**: the uncommitted work is unusually clean for mid-flight WIP — every
new domain table has a matching migration with correct FKs/indexes and a linear revision
chain, `apply_op` has 100% dispatch coverage of the `WorldOp` union, and `except Exception`
usage is narrow and justified rather than the silent-swallow anti-pattern v1's `spec/
bugs.md` explicitly warns against. It's close to committable. The items below are what's
worth fixing before or shortly after that.

## Narrative quality verdict (5 turns played)

Played 5 consecutive turns as a lighthouse keeper (Elias Thorne) investigating strange
catches in a seeded cosmic-horror coastal campaign ("The Deep Tide"). Judging the actual
play experience, separate from the technical bugs above:

**What's genuinely good:**
- **Prose quality is strong** — concrete sensory detail, real dialogue with distinct voices
  (Marta Vane's flat monotone vs. Elias's breathless twitchiness), no purple-prose padding.
  Matches the "grim and atmospheric" style requested at seed time.
- **Rolls are honored honestly and narrated with texture**, exactly per design intent — a
  narrow DEX failure in turn 2 became a fumbled grab with real consequences (dropped fish,
  village noticing), not a flat "you fail." A clean STR success in turn 4 read as
  effortless. This is the single best-executed design principle in the whole system.
- **Pacing/escalation across 5 turns is genuinely well-shaped**: arrival → failed
  investigation → NPC confrontation/reveal → physical confrontation + ultimatum → a timed
  race with a twist complication and a cliffhanger. That's a real five-beat structure, not
  a flat sequence of disconnected vignettes — it reads like competent GMing, not a chatbot.
- **The Twist node fired on schedule (turn 5, matching the default frequency) and landed
  well** — the fog turning into a "living membrane," the beam locking still, Silas Kade
  approaching with the keeper's coordinates — a real complication, not a non-sequitur.
- **The seeded must-include elements actually got woven in**, not just name-dropped: debts,
  isolation, and the wrong catches are all load-bearing to the plot by turn 5, not
  decorative flavor text abandoned after the opening scene.

**What actively breaks the experience:**
- **The name-collision bug (finding #1/#5)** turned into the single worst moment of the
  playthrough — the model built an entire interrogation scene where a random seeded NPC
  confesses the player's own backstory back to them. It's narratively confusing in a way
  that isn't "interesting unreliable narrator," it's just a data bug bleeding into the
  fiction.
- **The turn-5 verbatim-duplication bug (finding #4)** is severe: a player would have
  scrolled through ~4,800 characters of text they already read before reaching one new
  paragraph. If this scales with campaign length (worth checking — it's plausibly a
  context-size threshold effect), long campaigns could degrade badly over time as
  `recent_turns` context grows.
- **Play was interrupted by 500s repeatedly** during this 5-turn session (see reliability
  findings below) — even with clean DB-level rollback keeping state consistent, a real
  player would have hit "Internal Server Error" and had no idea whether to retry, refresh,
  or restart, several times in five turns. However the system behaves internally, that's
  not an acceptable frequency of visible breakage for something meant to feel like sitting
  across from a GM.

**Overall**: when it works, this is a legitimately good GM — better pacing discipline and
mechanical honesty than most "let the LLM improvise everything" implementations. But in
this session it didn't reliably work: one session-breaking continuity bug, one
severity-escalating context bug, and multiple raw crashes in 5 turns. The chain design and
prose quality are ahead of the reliability/correctness layer right now.

## Playtest log

Seeded a full campaign live end-to-end: pitch → propose → commit (33 ops applied), created
a Human Fighter via point-buy, pulled the opening scene, then played 2 full turns through
every chain node (including a real DEX check that failed clean and was narrated
truthfully). The core loop works. Three concrete problems surfaced only by actually running
it:

### 1. [bug, high] Player/NPC name collision → Narrator self-duplication

Seeding produced an NPC actor literally named **"Elias Thorne"** — identical to the
player's own character name (also "Elias Thorne", chosen at pitch time). Confirmed via
`GET /world-state`: two distinct `Actor` rows, same name, `kind="player"` vs `kind="npc"`.

Root cause: `seed_narrative_prompt` (`server/src/storybard/chain/prompts.py:696`) never
receives `player_actor_name` — `propose_seed` (`chain/seed_service.py:194-206`) doesn't
pass it, so nothing stops the LLM reusing it for a generated NPC.

Consequence, reproduced in **both** turns played: the Narrator described the player
simultaneously as "you" (the acting character) and as a separate third-person figure
——

> "From the shadows, Elias Thorne steps forward, his left eye twitching violently... He has
> seen you fail."

This is the same failure *shape* a docstring in `context_assembly.py:65-72` says was
already fixed once — an NPC narrated "as having been watching from the shadows" with no
actual staging — but that fix (the `present` flag) only solves staging/presence, not
identity collision. A different root cause, not caught previously.

**Fix**: pass `player_actor_name` (and ideally the full known-names list) into
`seed_narrative_prompt`, with an explicit instruction not to reuse it; reject/regenerate on
collision at commit time as a backstop.

### 2. [gap, med] Seed propose latency has no feedback and risks client timeouts

The narrative seeding call (`SeedNarrativeOut`, creative model) took **184 seconds** for a
single LLM call producing 33 ops — confirmed via server logs
(`lmstudio.request_started` → `request_completed`, `duration_s: 184.3`). A 180s client
timeout (a reasonable default) cuts it off with no response, even though the server
completes the work successfully. In `races_classes_mode="generate"`, a second creative-tier
call (`seed_content_prompt`) stacks on top of this one, likely pushing total wait past
5 minutes.

**Fix**: stream partial progress (SSE/WebSocket, same mechanism turns already use) or at
minimum set explicit client-side expectations ("this takes 3-5 minutes") in `SeedWizard.tsx`
rather than a generic spinner risking a false-negative timeout.

### 3. [gap, med] Orphaned paused turn after a server restart — confirmed, not just theoretical

Reproduced from server logs: a container restart (8 min uptime vs. 21h for `db`/`web`)
orphaned a turn paused mid-review. Resuming it crashed:

```
File "/app/src/storybard/chain/graph.py", line 335, in node
    return {"narration": resolved["narration"]}
KeyError: 'narration'
During task with name 'narrator_review'
```

This is the exact, already-documented gap (`spec/spec.md`: `InMemorySaver` "is a known,
tracked gap, not a final choice... swapping to `AsyncPostgresSaver`... is contained,
low-risk, and overdue") — now confirmed to fail as a raw unhandled 500 rather than
degrading gracefully. `GET .../current-turn` correctly recovers a turn that's still live in
the running server's memory, but has no way to detect *this* case (checkpoint genuinely
gone) and surface a clean "this turn's session expired, abandon and retry" instead of
propagating the `KeyError`.

**Fix**: the swap to `AsyncPostgresSaver` is the real fix (already flagged as overdue
elsewhere); short of that, wrap `advance_turn`'s `graph.ainvoke` in a handler that turns a
missing-checkpoint resume into a clean 409/410 with a recovery hint, not a 500.

### 4. [bug, high] Narrator verbatim-echoes prior turns into new narration under context load

Played 5 turns in one campaign. On turn 5, `TurnRun.final_narration` ballooned to **5,476
characters** — confirmed at the DB level, `raw_output->>'narration'` on the `narrator`
`ChainStep` itself, so this is the raw LLM output, not an app-side concatenation bug. Every
other turn in the same campaign was 700-1,550 chars. Inspecting the text: the first ~4,800
characters are a **word-for-word repeat of turns 1 through 4's entire narration**, and only
the final ~650 characters are actually new content continuing the scene. The `## Recent
exchange` block in `narrator_prompt` (`chain/prompts.py:930`) renders the last 5 turns'
full player/narrator text into the prompt as continuation context — nothing in the system
prompt tells the model not to reproduce it. By turn 5 the prompt for this call was already
~17-22K characters (`lmstudio.request_started` logs, `prompt_chars` field); the smaller
local creative model appears to have echoed the transcript back instead of continuing from
it under that load. Reproduced once, not yet confirmed as deterministic/frequency, but the
mechanism (unbounded verbatim transcript re-render, no anti-echo instruction, no
output-length sanity check) is real and will recur as campaigns grow.

**Fix**: add an explicit instruction against repeating/restating the "Recent exchange"
verbatim; consider a cheap guard (reject/retry if the new narration's prefix matches the
tail of `recent_turns` above some similarity threshold) as a backstop, the same spirit as
the existing `_generate_mechanical_content` retry-once-on-under-production pattern in
`seed_service.py`.

### 5. [compounding effect of finding #1] Name collision actively corrupted the fiction, not just cosmetically

Across turns 3-5 of the same playtest, the duplicate NPC "Elias Thorne" (see finding #1
above) didn't just appear as a background inconsistency — it became a major speaking
character who confesses to "selling his soul to the deep to pay his debts" and being
hunted by a "Consortium" collecting "the keeper's name," i.e., delivering the **player's
own stated pitch premise** back to the player as somebody else's backstory. The model never
self-corrected or flagged the collision; it built an entire confrontation/interrogation
scene around it. This isn't just a minor continuity blemish — it actively undermines the
premise the player set up at seed time. Reinforces that finding #1's fix (excluding the
player's name from seed-time NPC generation) is worth prioritizing over the other seeding
gaps.

## Static code-audit findings (uncommitted diff)

Ordered roughly by severity.

- **[bug, high]** `MechanicalCheckOut.skill` is hardcoded to
  `Literal["str","dex","con","int","wis","cha"]`
  (`server/src/storybard/services/llm/schemas.py:50`) — contradicts the project's own
  explicit design principle (`domain/ruleset.py`, `ClassDef` docstring) that ability keys
  are campaign data, not schema ("a thematic reskin... is a data change, not a schema
  change"). In a reskinned/custom-ruleset campaign, `mechanical_check` can never name the
  real ability key; `roll_resolution_generate` (`graph.py:191`) then does
  `ability_scores.get(ability_key, 10)`, silently defaulting every roll to "average
  ability" instead of the character's real sheet. Silently wrong mechanics, not a crash —
  exactly the failure class `spec/bugs.md`/`spec.md` call out as the lesson from v1.

- **[gap, high]** No `WorldOp` exists to grant/create an `InventoryItem` on an actor during
  play. `InventoryItem` (`domain/inventory.py`) is only ever instantiated by
  `seed_service.py:345` at campaign creation. `CreateItemDefOp` lets the chain invent a new
  item *template*, but nothing can ever attach an instance of it to an actor afterward — a
  shopkeeper handing over a potion, or looting a corpse, has no structural op to land on.

- **[gap, med]** `PlantedReveal.revealed` (`domain/reveal.py`) is never set anywhere in the
  codebase (zero hits outside the model definition). No GM-facing endpoint exists to read
  or flip it either. Write-once dead data — seeded, never consumed — despite
  `ThreadBeat`'s own docstring calling a reveal "a natural first consumer once a Twist node
  exists." The Twist node now exists (`graph.py:242`) but doesn't reference it.

- **[low]** No endpoint anywhere in `api/` lets a human move a `Hook` with
  `status="proposed"` to `accepted`/`rejected`. Per the design, any hook that
  `touches_entity_id` (recontextualizes existing canon) requires review and is never
  auto-accepted — but there's no way to actually grant that review. Confirmed still true in
  the current diff; `SceneWorldRail.tsx` can display it, nothing can resolve it.

- **[low]** `Clock.consequence_op` (`domain/clock.py`) is read by `ops.py:569-572`
  (`_tick_clock`) but no op anywhere sets it — dead branch, reachable only via direct DB
  manipulation. Honestly documented as a known gap in `CODEBASE_OVERVIEW.md`; worth deleting
  or wiring, not leaving live.

- **[low]** `api/turns.py::create_turn` (~lines 113-178) issues roughly 10 independent
  context-assembly reads sequentially (scene, narrator profile, campaign settings, active
  threads/clocks, known actors/locations, profile, sheet, recent turns, embedding call,
  memories, recent world events, npc impressions, idle-turn count) instead of batching
  independent ones with `asyncio.gather`. Small next to the 15-30s-per-call LLM chain that
  follows, but a free, safe win since none of these reads depend on each other.

- **[low]** Test coverage gap: `InventoryItem` and `PlantedReveal` are exercised only
  incidentally inside `test_seed_service.py` (creation path via seeding). No test covers an
  `InventoryItem` with `quantity > 1` or `equipped=True`, and none touches
  `PlantedReveal.revealed` at all (unsurprising, since nothing sets it — see above).
  `ThreadBeat` fire/abandon, by contrast, is well covered (`test_ops.py:727-761`).

## Structural improvement options (not scoped into a plan — for discussion)

- **Reliability**: swap `InMemorySaver` → `AsyncPostgresSaver` (already a dependency) so a
  restart doesn't orphan paused turns; make the orphaned-checkpoint case fail as a clean,
  recoverable API error instead of an unhandled 500.
- **Seeding correctness**: feed the player's chosen name (and ideally a compact known-names
  catalog) into every seed-time entity-generation prompt, closing the collision gap the
  in-play World Update path already guards against via `known_actors`/`known_locations`.
- **Ruleset flexibility**: replace the hardcoded ability `Literal` in `MechanicalCheckOut`
  with a value validated against the campaign's own `AttributeDefinition` keys, closing the
  silent "average ability" fallback.
- **Inventory as a real mechanic**: add a `grant_item`/`take_item` (or similar) op so loot,
  shops, and rewards can actually happen after session zero, not just at seed time.
- **Seeding latency**: stream/chunk the narrative seed call, or at minimum set honest
  wait-time expectations in `SeedWizard.tsx` instead of a generic spinner that risks a
  false-negative client timeout.
- **Hook lifecycle**: add the missing accept/reject endpoint so entity-touching hooks stop
  being permanently stuck in `proposed`.
