"use client";

import { AlertCircle, AlertTriangle, Info, ShieldAlert } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ChangeFinding } from "@/types/api";

type FindingsPanelProps = {
  findings: ChangeFinding[];
  className?: string;
};

const SEVERITY_STYLES: Record<string, string> = {
  critical: "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300",
  high: "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300",
  warning: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  info: "border-sky-500/30 bg-sky-500/10 text-sky-700 dark:text-sky-300"
};

export function FindingsPanel({ findings, className }: FindingsPanelProps) {
  return (
    <section
      aria-label="ChangeLens Findings"
      className={cn(
        "rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950",
        className
      )}
    >
      <div className="flex items-center justify-between border-b border-slate-100 pb-3 dark:border-slate-800">
        <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
          Evidence Findings ({findings.length})
        </h3>
      </div>

      {findings.length === 0 ? (
        <p className="mt-4 text-sm text-slate-500 dark:text-slate-400">
          No critical or warning findings detected for this change.
        </p>
      ) : (
        <ul className="mt-4 space-y-2.5">
          {findings.map((finding) => {
            const sev = finding.severity.toLowerCase();
            const style = SEVERITY_STYLES[sev] ?? SEVERITY_STYLES.info;
            const Icon =
              sev === "critical"
                ? ShieldAlert
                : sev === "high"
                  ? AlertCircle
                  : sev === "warning"
                    ? AlertTriangle
                    : Info;

            return (
              <li
                key={finding.id}
                className={cn("rounded-lg border p-3 text-sm", style)}
              >
                <div className="flex items-start gap-2.5">
                  <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide">
                      <span>{finding.severity}</span>
                      <span className="opacity-70">• {finding.category}</span>
                    </div>
                    <p className="mt-1 font-medium">{finding.message}</p>
                    <p className="mt-1 font-mono text-xs opacity-80">
                      {finding.file_path}
                      {finding.symbol_name ? `:${finding.symbol_name}` : ""}
                    </p>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
