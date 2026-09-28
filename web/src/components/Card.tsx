import type { HTMLAttributes } from "react";

export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`bg-ink-900 border border-ink-700 rounded-xl p-4 ${className}`}
      {...props}
    />
  );
}
