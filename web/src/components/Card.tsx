import type { HTMLAttributes } from "react";

type Variant = "flat" | "elevated" | "interactive";

const VARIANT_CLASSES: Record<Variant, string> = {
  flat: "bg-ink-900 border border-ink-700",
  elevated: "bg-ink-900 border border-ink-700 shadow-md",
  interactive: "bg-ink-900 border border-ink-700 shadow-sm hover:shadow-md hover:border-ink-600 transition-all duration-200 cursor-pointer",
};

export function Card({
  variant = "flat",
  className = "",
  ...props
}: HTMLAttributes<HTMLDivElement> & { variant?: Variant }) {
  return (
    <div
      className={`rounded-xl p-4 ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  );
}
