import { useEffect, useState } from "react";
import { type CharacterSheetState, getCharacterSheet } from "../lib/api";
import { Backpack, Footprints, Shield, Sparkles } from "lucide-react";
import { Badge } from "./Badge";
import { Card } from "./Card";

// Always-visible character panel — absorbs what the old CharacterHUD (compact bar) and
// CharacterSheetPanel (click-to-open modal) did, merged into one persistent rail. Per the
// "Frontend Redesign" plan: core info (your own character's state) shouldn't be hidden
// behind a click during play.

const ABILITY_LABELS: Record<string, string> = {
  str: "STR", dex: "DEX", con: "CON", int: "INT", wis: "WIS", cha: "CHA",
};

function abilityMod(score: number): number {
  return Math.floor((score - 10) / 2);
}

export function CharacterRail({
  campaignId,
  actorId,
  refreshKey,
}: {
  campaignId: string;
  actorId: string;
  refreshKey: number;
}) {
  const [sheet, setSheet] = useState<CharacterSheetState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCharacterSheet(campaignId, actorId)
      .then(setSheet)
      .catch((e) => setError(String(e)));
  }, [campaignId, actorId, refreshKey]);

  const hpRatio = sheet && sheet.max_hp > 0 ? sheet.current_hp / sheet.max_hp : 0;
  const hpColor = hpRatio > 0.5 ? "bg-teal-500" : hpRatio > 0.25 ? "bg-ember-500" : "bg-crimson-500";

  return (
    <aside className="h-full overflow-y-auto p-4 flex flex-col gap-4">
      {error && <pre className="text-crimson-300 text-xs whitespace-pre-wrap">{error}</pre>}
      {!sheet && !error && <p className="text-ink-500 text-sm px-1">Loading character...</p>}

      {sheet && (
        <>
          <Card variant="elevated">
            <div className="flex items-center gap-2 text-sm text-ink-100 mb-3">
              <Sparkles className="w-4 h-4 text-ember-400 shrink-0" />
              <span className="font-serif">
                {sheet.ancestry ?? "—"} {sheet.character_class ?? ""}
              </span>
              <span className="text-ink-500 text-xs ml-auto">Lvl {sheet.level}</span>
            </div>

            <div className="flex items-center justify-between text-xs text-ink-400 mb-1">
              <span>Hit Points</span>
              <span className="text-ink-200 font-medium">
                {sheet.current_hp} / {sheet.max_hp}
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-ink-800 overflow-hidden mb-3">
              <div
                className={`h-full rounded-full transition-all duration-300 ${hpColor}`}
                style={{ width: `${Math.max(0, Math.min(100, hpRatio * 100))}%` }}
              />
            </div>

            <div className="flex gap-4 text-xs text-ink-400">
              <span className="inline-flex items-center gap-1">
                <Shield className="w-3.5 h-3.5" /> AC {sheet.armor_class}
              </span>
              <span className="inline-flex items-center gap-1">
                <Footprints className="w-3.5 h-3.5" /> {sheet.speed} ft
              </span>
            </div>

            {sheet.conditions.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {sheet.conditions.map((c) => (
                  <Badge key={c} tone="danger">
                    {c}
                  </Badge>
                ))}
              </div>
            )}
          </Card>

          <div>
            <h3 className="text-xs uppercase tracking-wide text-ink-500 mb-2 px-1">Ability scores</h3>
            <div className="grid grid-cols-3 gap-1.5">
              {Object.entries(sheet.ability_scores).map(([key, score]) => (
                <div key={key} className="bg-ink-900 border border-ink-700 rounded-lg py-1.5 text-center">
                  <div className="text-[10px] text-ink-500">{ABILITY_LABELS[key] ?? key}</div>
                  <div className="text-sm text-ink-100 font-medium">{score}</div>
                  <div className="text-[10px] text-ink-500">
                    {abilityMod(score) >= 0 ? "+" : ""}{abilityMod(score)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-xs uppercase tracking-wide text-ink-500 mb-2 px-1 flex items-center gap-1.5">
              <Backpack className="w-3.5 h-3.5" /> Inventory ({sheet.inventory.length})
            </h3>
            <div className="flex flex-col gap-1.5">
              {sheet.inventory.map((item) => (
                <Card key={item.item_def_id} className="py-2 px-3 flex items-center justify-between">
                  <span className="text-sm text-ink-100">{item.name}</span>
                  <span className="text-xs text-ink-500">
                    {item.item_type}{item.quantity > 1 ? ` ×${item.quantity}` : ""}
                  </span>
                </Card>
              ))}
              {sheet.inventory.length === 0 && (
                <p className="text-xs text-ink-600 px-1">Nothing carried.</p>
              )}
            </div>
          </div>
        </>
      )}
    </aside>
  );
}
