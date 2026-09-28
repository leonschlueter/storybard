import { type ReactNode, useEffect, useState } from "react";
import { type WorldState, getWorldState } from "../lib/api";
import { Card } from "./Card";
import { Button } from "./Button";

// Read-only "codex" — spec.md's roadmap calls this "codex search," slated for later; this
// is a first, simple version: browse what the campaign actually contains.

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mb-5">
      <h3 className="text-xs uppercase tracking-wide text-ink-500 mb-2">{title}</h3>
      <div className="flex flex-col gap-1.5">{children}</div>
    </div>
  );
}

export function ExplorePanel({ campaignId, onClose }: { campaignId: string; onClose: () => void }) {
  const [state, setState] = useState<WorldState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getWorldState(campaignId)
      .then(setState)
      .catch((e) => setError(String(e)));
  }, [campaignId]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="flex-1 bg-black/50" onClick={onClose} />
      <div className="w-full max-w-sm h-full bg-ink-900 border-l border-ink-700 overflow-y-auto p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-serif text-lg text-ink-100">Explore</h2>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>

        {error && <pre className="text-ember-300 text-xs whitespace-pre-wrap">{error}</pre>}
        {!state && !error && <p className="text-ink-500 text-sm">Loading...</p>}

        {state && (
          <>
            <Section title={`Actors (${state.actors.length})`}>
              {state.actors.map((a) => (
                <Card key={a.id} className="py-2 px-3">
                  <span className="text-sm text-ink-100">{a.name}</span>{" "}
                  <span className="text-xs text-ink-500">({a.kind})</span>
                </Card>
              ))}
            </Section>

            <Section title={`Locations (${state.locations.length})`}>
              {state.locations.map((l) => (
                <Card key={l.id} className="py-2 px-3">
                  <div className="text-sm text-ink-100">{l.name}{l.scale && <span className="text-xs text-ink-500"> · {l.scale}</span>}</div>
                  {l.description && <div className="text-xs text-ink-400 mt-1">{l.description}</div>}
                </Card>
              ))}
            </Section>

            <Section title={`Threads (${state.threads.length})`}>
              {state.threads.map((t) => (
                <Card key={t.id} className="py-2 px-3">
                  <div className="text-sm text-ink-100">{t.title}</div>
                  <div className="text-xs text-ink-500">{t.tier}</div>
                </Card>
              ))}
            </Section>

            <Section title={`Items (${state.items.length})`}>
              {state.items.map((i) => (
                <Card key={i.id} className="py-2 px-3">
                  <span className="text-sm text-ink-100">{i.name}</span>{" "}
                  <span className="text-xs text-ink-500">({i.item_type})</span>
                </Card>
              ))}
            </Section>

            <Section title={`Spells (${state.spells.length})`}>
              {state.spells.map((s) => (
                <Card key={s.id} className="py-2 px-3">
                  <span className="text-sm text-ink-100">{s.name}</span>{" "}
                  <span className="text-xs text-ink-500">(lvl {s.level}, {s.school})</span>
                </Card>
              ))}
            </Section>

            {state.factions.length > 0 && (
              <Section title={`Factions (${state.factions.length})`}>
                {state.factions.map((f) => (
                  <Card key={f.id} className="py-2 px-3">
                    <span className="text-sm text-ink-100">{f.name}</span>
                  </Card>
                ))}
              </Section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
