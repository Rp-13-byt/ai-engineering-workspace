import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Dashboard } from "@/components/dashboard";

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    listRepositories: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
    listTasks: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 }))
  }
}));

function renderWithClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Dashboard />
    </QueryClientProvider>
  );
}

describe("Dashboard", () => {
  it("renders the workspace shell", () => {
    renderWithClient();
    expect(screen.getByText("AI Engineering Workspace")).toBeInTheDocument();
    expect(screen.getByText("Repositories")).toBeInTheDocument();
    expect(screen.getByText("AI code chat")).toBeInTheDocument();
  });
});
