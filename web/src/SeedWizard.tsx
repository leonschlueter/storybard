import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type SeedInput, type SeedProposal, commitSeed, pitchSeed, proposeSeed } from "./lib/api";
import { Sparkles, Wand2 } from "lucide-react";
import { Button } from "./components/Button";
import { Card } from "./components/Card";

// Scoped to exactly what chain/seed_service.py's SeedInput accepts today (spec.md's Step
// 1/2/6 fields — world description, races/classes mode, GM style, must-include wishlist,
// review-before-commit). Steps 3/4/5's fields (brutality, safety tools, personal drive,
// Mythic toggle, etc.) have no backend yet — see the Phase 3C plan for why they're not here.

const DEFAULT_INPUT: SeedInput = {
  campaign_name: "New Campaign",
  world_name: "Oakhaven",
  world_description: "A quiet crossroads town on the edge of a dark forest.",
  inspiration_tags: [],
  races_classes_mode: "standard_5e",
  narrator_style_description: "Plain, direct, spoken-style.",
  player_actor_name: "Arin",
  must_include: [],
  seed_npc_count: 3,
  seed_hook_count: 3,
  seed_npc_relationships: true,
  seed_rumor_count: 3,
  seed_location_depth: 2,
  seed_calendar_from_pitch: true,
  seed_always_faction: true,
  seed_session_zero: true,
  seed_starting_inventory: true,
  seed_starting_inventory_count: 3,
  seed_planted_reveal: true,
  safety_tools: "",
  personal_stakes: "",
  calendar_context: "",
};

// Which ops each reroll button replaces (feature #9's partial reroll) — see handleReroll.
const REROLL_OP_TYPES: Record<string, string[]> = {
  "NPCs & relationships": ["create_actor"],
  "Hooks & rumors": ["propose_hook"],
  Locations: ["create_world_node"],
};

const FIELD = "block text-sm text-ink-300 mb-1";
const INPUT =
  "w-full bg-ink-900 border border-ink-700 rounded-lg px-3 py-2 text-sm text-ink-100 focus:outline-none focus:border-ember-500";

export default function SeedWizard() {
  const navigate = useNavigate();

  const [step, setStep] = useState<"setup" | "review">("setup");
  const [setupTab, setSetupTab] = useState<"describe" | "details">("describe");
  const [pitch, setPitch] = useState("");
  const [form, setForm] = useState<SeedInput>(DEFAULT_INPUT);
  const [inspirationTagsText, setInspirationTagsText] = useState("");
  const [mustIncludeText, setMustIncludeText] = useState("");
  const [proposalDraft, setProposalDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField<K extends keyof SeedInput>(key: K, value: SeedInput[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handlePitch() {
    setBusy(true);
    setError(null);
    try {
      const generated = await pitchSeed(pitch);
      setForm(generated);
      setInspirationTagsText(generated.inspiration_tags.join(", "));
      setMustIncludeText(generated.must_include.join("\n"));
      setSetupTab("details");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleGenerate() {
    setBusy(true);
    setError(null);
    try {
      const input: SeedInput = {
        ...form,
        inspiration_tags: inspirationTagsText
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        must_include: mustIncludeText
          .split("\n")
          .map((t) => t.trim())
          .filter(Boolean),
      };
      const result = await proposeSeed(input);
      setProposalDraft(JSON.stringify(result, null, 2));
      setStep("review");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleReroll(category: string) {
    const opTypes = REROLL_OP_TYPES[category];
    setBusy(true);
    setError(null);
    try {
      const input: SeedInput = {
        ...form,
        inspiration_tags: inspirationTagsText.split(",").map((t) => t.trim()).filter(Boolean),
        must_include: mustIncludeText.split("\n").map((t) => t.trim()).filter(Boolean),
      };
      const fresh = await proposeSeed(input);
      const current = JSON.parse(proposalDraft) as SeedProposal;
      // Never replace the root world node (its identity is fixed once review starts) —
      // only child locations count as "Locations" for the reroll.
      const isRoot = (op: Record<string, unknown>) => op.op === "create_world_node" && !op.parent_node_id;
      const matches = (op: Record<string, unknown>) => opTypes.includes(op.op as string) && !isRoot(op);
      const freshMatching = fresh.ops.filter(matches);
      const keptOthers = current.ops.filter((op) => !matches(op));
      const merged: SeedProposal = {
        ...current,
        ops: [...keptOthers, ...freshMatching],
        planted_reveal: opTypes.includes("propose_hook") ? fresh.planted_reveal : current.planted_reveal,
      };
      setProposalDraft(JSON.stringify(merged, null, 2));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    setBusy(true);
    setError(null);
    try {
      const edited = JSON.parse(proposalDraft) as SeedProposal;
      const result = await commitSeed(edited);
      navigate(`/campaigns/${result.campaign_id}/party/${result.player_actor_id}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function handleBack() {
    setProposalDraft("");
    setStep("setup");
  }

  return (
    <div className="min-h-screen flex justify-center px-6 py-10">
      <div className="max-w-2xl w-full">
        <h1 className="font-serif text-3xl text-ink-100 mb-6 flex items-center gap-2.5">
          <Sparkles className="w-6 h-6 text-ember-400" /> New Campaign
        </h1>

        {error && <pre className="text-ember-300 text-xs mb-4 whitespace-pre-wrap">{error}</pre>}

        {step === "setup" ? (
          <Card variant="elevated">
            <div className="flex gap-2 mb-5">
              <Button
                variant={setupTab === "describe" ? "primary" : "secondary"}
                onClick={() => setSetupTab("describe")}
              >
                Describe it
              </Button>
              <Button
                variant={setupTab === "details" ? "primary" : "secondary"}
                onClick={() => setSetupTab("details")}
              >
                Fill in manually
              </Button>
            </div>

            {setupTab === "describe" && (
              <div className="flex flex-col gap-3 mb-2">
                <label>
                  <span className={FIELD}>What kind of campaign do you want to play?</span>
                  <textarea
                    className={INPUT}
                    rows={4}
                    value={pitch}
                    onChange={(e) => setPitch(e.target.value)}
                    placeholder="A grim nautical horror campaign about a cursed whaling ship."
                  />
                </label>
                <Button
                  onClick={handlePitch}
                  disabled={busy || !pitch.trim()}
                  icon={<Wand2 className="w-4 h-4" />}
                >
                  {busy ? "Generating..." : "Generate inputs"}
                </Button>
                <p className="text-xs text-ink-500">
                  This fills in the fields under "Fill in manually" — nothing is created yet, review and edit them there first.
                </p>
              </div>
            )}

            <div className={`flex-col gap-4 ${setupTab === "details" ? "flex" : "hidden"}`}>
              <label>
                <span className={FIELD}>Campaign name</span>
                <input className={INPUT} value={form.campaign_name} onChange={(e) => updateField("campaign_name", e.target.value)} />
              </label>

              <label>
                <span className={FIELD}>World name</span>
                <input className={INPUT} value={form.world_name} onChange={(e) => updateField("world_name", e.target.value)} />
              </label>

              <label>
                <span className={FIELD}>World description</span>
                <textarea
                  className={INPUT}
                  rows={3}
                  value={form.world_description}
                  onChange={(e) => updateField("world_description", e.target.value)}
                />
              </label>

              <label>
                <span className={FIELD}>Inspiration tags (comma-separated)</span>
                <input
                  className={INPUT}
                  value={inspirationTagsText}
                  onChange={(e) => setInspirationTagsText(e.target.value)}
                  placeholder="Dark Souls, steampunk"
                />
              </label>

              <fieldset>
                <legend className={FIELD}>Races &amp; classes</legend>
                <label className="flex items-center gap-2 text-sm text-ink-200 mb-1">
                  <input
                    type="radio"
                    name="races_classes_mode"
                    checked={form.races_classes_mode === "standard_5e"}
                    onChange={() => updateField("races_classes_mode", "standard_5e")}
                    className="accent-ember-500"
                  />
                  Use the standard 5e set (fast, no LLM call)
                </label>
                <label className="flex items-center gap-2 text-sm text-ink-200">
                  <input
                    type="radio"
                    name="races_classes_mode"
                    checked={form.races_classes_mode === "generate"}
                    onChange={() => updateField("races_classes_mode", "generate")}
                    className="accent-ember-500"
                  />
                  Generate setting-specific ones for this world
                </label>
              </fieldset>

              <label>
                <span className={FIELD}>GM persona / narrator style</span>
                <input
                  className={INPUT}
                  value={form.narrator_style_description}
                  onChange={(e) => updateField("narrator_style_description", e.target.value)}
                />
              </label>

              <label>
                <span className={FIELD}>Player character name</span>
                <input
                  className={INPUT}
                  value={form.player_actor_name}
                  onChange={(e) => updateField("player_actor_name", e.target.value)}
                />
              </label>

              <label>
                <span className={FIELD}>Must-include elements (one per line)</span>
                <textarea
                  className={INPUT}
                  rows={3}
                  value={mustIncludeText}
                  onChange={(e) => setMustIncludeText(e.target.value)}
                  placeholder="A cursed relic beneath the town"
                />
              </label>

              <fieldset className="border border-ink-700 rounded-lg p-3">
                <legend className={FIELD}>Seeding options</legend>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <label>
                    <span className="text-xs text-ink-400">NPCs</span>
                    <input
                      type="number" min={0} max={10} className={INPUT}
                      value={form.seed_npc_count}
                      onChange={(e) => updateField("seed_npc_count", Number(e.target.value))}
                    />
                  </label>
                  <label>
                    <span className="text-xs text-ink-400">Hooks</span>
                    <input
                      type="number" min={0} max={10} className={INPUT}
                      value={form.seed_hook_count}
                      onChange={(e) => updateField("seed_hook_count", Number(e.target.value))}
                    />
                  </label>
                  <label>
                    <span className="text-xs text-ink-400">Rumors</span>
                    <input
                      type="number" min={0} max={10} className={INPUT}
                      value={form.seed_rumor_count}
                      onChange={(e) => updateField("seed_rumor_count", Number(e.target.value))}
                    />
                  </label>
                  <label>
                    <span className="text-xs text-ink-400">Starting items</span>
                    <input
                      type="number" min={0} max={10} className={INPUT}
                      value={form.seed_starting_inventory_count}
                      onChange={(e) => updateField("seed_starting_inventory_count", Number(e.target.value))}
                    />
                  </label>
                </div>
                <div className="flex flex-col gap-1.5">
                  {(
                    [
                      ["seed_npc_relationships", "NPCs reference each other (rivalries, debts, alliances)"],
                      ["seed_always_faction", "Always seed a background faction"],
                      ["seed_planted_reveal", "Seed a hidden GM-only twist for later"],
                      ["seed_calendar_from_pitch", "Set a starting-calendar flavor"],
                      ["seed_starting_inventory", "Give the player starting inventory"],
                      ["seed_session_zero", "Ask for session-zero content below"],
                    ] as [keyof SeedInput, string][]
                  ).map(([key, label]) => (
                    <label key={key} className="flex items-center gap-2 text-sm text-ink-200">
                      <input
                        type="checkbox"
                        checked={Boolean(form[key])}
                        onChange={(e) => updateField(key, e.target.checked as SeedInput[typeof key])}
                        className="accent-ember-500"
                      />
                      {label}
                    </label>
                  ))}
                  <label className="flex items-center gap-2 text-sm text-ink-200">
                    <span className="text-xs text-ink-400 shrink-0">Child locations</span>
                    <input
                      type="range" min={1} max={2}
                      value={form.seed_location_depth}
                      onChange={(e) => updateField("seed_location_depth", Number(e.target.value))}
                    />
                    <span className="text-xs text-ink-500">{form.seed_location_depth >= 2 ? "on" : "off"}</span>
                  </label>
                </div>
              </fieldset>

              {form.seed_session_zero && (
                <>
                  <label>
                    <span className={FIELD}>Safety tools (content lines/veils, table agreements)</span>
                    <textarea
                      className={INPUT}
                      rows={2}
                      value={form.safety_tools}
                      onChange={(e) => updateField("safety_tools", e.target.value)}
                      placeholder="Lines and veils apply. Check in if anything's too much."
                    />
                  </label>
                  <label>
                    <span className={FIELD}>Why does your character care?</span>
                    <textarea
                      className={INPUT}
                      rows={2}
                      value={form.personal_stakes}
                      onChange={(e) => updateField("personal_stakes", e.target.value)}
                      placeholder="Your sister went missing here three years ago."
                    />
                  </label>
                </>
              )}

              <Button onClick={handleGenerate} disabled={busy} icon={<Wand2 className="w-4 h-4" />}>
                {busy ? "Generating..." : "Generate"}
              </Button>
              {busy && (
                <p className="text-xs text-ink-500">
                  This runs on a local model and takes real time — narrative content alone
                  has taken up to ~3 minutes in testing.
                  {form.races_classes_mode === "generate" &&
                    " With custom races/classes, expect closer to 5 minutes: two full generation passes run back to back."}
                  {" "}Don't close this tab; a slow response isn't a stuck one.
                </p>
              )}
            </div>
          </Card>
        ) : (
          <Card variant="elevated">
            <h2 className="font-serif text-xl text-ink-100 mb-2 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-ember-400" /> Review &amp; generate
            </h2>
            <p className="text-sm text-ink-400 mb-3">
              Everything below will be created when you confirm. Edit the JSON directly if you want to change anything before committing.
            </p>
            <div className="flex flex-wrap gap-2 mb-3">
              {Object.keys(REROLL_OP_TYPES).map((category) => (
                <Button key={category} variant="secondary" onClick={() => handleReroll(category)} disabled={busy}>
                  Reroll {category}
                </Button>
              ))}
            </div>
            <textarea
              className={`${INPUT} font-mono`}
              rows={22}
              value={proposalDraft}
              onChange={(e) => setProposalDraft(e.target.value)}
            />
            <div className="flex gap-2 mt-4">
              <Button onClick={handleConfirm} disabled={busy}>
                {busy ? "Creating..." : "Confirm & Create Campaign"}
              </Button>
              <Button variant="secondary" onClick={handleBack} disabled={busy}>
                Back
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
