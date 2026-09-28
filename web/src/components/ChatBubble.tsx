import type { ReactNode } from "react";

export function ChatBubble({
  from,
  children,
}: {
  from: "player" | "narrator";
  children: ReactNode;
}) {
  const isPlayer = from === "player";
  return (
    <div className={`flex ${isPlayer ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
          isPlayer
            ? "bg-ember-500/90 text-ink-950 rounded-br-sm"
            : "bg-ink-800 text-ink-100 border border-ink-700 rounded-bl-sm font-serif"
        }`}
      >
        {children}
      </div>
    </div>
  );
}
