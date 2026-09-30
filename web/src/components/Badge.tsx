import type { HTMLAttributes } from "react";

type Tone = "neutral" | "active" | "done" | "warn" | "success" | "danger";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-ink-800 text-ink-400 border-ink-700",
  active: "bg-teal-500/15 text-teal-400 border-teal-500/40 animate-pulse",
  done: "bg-teal-500/10 text-teal-400 border-teal-500/30",
  warn: "bg-ember-500/15 text-ember-300 border-ember-500/40",
  // Roll-outcome semantics (feature: real mechanical consequences) — distinct from
  // "active"/"done" (process/step status) even though success reuses the same teal family.
  success: "bg-teal-500/15 text-teal-400 border-teal-500/40",
  danger: "bg-crimson-500/15 text-crimson-300 border-crimson-500/40",
};

export function Badge({
  tone = "neutral",
  className = "",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border animate-fade-in-up ${TONE_CLASSES[tone]} ${className}`}
      {...props}
    />
  );
}
