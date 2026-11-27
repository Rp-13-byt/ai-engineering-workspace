"use client";

import { Activity, AlertOctagon, GitCommit, ShieldAlert } from "lucide-react";

import type { ChangeAnalysis } from "@/types/api";
import { cn } from "@/lib/utils";

import { RiskScoreBadge } from "./risk-badge";

type RiskBreakdownCardProps = {
  analysis: ChangeAnalysis;
  className?: string;
};

export function RiskBreakdownCard({ analysis, className }: RiskBreakdownCardProps) {
  const confidencePct = Math.round(analysis.confidence_score * 100);

  return (
    <section
      aria-label="ChangeLens Risk Assessment"
      className={cn(
        "rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950",
        className
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
            <GitCommit className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="font-mono">
              {analysis.base_sha.slice(0, 7)} → {analysis.head_sha.slice(0, 7)}
            </span>
            {analysis.pr_number !== null && <span>• PR #{analysis.pr_number}</span>}
          </div>
          <h3 className="mt-1 text-base font-semibold text-slate-900 dark:text-slate-100">
            Evidence-Based Change Risk Breakdown
          </h3>
          {analysis.summary && (
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{analysis.summary}</p>
          )}
        </div>

        <RiskScoreBadge
          riskLevel={analysis.risk_level}
          riskScore={analysis.risk_score}
          confidenceScore={analysis.confidence_score}
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-900">
          <div className="text-xs text-slate-500 dark:text-slate-400">Blast Radius</div>
          <div className="mt-0.5 flex items-center gap-1.5 text-lg font-semibold text-slate-900 dark:text-slate-100">
            <Activity className="h-4 w-4 text-indigo-500" aria-hidden="true" />
            <span>{analysis.blast_radius} symbols</span>
          </div>
        </div>
        <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-900">
          <div className="text-xs text-slate-500 dark:text-slate-400">Evidence Confidence</div>
          <div className="mt-0.5 text-lg font-semibold text-slate-900 dark:text-slate-100">
            {confidencePct}%
          </div>
        </div>
        <div className="col-span-2 rounded-lg bg-slate-50 p-3 sm:col-span-1 dark:bg-slate-900">
          <div className="text-xs text-slate-500 dark:text-slate-400">Approval Gate</div>
          <div className="mt-0.5 text-sm font-semibold text-slate-900 dark:text-slate-100">
            {analysis.requires_human_approval ? "Human Review Required" : "Standard Checks"}
          </div>
        </div>
      </div>

      {analysis.requires_human_approval && (
        <div
          role="alert"
          className="mt-4 flex items-start gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200"
        >
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            High-impact change detected. Deterministic policy requires human reviewer sign-off before merge.
          </span>
        </div>
      )}

      {analysis.breaking_indicators.length > 0 && (
        <div className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-rose-700 dark:text-rose-300">
            <AlertOctagon className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Breaking Change Indicators</span>
          </div>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-rose-800 dark:text-rose-200">
            {analysis.breaking_indicators.map((indicator, idx) => (
              <li key={idx}>{indicator}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 space-y-3">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Risk Dimensions
        </h4>
        {analysis.dimensions.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">No dimension details recorded.</p>
        ) : (
          analysis.dimensions.map((dim) => {
            const pct = dim.max_score > 0 ? Math.min(100, Math.round((dim.score / dim.max_score) * 100)) : 0;
            return (
              <div key={dim.name} className="space-y-1">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-800 dark:text-slate-200">{dim.name}</span>
                  <span className="font-mono text-xs text-slate-600 dark:text-slate-400">
                    {dim.score.toFixed(1)} / {dim.max_score.toFixed(1)}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      pct >= 75 ? "bg-rose-500" : pct >= 45 ? "bg-amber-500" : "bg-emerald-500"
                    )}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-400">{dim.explanation}</p>
                {dim.evidence.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-0.5">
                    {dim.evidence.slice(0, 5).map((ev, idx) => (
                      <span
                        key={idx}
                        className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                      >
                        {ev}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
