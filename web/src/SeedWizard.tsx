import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { type SeedInput, type SeedProposal, commitSeed, pitchSeed, proposeSeed } from "./lib/api";
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
        <h1 className="font-serif text-3xl text-ink-100 mb-6">New Campaign</h1>

        {error && <pre className="text-ember-300 text-xs mb-4 whitespace-pre-wrap">{error}</pre>}

        {step === "setup" ? (
          <Card>
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
                <Button onClick={handlePitch} disabled={busy || !pitch.trim()}>
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

              <Button onClick={handleGenerate} disabled={busy}>
                {busy ? "Generating..." : "Generate"}
              </Button>
            </div>
          </Card>
        ) : (
          <Card>
            <h2 className="font-serif text-xl text-ink-100 mb-2">Review &amp; generate</h2>
            <p className="text-sm text-ink-400 mb-3">
              Everything below will be created when you confirm. Edit the JSON directly if you want to change anything before committing.
            </p>
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
