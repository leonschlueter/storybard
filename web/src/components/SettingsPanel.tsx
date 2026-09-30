import { useEffect, useState } from "react";
import { type CampaignSettings, getCampaignSettings, patchCampaignSettings } from "../lib/api";
import { Button } from "./Button";

// The real, reachable-from-the-UI "make everything configurable" surface — every field
// on CampaignSettings, not just curl-able via the API. Grouped to mirror the "All 20
// Features" plan's two lists (seeding enrichment / narration liveliness). Seeding fields
// are shown for reference/consistency (they took effect at seed time and mostly don't
// change anything to edit post-seed) — the narration fields are the ones that actually
// affect future turns live.

const BOOL_FIELDS: [keyof CampaignSettings, string, "seed" | "narration"][] = [
  ["seed_npc_relationships", "NPCs reference each other", "seed"],
  ["seed_calendar_from_pitch", "Starting calendar flavor", "seed"],
  ["seed_always_faction", "Always seed a faction", "seed"],
  ["seed_session_zero", "Session-zero content", "seed"],
  ["seed_starting_inventory", "Starting inventory", "seed"],
  ["seed_planted_reveal", "Planted reveal (hidden twist)", "seed"],
  ["narration_npc_offscreen", "NPCs act off-screen (world-tick)", "narration"],
  ["narration_twist_enabled", "Twist node", "narration"],
  ["narration_npc_voices", "Distinct NPC voices", "narration"],
  ["narration_consequence_ledger", "Narrator weaves in recent events", "narration"],
  ["mechanical_degrees_of_success", "Textured roll outcomes", "narration"],
  ["narration_thinking_gloss", "\"GM is thinking\" messages", "narration"],
  ["narration_oracle_enabled", "Oracle table for forced beats", "narration"],
  ["narration_npc_memory", "NPCs remember the player", "narration"],
];

const NUMBER_FIELDS: [keyof CampaignSettings, string, "seed" | "narration"][] = [
  ["seed_npc_count", "NPC count", "seed"],
  ["seed_hook_count", "Hook count", "seed"],
  ["seed_rumor_count", "Rumor count", "seed"],
  ["seed_location_depth", "Location depth (1 or 2)", "seed"],
  ["seed_starting_inventory_count", "Starting item count", "seed"],
  ["narration_npc_offscreen_interval_hours", "Off-screen check interval (hours)", "narration"],
  ["narration_twist_frequency", "Twist frequency (every N turns)", "narration"],
  ["narration_hard_stagnation_threshold", "Hard pacing floor (0 = off)", "narration"],
];

export function SettingsPanel({ campaignId, onClose }: { campaignId: string; onClose: () => void }) {
  const [settings, setSettings] = useState<CampaignSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCampaignSettings(campaignId)
      .then(setSettings)
      .catch((e) => setError(String(e)));
  }, [campaignId]);

  async function update<K extends keyof CampaignSettings>(key: K, value: CampaignSettings[K]) {
    if (!settings) return;
    setSettings({ ...settings, [key]: value });
    try {
      await patchCampaignSettings(campaignId, { [key]: value });
    } catch (e) {
      setError(String(e));
    }
  }

  function group(title: string, category: "seed" | "narration") {
    return (
      <div className="mb-5">
        <h3 className="text-xs uppercase tracking-wide text-ink-500 mb-2">{title}</h3>
        <div className="flex flex-col gap-2">
          {NUMBER_FIELDS.filter(([, , c]) => c === category).map(([key, label]) => (
            <label key={key} className="flex items-center justify-between gap-2 text-sm text-ink-200">
              {label}
              <input
                type="number"
                className="w-20 bg-ink-950 border border-ink-700 rounded-lg px-2 py-1 text-xs text-ink-100"
                value={settings ? (settings[key] as number) : 0}
                onChange={(e) => update(key, Number(e.target.value) as CampaignSettings[typeof key])}
              />
            </label>
          ))}
          {BOOL_FIELDS.filter(([, , c]) => c === category).map(([key, label]) => (
            <label key={key} className="flex items-center justify-between gap-2 text-sm text-ink-200 cursor-pointer">
              {label}
              <input
                type="checkbox"
                className="accent-ember-500"
                checked={settings ? Boolean(settings[key]) : false}
                onChange={(e) => update(key, e.target.checked as CampaignSettings[typeof key])}
              />
            </label>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="flex-1 bg-black/50" onClick={onClose} />
      <div className="w-full max-w-sm h-full bg-ink-900 border-l border-ink-700 overflow-y-auto p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-lg text-ink-100">Settings</h2>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>

        {error && <pre className="text-ember-300 text-xs whitespace-pre-wrap">{error}</pre>}
        {!settings && !error && <p className="text-ink-500 text-sm">Loading...</p>}

        {settings && (
          <>
            {group("Narration", "narration")}
            {group("Seeding (reference)", "seed")}
          </>
        )}
      </div>
    </div>
  );
}
