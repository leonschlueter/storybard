import type { ReactNode } from "react";
import { Feather, User } from "lucide-react";

function Avatar({ isPlayer }: { isPlayer: boolean }) {
  return (
    <div
      className={`shrink-0 w-7 h-7 rounded-full flex items-center justify-center ${
        isPlayer ? "bg-ember-500/20 text-ember-300" : "bg-teal-500/15 text-teal-400"
      }`}
    >
      {isPlayer ? <User className="w-3.5 h-3.5" /> : <Feather className="w-3.5 h-3.5" />}
    </div>
  );
}

export function ChatBubble({
  from,
  children,
}: {
  from: "player" | "narrator";
  children: ReactNode;
}) {
  const isPlayer = from === "player";
  return (
    <div className={`flex items-end gap-2 ${isPlayer ? "justify-end" : "justify-start"}`}>
      {!isPlayer && <Avatar isPlayer={false} />}
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap animate-fade-in-up ${
          isPlayer
            ? "bg-ember-500/90 text-ink-950 rounded-br-sm"
            : "bg-ink-800 text-ink-100 border border-ink-700 rounded-bl-sm font-serif"
        }`}
      >
        {children}
      </div>
      {isPlayer && <Avatar isPlayer={true} />}
    </div>
  );
}
