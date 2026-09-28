import type { HTMLAttributes } from "react";

type Tone = "neutral" | "active" | "done" | "warn";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-ink-800 text-ink-400 border-ink-700",
  active: "bg-teal-500/15 text-teal-400 border-teal-500/40 animate-pulse",
  done: "bg-teal-500/10 text-teal-400 border-teal-500/30",
  warn: "bg-ember-500/15 text-ember-300 border-ember-500/40",
};

export function Badge({
  tone = "neutral",
  className = "",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border ${TONE_CLASSES[tone]} ${className}`}
      {...props}
    />
  );
}
