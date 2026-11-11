import type { LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  icon: LucideIcon;
  label: string;
  variant?: "primary" | "secondary" | "ghost" | "danger";
};

const variants = {
  primary: "border-accent bg-accent text-white hover:bg-accent/90",
  secondary: "border-border bg-panel text-foreground hover:bg-background",
  ghost: "border-transparent bg-transparent text-foreground hover:bg-panel",
  danger: "border-danger bg-danger text-white hover:bg-danger/90"
};

export function IconButton({ icon: Icon, label, variant = "primary", className, ...props }: IconButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-10 items-center justify-center gap-2 border px-3 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
        variants[variant],
        className
      )}
      title={label}
      aria-label={label}
      {...props}
    >
      <Icon aria-hidden className="h-4 w-4 shrink-0" />
      <span className="truncate">{label}</span>
    </button>
  );
}
