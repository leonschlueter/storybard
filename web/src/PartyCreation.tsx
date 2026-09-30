import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  type AncestryOption,
  type CharacterOptions,
  type ClassOption,
  finalizeCharacter,
  getCharacterOptions,
} from "./lib/api";
import { Dices, Shield, Sparkles, Users } from "lucide-react";
import { Button } from "./components/Button";
import { Card } from "./components/Card";

// spec.md Step 7. Ancestry/class picking + roll-for-stats or point-buy. Dice rolling
// happens client-side (no adversarial multiplayer concern in a solo local game); point-buy's
// cost curve is duplicated here only for live UX feedback — the server call is the actual
// guardrail (see api/party.py::_finalize_character).

const POINT_BUY_POOL = 27;
const POINT_BUY_COST: Record<number, number> = { 8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9 };

function abilityMod(score: number): number {
  return Math.floor((score - 10) / 2);
}

function rollOne4d6DropLowest(): number {
  const rolls = Array.from({ length: 4 }, () => 1 + Math.floor(Math.random() * 6));
  rolls.sort((a, b) => a - b);
  return rolls[1] + rolls[2] + rolls[3];
}

export default function PartyCreation() {
  const { campaignId, actorId } = useParams<{ campaignId: string; actorId: string }>();
  const navigate = useNavigate();

  const [options, setOptions] = useState<CharacterOptions | null>(null);
  const [ancestryKey, setAncestryKey] = useState<string>("");
  const [classKey, setClassKey] = useState<string>("");
  const [method, setMethod] = useState<"roll" | "point_buy">("roll");
  const [scores, setScores] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!campaignId) return;
    getCharacterOptions(campaignId)
      .then((opts) => {
        setOptions(opts);
        setAncestryKey(opts.ancestry_defs[0]?.key ?? "");
        setClassKey(opts.class_defs[0]?.key ?? "");
        const initial: Record<string, number> = {};
        for (const attr of opts.attribute_definitions) initial[attr.key] = 10;
        setScores(initial);
      })
      .catch((e) => setError(String(e)));
  }, [campaignId]);

  function handleRoll() {
    if (!options) return;
    const rolled = options.attribute_definitions.map(() => rollOne4d6DropLowest());
    const next: Record<string, number> = {};
    options.attribute_definitions.forEach((attr, i) => {
      next[attr.key] = rolled[i];
    });
    setScores(next);
  }

  function updateScore(key: string, value: number) {
    setScores((prev) => ({ ...prev, [key]: value }));
  }

  const pointBuySpent = Object.values(scores).reduce((sum, s) => sum + (POINT_BUY_COST[s] ?? 0), 0);

  const selectedClass: ClassOption | undefined = options?.class_defs.find((c) => c.key === classKey);
  const selectedAncestry: AncestryOption | undefined = options?.ancestry_defs.find((a) => a.key === ancestryKey);
  const conScore = scores["con"] ?? 10;
  const dexScore = scores["dex"] ?? 10;
  const previewMaxHp = selectedClass ? Math.max(1, selectedClass.hit_die + abilityMod(conScore)) : null;
  const previewAc = 10 + abilityMod(dexScore);

  async function handleConfirm() {
    if (!campaignId || !actorId) return;
    setBusy(true);
    setError(null);
    try {
      await finalizeCharacter(campaignId, actorId, {
        ancestry_key: ancestryKey,
        class_key: classKey,
        method,
        ability_scores: scores,
      });
      navigate(`/campaigns/${campaignId}/play/${actorId}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!campaignId || !actorId) {
    return <p className="p-6 text-ember-300">Missing campaign or actor id in URL.</p>;
  }

  if (error && !options) {
    return <pre className="p-6 text-ember-300 whitespace-pre-wrap">{error}</pre>;
  }

  if (!options) {
    return <p className="p-6 text-ink-400">Loading character options...</p>;
  }

  const overBudget = method === "point_buy" && pointBuySpent > POINT_BUY_POOL;
  // Guards a real failure observed live: a "generate" mode seed can under-produce (e.g.
  // ancestries with zero classes) — without this, Confirm silently submitted class_key=""
  // and the player hit a confusing 404 instead of a clear in-context explanation.
  const missingOptions = options.ancestry_defs.length === 0 || options.class_defs.length === 0;

  return (
    <div className="min-h-screen flex justify-center px-6 py-10">
      <div className="max-w-2xl w-full flex flex-col gap-4">
        <h1 className="font-serif text-3xl text-ink-100 mb-2 flex items-center gap-2.5">
          <Users className="w-6 h-6 text-ember-400" /> Create Your Character
        </h1>

        {error && <pre className="text-ember-300 text-xs whitespace-pre-wrap">{error}</pre>}

        <Card variant="elevated">
          <h2 className="font-serif text-lg text-ink-100 mb-3">Ancestry</h2>
          <div className="flex flex-col gap-1.5">
            {options.ancestry_defs.map((a) => (
              <label key={a.key} className="flex items-start gap-2 text-sm text-ink-200">
                <input
                  type="radio"
                  name="ancestry"
                  checked={ancestryKey === a.key}
                  onChange={() => setAncestryKey(a.key)}
                  className="accent-ember-500 mt-0.5"
                />
                <span>
                  <span className="text-ink-100 font-medium">{a.name}</span> — {a.description} (speed {a.speed})
                </span>
              </label>
            ))}
          </div>
        </Card>

        <Card variant="elevated">
          <h2 className="font-serif text-lg text-ink-100 mb-3">Class</h2>
          <div className="flex flex-col gap-1.5">
            {options.class_defs.map((c) => (
              <label key={c.key} className="flex items-start gap-2 text-sm text-ink-200">
                <input
                  type="radio"
                  name="class"
                  checked={classKey === c.key}
                  onChange={() => setClassKey(c.key)}
                  className="accent-ember-500 mt-0.5"
                />
                <span>
                  <span className="text-ink-100 font-medium">{c.name}</span> — {c.description} (hit die d{c.hit_die})
                </span>
              </label>
            ))}
          </div>
        </Card>

        <Card variant="elevated">
          <h2 className="font-serif text-lg text-ink-100 mb-3">Ability scores</h2>
          <div className="flex flex-col gap-2 mb-3">
            <label className="flex items-center gap-2 text-sm text-ink-200">
              <input type="radio" name="method" checked={method === "roll"} onChange={() => setMethod("roll")} className="accent-ember-500" />
              Roll (4d6, drop lowest)
            </label>
            <label className="flex items-center gap-2 text-sm text-ink-200">
              <input
                type="radio"
                name="method"
                checked={method === "point_buy"}
                onChange={() => setMethod("point_buy")}
                className="accent-ember-500"
              />
              Point buy ({POINT_BUY_POOL} points, {pointBuySpent} spent
              {overBudget ? " — over budget!" : ""})
            </label>
          </div>

          {method === "roll" && (
            <Button variant="secondary" onClick={handleRoll} className="mb-3" icon={<Dices className="w-4 h-4" />}>
              Roll
            </Button>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {options.attribute_definitions.map((attr) => (
              <div key={attr.key} className="flex items-center justify-between bg-ink-950 border border-ink-700 rounded-lg px-3 py-2">
                <span className="text-sm text-ink-300">{attr.abbreviation}</span>
                <div className="flex items-center gap-2">
                  {method === "point_buy" ? (
                    <input
                      type="number"
                      min={8}
                      max={15}
                      value={scores[attr.key] ?? 10}
                      onChange={(e) => updateScore(attr.key, Number(e.target.value))}
                      className="w-14 bg-ink-900 border border-ink-700 rounded px-1 py-0.5 text-sm text-ink-100 text-center"
                    />
                  ) : (
                    <span className="text-sm text-ink-100 font-medium">{scores[attr.key] ?? "—"}</span>
                  )}
                  <span className="text-xs text-ink-500">
                    ({abilityMod(scores[attr.key] ?? 10) >= 0 ? "+" : ""}
                    {abilityMod(scores[attr.key] ?? 10)})
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card variant="elevated" className="text-sm text-ink-300 flex items-center gap-2">
          <Shield className="w-4 h-4 text-teal-400 shrink-0" />
          Max HP: <span className="text-ink-100">{previewMaxHp ?? "—"}</span> · Armor Class:{" "}
          <span className="text-ink-100">{previewAc}</span> · Speed:{" "}
          <span className="text-ink-100">{selectedAncestry?.speed ?? "—"}</span>
        </Card>

        {missingOptions && (
          <Card className="text-sm text-crimson-300 border-crimson-500/40">
            This campaign is missing {options.ancestry_defs.length === 0 ? "ancestries" : "classes"} —
            it looks like seeding didn't fully generate. Re-seed the campaign before creating a character.
          </Card>
        )}

        <Button
          onClick={handleConfirm}
          disabled={busy || overBudget || missingOptions}
          icon={<Sparkles className="w-4 h-4" />}
        >
          {busy ? "Creating..." : "Confirm Character"}
        </Button>
      </div>
    </div>
  );
}
