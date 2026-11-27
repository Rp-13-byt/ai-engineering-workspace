import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FindingsPanel } from "@/components/changelens/findings-panel";
import { RiskScoreBadge } from "@/components/changelens/risk-badge";
import { RiskBreakdownCard } from "@/components/changelens/risk-breakdown-card";
import { TestPlanViewer } from "@/components/changelens/test-plan-viewer";
import type { ChangeAnalysis, ChangeFinding, ChangeTestPlan } from "@/types/api";

const mockAnalysis: ChangeAnalysis = {
  id: "11111111-1111-1111-1111-111111111111",
  repository_id: "22222222-2222-2222-2222-222222222222",
  base_sha: "abc1234567",
  head_sha: "def7654321",
  pr_number: 42,
  risk_score: 84.5,
  risk_level: "CRITICAL",
  confidence_score: 0.91,
  blast_radius: 14,
  summary: "Critical authentication middleware signature modified.",
  dimensions: [
    {
      name: "Blast Radius",
      score: 22.0,
      max_score: 25.0,
      explanation: "Impacts 14 downstream route handlers.",
      evidence: ["apps/api/auth.py", "apps/api/routes/users.py"]
    }
  ],
  breaking_indicators: ["Removed backward-compatible token parameter"],
  requires_human_approval: true,
  findings: [],
  test_plans: [],
  created_at: "2026-11-27T12:00:00Z"
};

const mockTestPlan: ChangeTestPlan = {
  id: "33333333-3333-3333-3333-333333333333",
  selection_mode: "fast_feedback",
  selected_tests_json: [
    {
      test_id: "tests/test_auth.py::test_verify_token",
      target_file: "apps/api/auth.py",
      estimated_duration_seconds: 1.8,
      tier: "critical",
      covered_node_ids: ["apps/api/auth.py:verify_token"],
      priority_score: 120.5,
      selection_reason: "Direct critical auth test"
    }
  ],
  omitted_tests_json: [
    {
      test_id: "tests/test_slow_e2e.py::test_full_flow",
      target_file: "apps/api/e2e.py",
      estimated_duration_seconds: 45.0,
      tier: "transitive",
      covered_node_ids: [],
      priority_score: 15.0,
      selection_reason: "Deferred"
    }
  ],
  estimated_duration_seconds: 1.8,
  coverage_ratio: 1.0,
  fallback_triggered: true,
  fallback_reason: "Fallback smoke tests included for unmapped edge module."
};

const mockFindings: ChangeFinding[] = [
  {
    id: "44444444-4444-4444-4444-444444444444",
    category: "breaking_change",
    severity: "critical",
    file_path: "apps/api/auth.py",
    symbol_name: "verify_token",
    message: "Signature change breaks 4 downstream callers",
    evidence_json: {}
  }
];

describe("ChangeLens UI Components", () => {
  it("renders RiskScoreBadge with score, level, and confidence", () => {
    render(<RiskScoreBadge riskLevel="LOW" riskScore={18.2} confidenceScore={0.88} />);
    expect(screen.getByText("Low Risk")).toBeInTheDocument();
    expect(screen.getByText("18.2/100")).toBeInTheDocument();
    expect(screen.getByText("(88% conf)")).toBeInTheDocument();
  });

  it("renders RiskBreakdownCard with dimensions, breaking indicators, and approval gate", () => {
    render(<RiskBreakdownCard analysis={mockAnalysis} />);
    expect(screen.getByText("Evidence-Based Change Risk Breakdown")).toBeInTheDocument();
    expect(screen.getByText("14 symbols")).toBeInTheDocument();
    expect(screen.getByText("Human Review Required")).toBeInTheDocument();
    expect(screen.getByText("Removed backward-compatible token parameter")).toBeInTheDocument();
    expect(screen.getAllByText("Blast Radius").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("22.0 / 25.0")).toBeInTheDocument();
  });

  it("renders TestPlanViewer with selected tests, omitted tests, and fallback notice", () => {
    render(<TestPlanViewer testPlan={mockTestPlan} />);
    expect(screen.getByText("Budget-Aware Regression Test Plan")).toBeInTheDocument();
    expect(screen.getByText("fast_feedback")).toBeInTheDocument();
    expect(screen.getByText("100% symbol coverage")).toBeInTheDocument();
    expect(screen.getByText("tests/test_auth.py::test_verify_token")).toBeInTheDocument();
    expect(screen.getByText("Fallback smoke tests included for unmapped edge module.")).toBeInTheDocument();
    expect(screen.getByText("Deferred by Budget (1)")).toBeInTheDocument();
  });

  it("renders FindingsPanel with findings and empty state", () => {
    const { rerender } = render(<FindingsPanel findings={mockFindings} />);
    expect(screen.getByText("Evidence Findings (1)")).toBeInTheDocument();
    expect(screen.getByText("Signature change breaks 4 downstream callers")).toBeInTheDocument();
    expect(screen.getByText("apps/api/auth.py:verify_token")).toBeInTheDocument();

    rerender(<FindingsPanel findings={[]} />);
    expect(screen.getByText("No critical or warning findings detected for this change.")).toBeInTheDocument();
  });
});
