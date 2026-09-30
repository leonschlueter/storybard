import { useEffect, useState } from "react";
import {
  type SceneState,
  type WorldState,
  getScene,
  getWorldState,
  resolveHook,
} from "../lib/api";
import {
  BookOpen,
  ChevronDown,
  Flag,
  MapPin,
  MessageCircleQuestion,
  Sparkles,
  Users,
  Wand2,
} from "lucide-react";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";

// Replaces the old ExplorePanel modal — always-visible per the "Frontend Redesign" plan
// ("no tab-switching to see core info"), and restructured around the Thread/Beat/Scene
// model instead of a flat campaign-wide dump: "Here now" (this location, who's present,
// what's due) is the primary content; the browsable World catalog lives below it.
//
// Audit finding: build_known_actors already returns bio/personality/speech_style/present
// for every NPC in the campaign (fed to the chain since the "chain audit" pass), but none
// of it ever reached this component — world.actors was fetched and simply never rendered.
// ActorRow below is the fix: every actor-shaped list (Here now, Cast) renders through it.

type ActorLike = {
  id: string;
  name: string;
  kind: string;
  bio?: string | null;
  current_goal?: string | null;
  personality?: string | null;
  speech_style?: string | null;
};

function ActorRow({ actor, presentBadge }: { actor: ActorLike; presentBadge?: "here" | "elsewhere" }) {
  const [open, setOpen] = useState(false);
  const hasDetail = Boolean(actor.bio || actor.current_goal || actor.personality || actor.speech_style);

  return (
    <div className="rounded-lg border border-ink-800 bg-ink-900/40 overflow-hidden">
      <button
        onClick={() => hasDetail && setOpen((v) => !v)}
        className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-left ${hasDetail ? "cursor-pointer hover:bg-ink-900/70" : "cursor-default"}`}
      >
        <span className="text-sm text-ink-100 min-w-0 truncate">
          {actor.name} <span className="text-xs text-ink-500">({actor.kind})</span>
        </span>
        <span className="flex items-center gap-1.5 shrink-0">
          {presentBadge === "here" && <Badge tone="success">here</Badge>}
          {presentBadge === "elsewhere" && <Badge tone="neutral">elsewhere</Badge>}
          {hasDetail && (
            <ChevronDown className={`w-3.5 h-3.5 text-ink-500 transition-transform ${open ? "rotate-180" : ""}`} />
          )}
        </span>
      </button>
      {open && (
        <div className="px-3 pb-2.5 flex flex-col gap-1.5 text-xs text-ink-400 border-t border-ink-800 pt-2">
          {actor.bio && <p className="leading-relaxed">{actor.bio}</p>}
          {actor.current_goal && (
            <p>
              <span className="text-ink-500">Wants: </span>
              {actor.current_goal}
            </p>
          )}
          {actor.speech_style && (
            <p>
              <span className="text-ink-500">Voice: </span>
              {actor.speech_style}
            </p>
          )}
          {actor.personality && (
            <p>
              <span className="text-ink-500">Personality: </span>
              {actor.personality}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h3 className="text-xs uppercase tracking-wide text-ink-500 mb-2 px-1 flex items-center gap-1.5">
        {icon} {title}
      </h3>
      <div className="flex flex-col gap-1.5">{children}</div>
    </div>
  );
}

export function SceneWorldRail({
  campaignId,
  actorId,
  refreshKey,
}: {
  campaignId: string;
  actorId: string;
  refreshKey: number;
}) {
  const [scene, setScene] = useState<SceneState | null>(null);
  const [world, setWorld] = useState<WorldState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showGmNotes, setShowGmNotes] = useState(false);

  useEffect(() => {
    Promise.all([getScene(campaignId, actorId), getWorldState(campaignId)])
      .then(([s, w]) => {
        setScene(s);
        setWorld(w);
      })
      .catch((e) => setError(String(e)));
  }, [campaignId, actorId, refreshKey]);

  // Previously nothing could move a touches_entity_id-bearing hook out of
  // status="proposed" — it just sat there permanently. Optimistic local update (no
  // refetch needed) once resolved.
  function handleResolveHook(hookId: string, action: "accept" | "reject") {
    resolveHook(campaignId, hookId, action)
      .then(({ status }) => {
        setWorld((prev) =>
          prev
            ? { ...prev, hooks: prev.hooks.map((h) => (h.id === hookId ? { ...h, status } : h)) }
            : prev
        );
      })
      .catch((e) => setError(String(e)));
  }

  return (
    <aside className="h-full overflow-y-auto p-4">
      {error && <pre className="text-crimson-300 text-xs whitespace-pre-wrap">{error}</pre>}
      {!scene && !world && !error && <p className="text-ink-500 text-sm px-1">Loading...</p>}

      {scene && (
        <div className="mb-6">
          <Card variant="elevated">
            <div className="flex items-center gap-2 text-sm text-ink-100 mb-2">
              <MapPin className="w-4 h-4 text-ember-400 shrink-0" />
              <span className="font-serif">{scene.location_name ?? "Nowhere in particular"}</span>
            </div>

            <div className="flex items-center gap-1.5 text-xs text-ink-400 mb-1.5">
              <Users className="w-3.5 h-3.5" /> Here now
            </div>
            {scene.actors_present.length > 0 ? (
              <div className="flex flex-col gap-1.5">
                {scene.actors_present.map((a) => {
                  // world.actors has the full catalog (bio/personality/speech_style);
                  // scene.actors_present only has presence + current_goal — merge by id
                  // so "Here now" gets the same rich detail as the Cast section below.
                  const full = world?.actors.find((wa) => wa.id === a.id);
                  return <ActorRow key={a.id} actor={full ?? a} />;
                })}
              </div>
            ) : (
              <p className="text-xs text-ink-600">No one else is here.</p>
            )}

            {scene.due_beats.length > 0 && (
              <button
                onClick={() => setShowGmNotes((v) => !v)}
                className="mt-3 flex items-center gap-1.5 text-xs text-ink-500 hover:text-ink-300 transition-colors cursor-pointer"
              >
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showGmNotes ? "rotate-180" : ""}`} />
                GM notes (spoilers) — {scene.due_beats.length} planned
              </button>
            )}
            {showGmNotes && (
              <div className="flex flex-col gap-1.5 mt-2">
                {scene.due_beats.map((b) => (
                  <div key={b.beat_id} className="text-xs text-ink-400 bg-ink-950/60 border border-ink-800 rounded-lg p-2">
                    <span className="text-ink-500">({b.thread_title})</span> {b.description}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {world && (
        <>
          <Section title={`Cast (${world.actors.length})`} icon={<Users className="w-3.5 h-3.5" />}>
            {world.actors.map((a) => (
              <ActorRow key={a.id} actor={a} presentBadge={a.present ? "here" : "elsewhere"} />
            ))}
            {world.actors.length === 0 && <p className="text-xs text-ink-600 px-1">No one's been introduced yet.</p>}
          </Section>

          <Section title={`Threads (${world.threads.length})`} icon={<BookOpen className="w-3.5 h-3.5" />}>
            {world.threads.map((t) => (
              <Card key={t.id} className="py-2 px-3">
                <div className="text-sm text-ink-100">{t.title}</div>
                <Badge tone={t.tier === "major" ? "warn" : "neutral"} className="mt-1">
                  {t.tier}
                </Badge>
                {t.summary && <div className="text-xs text-ink-400 mt-1.5 leading-relaxed">{t.summary}</div>}
              </Card>
            ))}
          </Section>

          <Section title={`Hooks & rumors (${world.hooks.length})`} icon={<MessageCircleQuestion className="w-3.5 h-3.5" />}>
            {world.hooks.map((h) => (
              <Card key={h.id} className="py-2 px-3">
                <div className="text-sm text-ink-100">{h.proposed_text}</div>
                <div className="flex items-center gap-1.5 mt-1.5">
                  <Badge tone="neutral">{h.origin}</Badge>
                  <Badge
                    tone={h.status === "accepted" ? "success" : h.status === "rejected" ? "danger" : "neutral"}
                  >
                    {h.status}
                  </Badge>
                </div>
                {h.status === "proposed" && (
                  <div className="flex gap-1.5 mt-2">
                    <Button variant="secondary" onClick={() => handleResolveHook(h.id, "accept")}>
                      Accept
                    </Button>
                    <Button variant="ghost" onClick={() => handleResolveHook(h.id, "reject")}>
                      Reject
                    </Button>
                  </div>
                )}
              </Card>
            ))}
          </Section>

          <Section title={`Locations (${world.locations.length})`} icon={<MapPin className="w-3.5 h-3.5" />}>
            {world.locations.map((l) => (
              <Card key={l.id} className="py-2 px-3">
                <div className="text-sm text-ink-100">
                  {l.name}{l.scale && <span className="text-xs text-ink-500"> · {l.scale}</span>}
                </div>
                {l.description && <div className="text-xs text-ink-400 mt-1">{l.description}</div>}
              </Card>
            ))}
          </Section>

          <Section title={`Items (${world.items.length})`} icon={<Sparkles className="w-3.5 h-3.5" />}>
            {world.items.map((i) => (
              <Card key={i.id} className="py-2 px-3">
                <span className="text-sm text-ink-100">{i.name}</span>{" "}
                <span className="text-xs text-ink-500">({i.item_type})</span>
                {i.description && <div className="text-xs text-ink-400 mt-1 leading-relaxed">{i.description}</div>}
              </Card>
            ))}
          </Section>

          <Section title={`Spells (${world.spells.length})`} icon={<Wand2 className="w-3.5 h-3.5" />}>
            {world.spells.map((s) => (
              <Card key={s.id} className="py-2 px-3">
                <span className="text-sm text-ink-100">{s.name}</span>{" "}
                <span className="text-xs text-ink-500">(lvl {s.level}, {s.school})</span>
                {s.description && <div className="text-xs text-ink-400 mt-1 leading-relaxed">{s.description}</div>}
                {s.effect && <div className="text-xs text-ink-500 mt-1">{s.effect}</div>}
              </Card>
            ))}
          </Section>

          {world.factions.length > 0 && (
            <Section title={`Factions (${world.factions.length})`} icon={<Flag className="w-3.5 h-3.5" />}>
              {world.factions.map((f) => (
                <Card key={f.id} className="py-2 px-3">
                  <span className="text-sm text-ink-100">{f.name}</span>
                  {f.description && <div className="text-xs text-ink-400 mt-1 leading-relaxed">{f.description}</div>}
                </Card>
              ))}
            </Section>
          )}
        </>
      )}
    </aside>
  );
}
