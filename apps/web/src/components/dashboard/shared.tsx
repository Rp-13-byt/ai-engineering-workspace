import { CheckCircle2, CircleDot, Loader2, Shield, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";

export function Panel({
  title,
  icon: Icon,
  children
}: {
  title: string;
  icon: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <section className="min-w-0 glass-panel rounded-xl overflow-hidden transition-all duration-300 hover:shadow-md">
      <div className="flex items-center justify-between border-b border-border/50 bg-black/5 dark:bg-white/5 px-4 py-3">
        <div className="flex items-center gap-2">
          <Icon aria-hidden className="h-4 w-4 text-accent" />
          <h2 className="text-sm font-semibold tracking-tight">{title}</h2>
        </div>
        <Shield aria-hidden className="h-4 w-4 text-muted/50" />
      </div>
      <div className="p-4 space-y-4">{children}</div>
    </section>
  );
}

export function RowSkeleton({ count }: { count: number }) {
  return (
    <div className="space-y-1">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="border border-transparent p-3 rounded-lg bg-black/5 dark:bg-white/5 animate-pulse">
          <div className="h-4 w-3/4 rounded bg-black/10 dark:bg-white/10" />
          <div className="mt-2 h-3 w-1/2 rounded bg-black/10 dark:bg-white/10" />
        </div>
      ))}
    </div>
  );
}

export function ErrorStrip({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? `${error.status}: ${error.message}` : "Request failed";
  return <div className="rounded-lg bg-danger/10 p-3 text-sm font-medium text-danger">{message}</div>;
}

export function LoaderLine({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm font-medium text-muted">
      <Loader2 aria-hidden className="h-4 w-4 animate-spin text-accent" />
      <span>{label}</span>
    </div>
  );
}

export function StatusPill({ label, tone }: { label: string; tone: "success" | "warning" | "danger" | "neutral" }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-semibold uppercase tracking-wider backdrop-blur-sm",
        tone === "success" && "bg-success/10 text-success border-success/20",
        tone === "warning" && "bg-warning/10 text-warning border-warning/20",
        tone === "danger" && "bg-danger/10 text-danger border-danger/20",
        tone === "neutral" && "bg-muted/10 text-muted-foreground border-border"
      )}
    >
      {tone === "success" ? <CheckCircle2 aria-hidden className="h-3 w-3" /> : <CircleDot aria-hidden className="h-3 w-3" />}
      {label}
    </span>
  );
}
