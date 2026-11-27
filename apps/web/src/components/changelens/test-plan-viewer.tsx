"use client";

import { AlertTriangle, CheckCircle2, Clock, FlaskConical } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ChangeTestPlan } from "@/types/api";

type TestPlanViewerProps = {
  testPlan: ChangeTestPlan;
  className?: string;
};

const TIER_BADGE_STYLES: Record<string, string> = {
  critical: "bg-rose-500/15 text-rose-700 dark:text-rose-300",
  direct: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
  transitive: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  smoke: "bg-slate-500/15 text-slate-700 dark:text-slate-300"
};

export function TestPlanViewer({ testPlan, className }: TestPlanViewerProps) {
  const coveragePct = Math.round(testPlan.coverage_ratio * 100);

  return (
    <section
      aria-label="Budget-Aware Regression Test Plan"
      className={cn(
        "rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-950",
        className
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-indigo-500" aria-hidden="true" />
            <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Budget-Aware Regression Test Plan
            </h3>
          </div>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            Selection mode:{" "}
            <span className="font-mono font-medium text-slate-700 dark:text-slate-300">
              {testPlan.selection_mode}
            </span>
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
            <Clock className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
            <span>{testPlan.estimated_duration_seconds.toFixed(1)}s est.</span>
          </div>
          <div className="rounded-full bg-emerald-500/10 px-2.5 py-1 font-medium text-emerald-700 dark:text-emerald-300">
            {coveragePct}% symbol coverage
          </div>
        </div>
      </div>

      {testPlan.fallback_triggered && (
        <div
          role="status"
          className="mt-4 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{testPlan.fallback_reason ?? "Fallback smoke suite selected."}</span>
        </div>
      )}

      <div className="mt-4 space-y-2">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Selected Tests ({testPlan.selected_tests_json.length})
        </h4>
        {testPlan.selected_tests_json.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">No tests selected.</p>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-100 dark:divide-slate-800 dark:border-slate-800">
            {testPlan.selected_tests_json.map((test) => {
              const tierStyle =
                TIER_BADGE_STYLES[test.tier.toLowerCase()] ?? TIER_BADGE_STYLES.direct;
              return (
                <li
                  key={test.test_id}
                  className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 text-sm"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" aria-hidden="true" />
                      <span className="truncate font-mono text-xs font-medium text-slate-900 dark:text-slate-100">
                        {test.test_id}
                      </span>
                    </div>
                    {test.selection_reason && (
                      <p className="mt-0.5 pl-5 text-xs text-slate-500 dark:text-slate-400">
                        {test.selection_reason}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className={cn("rounded px-2 py-0.5 font-medium capitalize", tierStyle)}>
                      {test.tier}
                    </span>
                    <span className="font-mono text-slate-500 dark:text-slate-400">
                      p={test.priority_score.toFixed(1)}
                    </span>
                    <span className="font-mono text-slate-500 dark:text-slate-400">
                      {test.estimated_duration_seconds.toFixed(1)}s
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {testPlan.omitted_tests_json.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Deferred by Budget ({testPlan.omitted_tests_json.length})
          </h4>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {testPlan.omitted_tests_json.map((t) => t.test_id).join(", ")}
          </p>
        </div>
      )}
    </section>
  );
}
