import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-ember-500 hover:bg-ember-400 text-ink-950 font-medium disabled:bg-ink-700 disabled:text-ink-400",
  secondary:
    "bg-ink-700 hover:bg-ink-600 text-ink-100 disabled:bg-ink-800 disabled:text-ink-500",
  ghost:
    "bg-transparent hover:bg-ink-800 text-ink-300 disabled:text-ink-600",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`px-4 py-2 rounded-lg text-sm transition-colors disabled:cursor-not-allowed cursor-pointer ${VARIANT_CLASSES[variant]} ${className}`}
      {...props}
    />
  );
}
