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
