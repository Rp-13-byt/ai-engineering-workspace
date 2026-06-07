import type { ChatResponse, PullRequestDraft, Repository, SearchResult, WorkspaceTask } from "@/types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const DEMO_ORG_ID = "22222222-2222-2222-2222-222222222222";

type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("workspace.accessToken") : null;
  const organizationId =
    typeof window !== "undefined" ? window.localStorage.getItem("workspace.organizationId") ?? DEMO_ORG_ID : DEMO_ORG_ID;
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Organization-Id": organizationId,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers
    },
    cache: "no-store"
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ error: response.statusText }));
    throw new ApiError(payload.error ?? "Request failed", response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  login: (input: { email: string; password: string }) =>
    request<{
      access_token: string;
      refresh_token: string;
      expires_at: string;
      user: { id: string; email: string; display_name: string };
      organization: { id: string; slug: string; name: string };
    }>("/auth/login", { method: "POST", body: JSON.stringify(input) }),
  listRepositories: (offset = 0) => request<Page<Repository>>(`/repositories?limit=20&offset=${offset}`),
  importRepository: (input: { owner: string; name: string }) =>
    request<Repository>("/repositories/import", { method: "POST", body: JSON.stringify(input) }),
  reindexRepository: (repositoryId: string) =>
    request<{ repository_id: string; status: string }>(`/repositories/${repositoryId}/reindex`, { method: "POST" }),
  semanticSearch: (input: { repository_id: string; query: string; limit: number }) =>
    request<{ results: SearchResult[]; cached: boolean }>("/search/semantic", {
      method: "POST",
      body: JSON.stringify(input)
    }),
  chat: (input: { repository_id: string; message: string; conversation_id?: string }) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(input) }),
  generatePullRequest: (input: { repository_id: string; instructions: string; open_on_github: boolean }) =>
    request<PullRequestDraft>("/pull-requests/generate", { method: "POST", body: JSON.stringify(input) }),
  listTasks: ({ offset = 0, repositoryId }: { offset?: number; repositoryId?: string }) => {
    const params = new URLSearchParams({ limit: "20", offset: String(offset) });
    if (repositoryId) params.set("repository_id", repositoryId);
    return request<Page<WorkspaceTask>>(`/tasks?${params.toString()}`);
  },
  createTask: (input: { repository_id: string; title: string; description: string; priority: number }) =>
    request<WorkspaceTask>("/tasks", { method: "POST", body: JSON.stringify(input) }),
  generateDocs: (input: { repository_id: string; target: string }) =>
    request<{ markdown: string }>("/docs/generate", { method: "POST", body: JSON.stringify(input) }),
  generateTests: (input: { repository_id: string; target: string }) =>
    request<{ test_plan: string }>("/docs/tests", { method: "POST", body: JSON.stringify(input) }),
  detectBugs: (input: { repository_id: string; target: string }) =>
    request<{ findings: Array<{ path: string; severity: string; message: string }> }>("/docs/bugs", {
      method: "POST",
      body: JSON.stringify(input)
    })
};
