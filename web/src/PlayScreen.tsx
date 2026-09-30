import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  type ChainStepOut,
  type RollResolutionOut,
  abandonCurrentTurn,
  connectCampaignStream,
  getCampaignSettings,
  getCurrentTurn,
  getOpeningScene,
  getTurnHistory,
  resolveStep,
  submitTurn,
} from "./lib/api";
import { Menu, ScrollText, Settings as SettingsIcon, X } from "lucide-react";
import { Badge } from "./components/Badge";
import { Button } from "./components/Button";
import { ChatBubble } from "./components/ChatBubble";
import { Card } from "./components/Card";
import { CharacterRail } from "./components/CharacterRail";
import { SceneWorldRail } from "./components/SceneWorldRail";
import { SettingsPanel } from "./components/SettingsPanel";

// A persistent three-pane dashboard (character rail / chat / scene+world rail) — per the
// "Frontend Redesign" plan, core info (your character's state, who's around you, what the
// campaign's threads actually are) is always visible, not hidden behind clicks/tabs.
// Settings stays a modal deliberately: it's an occasional configuration action, not
// information you want on screen while playing.

interface TurnEntry {
  id: string;
  playerText: string;
  steps: ChainStepOut[];
  narration: string | null;
  status: "running" | "completed";
}

const NODE_LABELS: Record<string, string> = {
  intent_parse: "Intent",
  plausibility_check: "Plausibility",
  thread_tick: "Thread Tick",
  opportunity_spotting: "Opportunity",
  mechanical_check: "Mechanics",
  roll_resolution: "Roll",
  tone_assessment: "Tone",
  plan_synthesis: "Plan",
  twist: "Twist",
  world_update: "World",
  memory_regression: "Memory",
};

const SUCCESS_DEGREES = new Set(["critical_success", "clean_success", "narrow_success"]);

function rollBadgeText(roll: RollResolutionOut): string {
  const sign = roll.modifier >= 0 ? "+" : "";
  const degreeLabel = roll.degree.replace(/_/g, " ");
  return `🎲 ${roll.rolled}${sign}${roll.modifier}=${roll.total} vs DC${roll.dc} · ${degreeLabel}`;
}

// Feature #17: a cheap, friendly "GM is thinking" gloss shown while a step is active —
// deliberately a static map, not an LLM call, so it adds zero latency for something purely
// cosmetic.
const THINKING_GLOSS: Record<string, string> = {
  intent_parse: "Figuring out what you're trying to do...",
  plausibility_check: "Weighing what's actually possible...",
  thread_tick: "Checking if anything's been building...",
  opportunity_spotting: "Looking for something worth noticing...",
  mechanical_check: "Deciding if this needs a roll...",
  roll_resolution: "Rolling the dice...",
  tone_assessment: "Reading the mood of the scene...",
  plan_synthesis: "Planning the next beat...",
  twist: "Considering a complication...",
  narrator: "Writing what happens...",
  world_update: "Updating the world...",
  memory_regression: "Remembering what mattered...",
};

function summarizeStep(step: ChainStepOut): string {
  const out = step.raw_output;
  switch (step.node_type) {
    case "intent_parse":
      return [out.primitive, out.target].filter(Boolean).join(" → ") as string;
    case "plausibility_check":
      return String(out.feasibility ?? "");
    case "thread_tick": {
      const n = (out.tick_suggestions as unknown[] | undefined)?.length ?? 0;
      return n ? `${n} tick(s)` : "no change";
    }
    case "opportunity_spotting": {
      const n = (out.hook_ideas as unknown[] | undefined)?.length ?? 0;
      return n ? `${n} idea(s)` : "none";
    }
    case "mechanical_check":
      return out.roll_required ? `DC ${out.dc} ${out.skill ?? ""}`.trim() : "no roll";
    case "roll_resolution":
      return rollBadgeText(out as unknown as RollResolutionOut);
    case "tone_assessment":
      return String(out.tension ?? "");
    case "plan_synthesis":
      return "beat planned";
    case "twist":
      return "complication";
    case "world_update": {
      const n = (out.ops as unknown[] | undefined)?.length ?? 0;
      return n ? `${n} change(s)` : "no change";
    }
    case "memory_regression": {
      const n = (out.memories as unknown[] | undefined)?.length ?? 0;
      return n ? `${n} memory(ies)` : "none";
    }
    default:
      return "";
  }
}

function upsertStepInTurns(turns: TurnEntry[], step: ChainStepOut): TurnEntry[] {
  if (turns.length === 0) return turns;
  const last = turns[turns.length - 1];
  const idx = last.steps.findIndex((s) => s.id === step.id);
  const steps = idx === -1 ? [...last.steps, step] : last.steps.map((s) => (s.id === step.id ? step : s));
  return [...turns.slice(0, -1), { ...last, steps }];
}

function completeLastTurn(turns: TurnEntry[], narration: string): TurnEntry[] {
  if (turns.length === 0) return turns;
  const last = turns[turns.length - 1];
  return [...turns.slice(0, -1), { ...last, narration, status: "completed" as const }];
}

const NODE_ORDER = [
  "intent_parse", "plausibility_check", "thread_tick", "opportunity_spotting",
  "mechanical_check", "roll_resolution", "tone_assessment", "plan_synthesis", "twist",
  "narrator", "world_update", "memory_regression",
];

// HP/condition deltas from a completed turn's World Update ops (feature: richer step
// visualization) — read straight from applied_results, the same data summarizeStep's
// world_update case already reads, so a "−4 HP · +Shaken" line can sit under the
// narration without a second round-trip to the server.
function consequenceDeltas(turn: TurnEntry): string[] {
  const worldStep = turn.steps.find((s) => s.node_type === "world_update");
  if (!worldStep) return [];
  const output = (worldStep.final_output?.ops ? worldStep.final_output : worldStep.raw_output) as {
    ops?: { op: string; amount?: number; condition?: string; active?: boolean }[];
    applied_results?: { op: string; applied: boolean }[];
  };
  const ops = output.ops ?? [];
  const appliedFlags = output.applied_results ?? [];
  const deltas: string[] = [];
  ops.forEach((op, i) => {
    if (appliedFlags[i] && !appliedFlags[i].applied) return;
    if (op.op === "apply_damage" && typeof op.amount === "number") {
      deltas.push(op.amount >= 0 ? `−${op.amount} HP` : `+${-op.amount} HP`);
    } else if (op.op === "apply_condition" && op.condition) {
      deltas.push(op.active ? `+${op.condition}` : `−${op.condition}`);
    }
  });
  return deltas;
}

function thinkingGloss(turn: TurnEntry): string {
  const lastType = turn.steps[turn.steps.length - 1]?.node_type;
  const idx = lastType ? NODE_ORDER.indexOf(lastType) : -1;
  const nextType = NODE_ORDER[idx + 1];
  return (nextType && THINKING_GLOSS[nextType]) || "The GM is thinking...";
}

export default function PlayScreen() {
  const { campaignId, actorId } = useParams<{ campaignId: string; actorId: string }>();

  const [turns, setTurns] = useState<TurnEntry[]>([]);
  const [openingNarration, setOpeningNarration] = useState<string | null>(null);
  const [actionText, setActionText] = useState("");
  const [autoApprove, setAutoApprove] = useState(true);
  const [editingStepId, setEditingStepId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [mobileCharOpen, setMobileCharOpen] = useState(false);
  const [mobileWorldOpen, setMobileWorldOpen] = useState(false);
  const [sheetRefreshKey, setSheetRefreshKey] = useState(0);
  const [thinkingGlossEnabled, setThinkingGlossEnabled] = useState(true);
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

  function toggleStepExpanded(stepId: string) {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(stepId)) next.delete(stepId);
      else next.add(stepId);
      return next;
    });
  }

  const disconnectRef = useRef<(() => void) | null>(null);
  const autoApproveRef = useRef(autoApprove);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    autoApproveRef.current = autoApprove;
  }, [autoApprove]);

  useEffect(() => {
    if (!campaignId || !actorId) return;
    getOpeningScene(campaignId, actorId)
      .then((res) => setOpeningNarration(res.narration))
      .catch((e) => setError(String(e)));
  }, [campaignId, actorId]);

  // The transcript was only ever populated live via the WebSocket stream — nothing
  // fetched past turns on load, so a refresh silently lost the whole conversation even
  // though it was sitting in the database the whole time. Same used to be true of each
  // turn's per-node trail (the "what did the GM actually decide at each step" detail
  // behind the badges below) — getTurnHistory now returns it, synthesized here into the
  // same ChainStepOut shape the live WebSocket path uses so one rendering path (badges +
  // expand-to-inspect) serves both live and historical turns.
  useEffect(() => {
    if (!campaignId || !actorId) return;
    getTurnHistory(campaignId, actorId)
      .then((res) => {
        setTurns(
          res.turns.map((t) => ({
            id: t.id,
            playerText: t.player_text,
            steps: t.steps.map((s, i) => ({
              id: `${t.id}-${s.node_type}`,
              turn_run_id: t.id,
              node_type: s.node_type,
              sequence: i,
              raw_output: s.output,
              final_output: s.output,
              status: "approved",
            })),
            narration: t.narration,
            status: "completed" as const,
          }))
        );
      })
      .then(() => getCurrentTurn(campaignId, actorId))
      .then((current) => {
        // A turn stuck on a pending review step (e.g. the tab was closed or refreshed
        // before approving/editing/retrying it) used to just vanish from the UI on
        // reload — the ChainStep was still sitting there in the database, unresolved,
        // silently blocking every future turn for this actor. Recover it into the same
        // "running" shape a live turn has, so the existing pending-review card picks it
        // up exactly as if it had just paused.
        if (!current) return;
        setTurns((prev) => [
          ...prev,
          {
            id: current.turn_run_id,
            playerText: current.player_text,
            steps: current.steps,
            narration: null,
            status: "running" as const,
          },
        ]);
        // The live WebSocket path auto-approves a pending step when the toggle is on;
        // a recovered step arrived outside that path (it paused before this page load
        // existed), so it needs the same treatment explicitly or it just sits there
        // forever even with auto-approve on.
        const pending = current.steps.find((s) => s.status === "pending");
        if (pending && autoApproveRef.current) {
          resolveStep(pending.id, "approve").catch((e) => setError(String(e)));
        }
      })
      .catch((e) => setError(String(e)));
  }, [campaignId, actorId]);

  useEffect(() => {
    if (!campaignId) return;
    getCampaignSettings(campaignId)
      .then((s) => setThinkingGlossEnabled(s.narration_thinking_gloss))
      .catch(() => {
        /* non-critical — default (enabled) stands if this fails */
      });
  }, [campaignId]);

  useEffect(() => {
    if (!campaignId) return;
    disconnectRef.current = connectCampaignStream(campaignId, (event) => {
      if (event.status === "paused") {
        setTurns((prev) => upsertStepInTurns(prev, event.step));
        if (autoApproveRef.current) {
          resolveStep(event.step.id, "approve").catch((e) => setError(String(e)));
        }
      } else {
        setTurns((prev) => completeLastTurn(prev, event.narration));
        setSheetRefreshKey((k) => k + 1);
      }
    });
    return () => disconnectRef.current?.();
  }, [campaignId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function handleSendAction() {
    if (!campaignId || !actorId || !actionText.trim() || busy) return;
    const text = actionText;
    setActionText("");
    setBusy(true);
    setError(null);
    const optimisticId = crypto.randomUUID();
    setTurns((prev) => [...prev, { id: optimisticId, playerText: text, steps: [], narration: null, status: "running" }]);
    try {
      await submitTurn(campaignId, actorId, text);
    } catch (e) {
      // A failed submitTurn (e.g. 409 turn_in_progress) used to leave the optimistic
      // "running" entry stuck in the transcript forever with no steps and no way to
      // resolve it — the player's own message would just sit there unanswered.
      setTurns((prev) => prev.filter((t) => t.id !== optimisticId));
      setError(
        String(e).includes("409")
          ? "You have a turn still awaiting review — resolve or abandon it before sending another."
          : String(e)
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleResolve(step: ChainStepOut, action: "approve" | "edit" | "retry") {
    setBusy(true);
    setError(null);
    try {
      let editedOutput: Record<string, unknown> | undefined;
      if (action === "edit") {
        editedOutput = JSON.parse(editDraft);
      }
      await resolveStep(step.id, action, editedOutput);
      setEditingStepId(null);
    } catch (e) {
      if (String(e).includes("410")) {
        // The server already marked this turn "abandoned" (its LangGraph checkpoint was
        // gone — e.g. a server restart since it paused) — drop the now-stale entry
        // locally too so the next action isn't blocked by a turn that no longer exists.
        setTurns((prev) => prev.filter((t) => t.status !== "running"));
        setError("That turn's session expired (likely a server restart) and was abandoned. Please try again.");
      } else {
        setError(String(e));
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleAbandon() {
    if (!campaignId || !actorId) return;
    setBusy(true);
    setError(null);
    try {
      await abandonCurrentTurn(campaignId, actorId);
      setTurns((prev) => prev.filter((t) => t.status !== "running"));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!campaignId || !actorId) {
    return <p className="p-6 text-ember-300">Missing campaign or actor id in URL.</p>;
  }

  const lastTurn = turns[turns.length - 1];
  const pendingStep =
    !autoApprove && lastTurn?.status === "running"
      ? lastTurn.steps.find((s) => s.status === "pending")
      : undefined;

  return (
    <div className="flex h-screen">
      {/* Character rail — always visible on lg+; a full-screen drawer on narrow viewports */}
      <div
        className={`${mobileCharOpen ? "fixed inset-0 z-50 bg-ink-950" : "hidden"} lg:static lg:block lg:z-auto lg:bg-transparent lg:w-[280px] lg:shrink-0 border-r border-ink-800`}
      >
        <div className="lg:hidden flex justify-end p-2 border-b border-ink-800">
          <Button variant="ghost" onClick={() => setMobileCharOpen(false)} icon={<X className="w-4 h-4" />}>
            Close
          </Button>
        </div>
        <CharacterRail campaignId={campaignId} actorId={actorId} refreshKey={sheetRefreshKey} />
      </div>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="border-b border-ink-800 px-4 lg:px-6 py-3 flex items-center justify-between bg-ink-900/60 backdrop-blur">
          <div className="flex items-center gap-2">
            <Button variant="ghost" className="lg:hidden" onClick={() => setMobileCharOpen(true)} icon={<Menu className="w-4 h-4" />} />
            <h1 className="font-serif text-lg text-ink-100">Storybard</h1>
          </div>
          <div className="flex items-center gap-3">
            <label className="hidden sm:flex items-center gap-2 text-sm text-ink-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={autoApprove}
                onChange={(e) => setAutoApprove(e.target.checked)}
                className="accent-ember-500"
              />
              Auto-approve
            </label>
            <Button variant="ghost" onClick={() => setShowSettings(true)} icon={<SettingsIcon className="w-4 h-4" />}>
              <span className="hidden sm:inline">Settings</span>
            </Button>
            <Button variant="ghost" className="lg:hidden" onClick={() => setMobileWorldOpen(true)} icon={<ScrollText className="w-4 h-4" />} />
          </div>
        </header>

        {showSettings && <SettingsPanel campaignId={campaignId} onClose={() => setShowSettings(false)} />}

        {error && <pre className="text-ember-300 text-xs px-6 py-2 whitespace-pre-wrap">{error}</pre>}

        <main className="flex-1 overflow-y-auto px-4 lg:px-6 py-6 flex flex-col gap-6 max-w-3xl w-full mx-auto">
          {openingNarration && <ChatBubble from="narrator">{openingNarration}</ChatBubble>}

          {turns.map((turn) => (
            <div key={turn.id} className="flex flex-col gap-2">
              <ChatBubble from="player">{turn.playerText}</ChatBubble>

              {turn.steps.length > 0 && (
                <div className="flex flex-wrap gap-1.5 ml-9">
                  {turn.steps
                    .filter((s) => s.node_type !== "narrator" && NODE_LABELS[s.node_type])
                    .map((s, i, arr) => {
                      const isLast = i === arr.length - 1 && turn.status === "running";
                      const isOpen = expandedSteps.has(s.id);
                      if (s.node_type === "roll_resolution") {
                        const roll = s.raw_output as unknown as RollResolutionOut;
                        const tone = isLast ? "active" : SUCCESS_DEGREES.has(roll.degree) ? "success" : "danger";
                        return (
                          <button key={s.id} onClick={() => toggleStepExpanded(s.id)} className="cursor-pointer">
                            <Badge tone={tone}>{rollBadgeText(roll)}</Badge>
                          </button>
                        );
                      }
                      return (
                        <button key={s.id} onClick={() => toggleStepExpanded(s.id)} className="cursor-pointer">
                          <Badge tone={isOpen ? "active" : isLast ? "active" : "done"}>
                            {NODE_LABELS[s.node_type]}
                            {summarizeStep(s) && `: ${summarizeStep(s)}`}
                          </Badge>
                        </button>
                      );
                    })}
                </div>
              )}

              {/* Node output explorer — click any step badge above to see exactly what
                  that node decided, not just the one-line summary. Reads final_output
                  when a step has been resolved (possibly edited), raw_output otherwise
                  (still pending, or a historical row where both are the same value). */}
              {turn.steps
                .filter((s) => expandedSteps.has(s.id))
                .map((s) => (
                  <Card key={`detail-${s.id}`} className="ml-9">
                    <div className="text-xs text-ink-500 mb-1.5">
                      {NODE_LABELS[s.node_type] ?? s.node_type} — full output
                    </div>
                    <pre className="text-xs text-ink-400 whitespace-pre-wrap break-words">
                      {JSON.stringify(
                        Object.keys(s.final_output ?? {}).length > 0 ? s.final_output : s.raw_output,
                        null,
                        2
                      )}
                    </pre>
                  </Card>
                ))}

              {thinkingGlossEnabled && turn.status === "running" && turn.id === lastTurn.id && !pendingStep && (
                <div className="text-xs text-ink-500 italic ml-9">{thinkingGloss(turn)}</div>
              )}

              {pendingStep && turn.id === lastTurn.id && (
                <Card className="ml-9">
                  <div className="text-xs text-ink-400 mb-2">{NODE_LABELS[pendingStep.node_type] ?? pendingStep.node_type} — awaiting review</div>
                  {editingStepId === pendingStep.id ? (
                    <div className="flex flex-col gap-2">
                      <textarea
                        className="w-full bg-ink-950 border border-ink-700 rounded-lg p-2 text-xs font-mono text-ink-100"
                        rows={5}
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <Button variant="primary" onClick={() => handleResolve(pendingStep, "edit")} disabled={busy}>
                          Submit Edit
                        </Button>
                        <Button variant="ghost" onClick={() => setEditingStepId(null)} disabled={busy}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-2">
                      <pre className="text-xs text-ink-400 whitespace-pre-wrap">{JSON.stringify(pendingStep.raw_output, null, 2)}</pre>
                      <div className="flex gap-2">
                        <Button variant="primary" onClick={() => handleResolve(pendingStep, "approve")} disabled={busy}>
                          Approve
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => {
                            setEditingStepId(pendingStep.id);
                            setEditDraft(JSON.stringify(pendingStep.raw_output, null, 2));
                          }}
                          disabled={busy}
                        >
                          Edit
                        </Button>
                        <Button variant="secondary" onClick={() => handleResolve(pendingStep, "retry")} disabled={busy}>
                          Retry
                        </Button>
                        <Button variant="ghost" onClick={handleAbandon} disabled={busy}>
                          Abandon turn
                        </Button>
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {turn.narration && <ChatBubble from="narrator">{turn.narration}</ChatBubble>}
              {turn.narration && consequenceDeltas(turn).length > 0 && (
                <div className="flex gap-1.5 ml-9">
                  {consequenceDeltas(turn).map((d, i) => (
                    <Badge key={i} tone={d.startsWith("−") ? "danger" : "success"}>
                      {d}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </main>

        <footer className="border-t border-ink-800 px-4 lg:px-6 py-4 bg-ink-900/60 backdrop-blur">
          <div className="max-w-3xl w-full mx-auto flex gap-2">
            <textarea
              className="flex-1 bg-ink-900 border border-ink-700 rounded-xl px-3 py-2 text-sm text-ink-100 resize-none focus:outline-none focus:border-ember-500"
              rows={2}
              placeholder="What do you do?"
              value={actionText}
              onChange={(e) => setActionText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSendAction();
                }
              }}
            />
            <Button onClick={handleSendAction} disabled={busy || !actionText.trim()}>
              Send
            </Button>
          </div>
        </footer>
      </div>

      {/* Scene & World rail — always visible on lg+; a full-screen drawer on narrow viewports */}
      <div
        className={`${mobileWorldOpen ? "fixed inset-0 z-50 bg-ink-950" : "hidden"} lg:static lg:block lg:z-auto lg:bg-transparent lg:w-[320px] lg:shrink-0 border-l border-ink-800`}
      >
        <div className="lg:hidden flex justify-end p-2 border-b border-ink-800">
          <Button variant="ghost" onClick={() => setMobileWorldOpen(false)} icon={<X className="w-4 h-4" />}>
            Close
          </Button>
        </div>
        <SceneWorldRail campaignId={campaignId} actorId={actorId} refreshKey={sheetRefreshKey} />
      </div>
    </div>
  );
}
