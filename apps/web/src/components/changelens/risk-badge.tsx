"use client";

import { AlertTriangle, ShieldAlert, ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ChangeRiskLevel } from "@/types/api";

type RiskScoreBadgeProps = {
  riskLevel: ChangeRiskLevel | string;
  riskScore: number;
  confidenceScore?: number;
  className?: string;
};

const LEVEL_STYLES: Record<string, { container: string; dot: string; label: string }> = {
  LOW: {
    container: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    dot: "bg-emerald-500",
    label: "Low Risk"
  },
  MEDIUM: {
    container: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    dot: "bg-amber-500",
    label: "Medium Risk"
  },
  HIGH: {
    container: "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300",
    dot: "bg-orange-500",
    label: "High Risk"
  },
  CRITICAL: {
    container: "border-rose-500/40 bg-rose-500/15 text-rose-700 dark:text-rose-300",
    dot: "bg-rose-500",
    label: "Critical Risk"
  }
};

export function RiskScoreBadge({
  riskLevel,
  riskScore,
  confidenceScore,
  className
}: RiskScoreBadgeProps) {
  const normalized = riskLevel.toUpperCase();
  const style = LEVEL_STYLES[normalized] ?? LEVEL_STYLES.MEDIUM;

  const Icon =
    normalized === "LOW"
      ? ShieldCheck
      : normalized === "CRITICAL" || normalized === "HIGH"
        ? ShieldAlert
        : AlertTriangle;

  return (
    <div
      data-testid="changelens-risk-badge"
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium",
        style.container,
        className
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{style.label}</span>
      <span className="font-mono font-semibold">{riskScore.toFixed(1)}/100</span>
      {confidenceScore !== undefined && (
        <span className="opacity-75">({Math.round(confidenceScore * 100)}% conf)</span>
      )}
    </div>
  );
}
