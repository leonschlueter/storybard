import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  type ChainStepOut,
  connectCampaignStream,
  getOpeningScene,
  resolveStep,
  submitTurn,
} from "./lib/api";
import { Badge } from "./components/Badge";
import { Button } from "./components/Button";
import { ChatBubble } from "./components/ChatBubble";
import { Card } from "./components/Card";
import { ExplorePanel } from "./components/ExplorePanel";

// Phase "Playable Chat UI": a running transcript (not a replace-each-turn view), with
// steps auto-approved by default so the ~10-step chain doesn't block on a click per step —
// the chain's reasoning still renders as a compact progress strip, just not click-gated.
// Flipping auto-approve off restores the original Approve/Edit/Retry review flow inline.

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
  tone_assessment: "Tone",
  plan_synthesis: "Plan",
  world_update: "World",
  memory_regression: "Memory",
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
    case "tone_assessment":
      return String(out.tension ?? "");
    case "plan_synthesis":
      return "beat planned";
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
  const [showExplore, setShowExplore] = useState(false);

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
    setTurns((prev) => [...prev, { id: crypto.randomUUID(), playerText: text, steps: [], narration: null, status: "running" }]);
    try {
      await submitTurn(campaignId, actorId, text);
    } catch (e) {
      setError(String(e));
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
    <div className="flex flex-col h-screen">
      <header className="border-b border-ink-800 px-6 py-3 flex items-center justify-between bg-ink-900/60 backdrop-blur">
        <h1 className="font-serif text-lg text-ink-100">Storybard</h1>
        <div className="flex items-center gap-4">
          <Button variant="secondary" onClick={() => setShowExplore(true)}>
            Explore
          </Button>
          <label className="flex items-center gap-2 text-sm text-ink-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={autoApprove}
              onChange={(e) => setAutoApprove(e.target.checked)}
              className="accent-ember-500"
            />
            Auto-approve
          </label>
        </div>
      </header>

      {showExplore && <ExplorePanel campaignId={campaignId} onClose={() => setShowExplore(false)} />}

      {error && <pre className="text-ember-300 text-xs px-6 py-2 whitespace-pre-wrap">{error}</pre>}

      <main className="flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-6 max-w-3xl w-full mx-auto">
        {openingNarration && <ChatBubble from="narrator">{openingNarration}</ChatBubble>}

        {turns.map((turn) => (
          <div key={turn.id} className="flex flex-col gap-2">
            <ChatBubble from="player">{turn.playerText}</ChatBubble>

            {turn.steps.length > 0 && (
              <div className="flex flex-wrap gap-1.5 ml-1">
                {turn.steps
                  .filter((s) => s.node_type !== "narrator" && NODE_LABELS[s.node_type])
                  .map((s, i, arr) => (
                    <Badge key={s.id} tone={i === arr.length - 1 && turn.status === "running" ? "active" : "done"}>
                      {NODE_LABELS[s.node_type]}
                      {summarizeStep(s) && `: ${summarizeStep(s)}`}
                    </Badge>
                  ))}
              </div>
            )}

            {pendingStep && turn.id === lastTurn.id && (
              <Card className="ml-1">
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
                    </div>
                  </div>
                )}
              </Card>
            )}

            {turn.narration && <ChatBubble from="narrator">{turn.narration}</ChatBubble>}
          </div>
        ))}
        <div ref={bottomRef} />
      </main>

      <footer className="border-t border-ink-800 px-6 py-4 bg-ink-900/60 backdrop-blur">
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
  );
}
