export type RepositoryStatus = "queued" | "indexing" | "indexed" | "failed";

export type Repository = {
  id: string;
  organization_id: string;
  provider: string;
  owner: string;
  name: string;
  default_branch: string;
  remote_url: string;
  indexing_status: RepositoryStatus;
  last_indexed_commit: string | null;
  created_at: string;
  updated_at: string;
};

export type SearchResult = {
  path: string;
  start_line: number;
  end_line: number;
  content: string;
  score: number;
};

export type ChatResponse = {
  conversation_id: string;
  answer: string;
  citations: Array<{
    path: string;
    start_line: number;
    end_line: number;
    score: number;
  }>;
  created_at: string;
};

export type TaskStatus = "todo" | "in_progress" | "blocked" | "done";

export type WorkspaceTask = {
  id: string;
  repository_id: string;
  assignee_id: string | null;
  title: string;
  description: string;
  status: TaskStatus;
  priority: number;
  created_at: string;
  updated_at: string;
};

export type PullRequestDraft = {
  id: string;
  repository_id: string;
  title: string;
  body: string;
  branch_name: string;
  diff: string;
  status: string;
  github_url: string | null;
  created_at: string;
};

export type ChangeRiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type SelectionMode = "fast_feedback" | "balanced" | "full_regression";

export type RiskDimension = {
  name: string;
  score: number;
  max_score: number;
  explanation: string;
  evidence: string[];
};

export type ChangeFinding = {
  id: string;
  category: string;
  severity: string;
  file_path: string;
  symbol_name: string | null;
  message: string;
  evidence_json: Record<string, unknown>;
};

export type TestCandidateItem = {
  test_id: string;
  target_file: string;
  estimated_duration_seconds: number;
  tier: string;
  covered_node_ids: string[];
  priority_score: number;
  selection_reason: string;
};

export type ChangeTestPlan = {
  id: string;
  selection_mode: SelectionMode | string;
  selected_tests_json: TestCandidateItem[];
  omitted_tests_json: TestCandidateItem[];
  estimated_duration_seconds: number;
  coverage_ratio: number;
  fallback_triggered: boolean;
  fallback_reason: string | null;
};

export type ChangeAnalysis = {
  id: string;
  repository_id: string;
  base_sha: string;
  head_sha: string;
  pr_number: number | null;
  risk_score: number;
  risk_level: ChangeRiskLevel | string;
  confidence_score: number;
  blast_radius: number;
  summary: string;
  dimensions: RiskDimension[];
  breaking_indicators: string[];
  requires_human_approval: boolean;
  findings: ChangeFinding[];
  test_plans: ChangeTestPlan[];
  created_at: string;
};

export type ChangeAnalysisRequest = {
  repository_id: string;
  base_sha: string;
  head_sha: string;
  diff_text: string;
  selection_mode?: SelectionMode;
  pr_number?: number | null;
  file_contents?: Record<string, string>;
  test_index?: Record<string, string[]>;
};

export type ChangeAnalysisListResponse = {
  items: ChangeAnalysis[];
  total: number;
};
