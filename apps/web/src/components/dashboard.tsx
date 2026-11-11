"use client";

import {
  Bot,
  Bug,
  CheckCircle2,
  CircleDot,
  Code2,
  FileText,
  GitBranch,
  GitPullRequest,
  Loader2,
  Moon,
  Plus,
  Search,
  Shield,
  Sparkles,
  Sun,
  TestTube2,
  type LucideIcon
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

import { api, ApiError } from "@/lib/api";
import { useRealtime } from "@/lib/realtime";
import { cn } from "@/lib/utils";
import { useWorkspaceStore } from "@/store/workspace-store";
import type { PullRequestDraft, Repository, SearchResult, WorkspaceTask } from "@/types/api";

import { IconButton } from "./ui/icon-button";

const DEMO_ORG_ID = "22222222-2222-2222-2222-222222222222";

const importSchema = z.object({
  owner: z.string().min(1).max(120),
  name: z.string().min(1).max(160)
});

const searchSchema = z.object({
  query: z.string().min(2).max(2000)
});

const chatSchema = z.object({
  message: z.string().min(2).max(8000)
});

const taskSchema = z.object({
  title: z.string().min(2).max(240),
  description: z.string().max(8000),
  priority: z.coerce.number().min(1).max(5)
});

const generationSchema = z.object({
  target: z.string().min(2).max(500)
});

type ImportForm = z.infer<typeof importSchema>;
type SearchForm = z.infer<typeof searchSchema>;
type ChatForm = z.infer<typeof chatSchema>;
type TaskForm = z.infer<typeof taskSchema>;
type GenerationForm = z.infer<typeof generationSchema>;

export function Dashboard() {
  const queryClient = useQueryClient();
  const selectedRepositoryId = useWorkspaceStore((state) => state.selectedRepositoryId);
  const setSelectedRepositoryId = useWorkspaceStore((state) => state.setSelectedRepositoryId);
  const darkMode = useWorkspaceStore((state) => state.darkMode);
  const toggleDarkMode = useWorkspaceStore((state) => state.toggleDarkMode);
  const [token, setToken] = useState<string | null>(null);
  const realtime = useRealtime(DEMO_ORG_ID, token);

  useEffect(() => {
    setToken(window.localStorage.getItem("workspace.accessToken"));
  }, []);

  const repositoriesQuery = useQuery({
    queryKey: ["repositories"],
    queryFn: () => api.listRepositories(0)
  });

  const repositories = repositoriesQuery.data?.items ?? [];
  const selectedRepository = useMemo(
    () => repositories.find((repository) => repository.id === selectedRepositoryId) ?? repositories[0] ?? null,
    [repositories, selectedRepositoryId]
  );

  useEffect(() => {
    if (!selectedRepositoryId && repositories[0]) {
      setSelectedRepositoryId(repositories[0].id);
    }
  }, [repositories, selectedRepositoryId, setSelectedRepositoryId]);

  const importMutation = useMutation({
    mutationFn: api.importRepository,
    onSuccess: (repository) => {
      setSelectedRepositoryId(repository.id);
      void queryClient.invalidateQueries({ queryKey: ["repositories"] });
    }
  });

  const reindexMutation = useMutation({
    mutationFn: api.reindexRepository,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["repositories"] })
  });

  return (
    <main className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-4 p-3 sm:p-4">
        <header className="flex min-h-16 flex-wrap items-center justify-between gap-3 border border-border bg-panel px-3 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center border border-border bg-background">
              <Code2 aria-hidden className="h-5 w-5 text-accent" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-base font-semibold sm:text-lg">AI Engineering Workspace</h1>
              <p className="truncate text-xs text-muted">
                {selectedRepository ? `${selectedRepository.owner}/${selectedRepository.name}` : "No repository selected"}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill label={realtime.status} tone={realtime.status === "online" ? "success" : "warning"} />
            <StatusPill label={`${realtime.onlineCount} online`} tone="neutral" />
            {selectedRepository ? (
              <IconButton
                icon={GitBranch}
                label={reindexMutation.isPending ? "Queueing" : "Reindex"}
                variant="secondary"
                disabled={reindexMutation.isPending}
                onClick={() => reindexMutation.mutate(selectedRepository.id)}
              />
            ) : null}
            <IconButton
              icon={darkMode ? Sun : Moon}
              label={darkMode ? "Light" : "Dark"}
              variant="ghost"
              onClick={toggleDarkMode}
            />
          </div>
        </header>

        <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
          <RepositoryPanel
            repositories={repositories}
            selectedRepositoryId={selectedRepository?.id ?? null}
            loading={repositoriesQuery.isLoading}
            error={repositoriesQuery.error}
            importing={importMutation.isPending}
            onSelect={setSelectedRepositoryId}
            onImport={(value) => importMutation.mutate(value)}
          />

          <section className="grid min-w-0 gap-4 xl:grid-cols-2">
            <SemanticSearchPanel repository={selectedRepository} />
            <ChatPanel repository={selectedRepository} />
            <TaskPanel repository={selectedRepository} />
            <GenerationPanel repository={selectedRepository} />
          </section>
        </div>
      </div>
    </main>
  );
}

function RepositoryPanel({
  repositories,
  selectedRepositoryId,
  loading,
  error,
  importing,
  onSelect,
  onImport
}: {
  repositories: Repository[];
  selectedRepositoryId: string | null;
  loading: boolean;
  error: Error | null;
  importing: boolean;
  onSelect: (repositoryId: string) => void;
  onImport: (value: ImportForm) => void;
}) {
  const form = useForm<ImportForm>({
    resolver: zodResolver(importSchema),
    defaultValues: { owner: "openai", name: "openai-python" }
  });

  return (
    <aside className="min-h-[calc(100vh-7rem)] border border-border bg-panel">
      <div className="border-b border-border p-3">
        <h2 className="text-sm font-semibold">Repositories</h2>
      </div>
      <form
        className="grid gap-2 border-b border-border p-3"
        onSubmit={form.handleSubmit((value) => onImport(value))}
      >
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs font-medium text-muted">
            Owner
            <input className="mt-1 h-10 w-full border border-border bg-background px-2 text-sm text-foreground" {...form.register("owner")} />
          </label>
          <label className="text-xs font-medium text-muted">
            Repo
            <input className="mt-1 h-10 w-full border border-border bg-background px-2 text-sm text-foreground" {...form.register("name")} />
          </label>
        </div>
        <IconButton icon={Plus} label={importing ? "Importing" : "Import"} disabled={importing} type="submit" />
      </form>
      <div className="max-h-[calc(100vh-17rem)] overflow-y-auto">
        {loading ? <RowSkeleton count={4} /> : null}
        {error ? <ErrorStrip error={error} /> : null}
        {repositories.map((repository) => (
          <button
            key={repository.id}
            className={cn(
              "flex w-full items-center justify-between gap-3 border-b border-border px-3 py-3 text-left transition hover:bg-background",
              selectedRepositoryId === repository.id && "bg-background"
            )}
            onClick={() => onSelect(repository.id)}
          >
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">
                {repository.owner}/{repository.name}
              </span>
              <span className="block truncate text-xs text-muted">{repository.default_branch}</span>
            </span>
            <StatusPill label={repository.indexing_status} tone={statusTone(repository.indexing_status)} />
          </button>
        ))}
      </div>
    </aside>
  );
}

function SemanticSearchPanel({ repository }: { repository: Repository | null }) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const form = useForm<SearchForm>({
    resolver: zodResolver(searchSchema),
    defaultValues: { query: "Where is authentication enforced?" }
  });
  const searchMutation = useMutation({
    mutationFn: api.semanticSearch,
    onSuccess: (response) => setResults(response.results)
  });

  return (
    <Panel title="Semantic search" icon={Search}>
      <form
        className="flex gap-2"
        onSubmit={form.handleSubmit((value) => {
          if (repository) searchMutation.mutate({ repository_id: repository.id, query: value.query, limit: 8 });
        })}
      >
        <input
          className="h-10 min-w-0 flex-1 border border-border bg-background px-3 text-sm"
          aria-label="Search query"
          {...form.register("query")}
        />
        <IconButton icon={Search} label="Search" disabled={!repository || searchMutation.isPending} type="submit" />
      </form>
      <div className="mt-3 max-h-72 overflow-y-auto border border-border">
        {searchMutation.isPending ? <RowSkeleton count={3} /> : null}
        {searchMutation.error ? <ErrorStrip error={searchMutation.error} /> : null}
        {results.map((result) => (
          <article key={`${result.path}-${result.start_line}`} className="border-b border-border p-3 last:border-b-0">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="truncate text-sm font-medium">{result.path}</p>
              <span className="text-xs text-muted">{Math.round(result.score * 100)}%</span>
            </div>
            <pre className="max-h-32 overflow-auto whitespace-pre-wrap text-xs leading-5 text-muted">
              {result.content}
            </pre>
          </article>
        ))}
      </div>
    </Panel>
  );
}

function ChatPanel({ repository }: { repository: Repository | null }) {
  const conversationId = useWorkspaceStore((state) => state.conversationId);
  const setConversationId = useWorkspaceStore((state) => state.setConversationId);
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);
  const form = useForm<ChatForm>({
    resolver: zodResolver(chatSchema),
    defaultValues: { message: "Find likely scalability risks in this repository." }
  });
  const chatMutation = useMutation({
    mutationFn: api.chat,
    onSuccess: (response) => {
      setConversationId(response.conversation_id);
      setMessages((current) => [...current, { role: "assistant", content: response.answer }]);
    }
  });

  return (
    <Panel title="AI code chat" icon={Bot}>
      <div className="mb-3 h-64 overflow-y-auto border border-border bg-background p-3">
        {messages.length === 0 ? <p className="text-sm text-muted">Ask about the selected codebase.</p> : null}
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className="mb-3 last:mb-0">
            <p className="mb-1 text-xs font-semibold uppercase tracking-normal text-muted">{message.role}</p>
            <p className="whitespace-pre-wrap text-sm leading-6">{message.content}</p>
          </div>
        ))}
        {chatMutation.isPending ? <LoaderLine label="Thinking" /> : null}
      </div>
      <form
        className="flex gap-2"
        onSubmit={form.handleSubmit((value) => {
          if (!repository) return;
          setMessages((current) => [...current, { role: "user", content: value.message }]);
          chatMutation.mutate({
            repository_id: repository.id,
            message: value.message,
            ...(conversationId ? { conversation_id: conversationId } : {})
          });
          form.reset({ message: "" });
        })}
      >
        <input className="h-10 min-w-0 flex-1 border border-border bg-background px-3 text-sm" {...form.register("message")} />
        <IconButton icon={Sparkles} label="Send" disabled={!repository || chatMutation.isPending} type="submit" />
      </form>
    </Panel>
  );
}

function TaskPanel({ repository }: { repository: Repository | null }) {
  const queryClient = useQueryClient();
  const form = useForm<TaskForm>({
    resolver: zodResolver(taskSchema),
    defaultValues: { title: "", description: "", priority: 3 }
  });
  const tasksQuery = useInfiniteQuery({
    queryKey: ["tasks", repository?.id],
    queryFn: ({ pageParam }) => api.listTasks({ repositoryId: repository?.id, offset: pageParam }),
    initialPageParam: 0,
    enabled: Boolean(repository),
    getNextPageParam: (lastPage) =>
      lastPage.offset + lastPage.items.length < lastPage.total ? lastPage.offset + lastPage.limit : undefined
  });
  const createTaskMutation = useMutation({
    mutationFn: api.createTask,
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: ["tasks", repository?.id] });
      return { input };
    },
    onSuccess: () => {
      form.reset({ title: "", description: "", priority: 3 });
      void queryClient.invalidateQueries({ queryKey: ["tasks", repository?.id] });
    }
  });
  const tasks = tasksQuery.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Panel title="Tasks" icon={CheckCircle2}>
      <form
        className="grid gap-2"
        onSubmit={form.handleSubmit((value) => {
          if (!repository) return;
          createTaskMutation.mutate({ repository_id: repository.id, ...value });
        })}
      >
        <div className="grid gap-2 sm:grid-cols-[1fr_88px]">
          <input
            className="h-10 border border-border bg-background px-3 text-sm"
            placeholder="Task title"
            {...form.register("title")}
          />
          <input
            className="h-10 border border-border bg-background px-3 text-sm"
            type="number"
            min={1}
            max={5}
            aria-label="Priority"
            {...form.register("priority")}
          />
        </div>
        <textarea
          className="min-h-20 resize-y border border-border bg-background px-3 py-2 text-sm"
          placeholder="Description"
          {...form.register("description")}
        />
        <IconButton icon={Plus} label="Add task" disabled={!repository || createTaskMutation.isPending} type="submit" />
      </form>
      <div className="mt-3 max-h-64 overflow-y-auto border border-border">
        {tasksQuery.isLoading ? <RowSkeleton count={3} /> : null}
        {tasks.map((task) => (
          <TaskRow key={task.id} task={task} />
        ))}
        {tasksQuery.hasNextPage ? (
          <button className="h-10 w-full text-sm text-accent" onClick={() => void tasksQuery.fetchNextPage()}>
            Load more
          </button>
        ) : null}
      </div>
    </Panel>
  );
}

function GenerationPanel({ repository }: { repository: Repository | null }) {
  const form = useForm<GenerationForm>({
    resolver: zodResolver(generationSchema),
    defaultValues: { target: "authentication and repository import" }
  });
  const [draft, setDraft] = useState<PullRequestDraft | null>(null);
  const [output, setOutput] = useState("");
  const docsMutation = useMutation({
    mutationFn: api.generateDocs,
    onSuccess: (response) => setOutput(response.markdown)
  });
  const testsMutation = useMutation({
    mutationFn: api.generateTests,
    onSuccess: (response) => setOutput(response.test_plan)
  });
  const bugsMutation = useMutation({
    mutationFn: api.detectBugs,
    onSuccess: (response) => setOutput(response.findings.map((finding) => `${finding.severity}: ${finding.path} - ${finding.message}`).join("\n") || "No findings.")
  });
  const prMutation = useMutation({
    mutationFn: api.generatePullRequest,
    onSuccess: (response) => {
      setDraft(response);
      setOutput(response.diff);
    }
  });

  const run = form.handleSubmit((value) => {
    if (!repository) return;
    docsMutation.mutate({ repository_id: repository.id, target: value.target });
  });

  const pending = docsMutation.isPending || testsMutation.isPending || bugsMutation.isPending || prMutation.isPending;

  return (
    <Panel title="Generation" icon={GitPullRequest}>
      <form className="grid gap-2" onSubmit={run}>
        <input className="h-10 border border-border bg-background px-3 text-sm" {...form.register("target")} />
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <IconButton icon={FileText} label="Docs" disabled={!repository || pending} type="submit" />
          <IconButton
            icon={TestTube2}
            label="Tests"
            variant="secondary"
            disabled={!repository || pending}
            type="button"
            onClick={form.handleSubmit((value) => repository && testsMutation.mutate({ repository_id: repository.id, target: value.target }))}
          />
          <IconButton
            icon={Bug}
            label="Bugs"
            variant="secondary"
            disabled={!repository || pending}
            type="button"
            onClick={form.handleSubmit((value) => repository && bugsMutation.mutate({ repository_id: repository.id, target: value.target }))}
          />
          <IconButton
            icon={GitPullRequest}
            label="PR"
            variant="secondary"
            disabled={!repository || pending}
            type="button"
            onClick={form.handleSubmit((value) =>
              repository &&
              prMutation.mutate({ repository_id: repository.id, instructions: value.target, open_on_github: false })
            )}
          />
        </div>
      </form>
      {pending ? <LoaderLine label="Generating" /> : null}
      {draft ? (
        <div className="mt-3 border border-border p-3">
          <p className="truncate text-sm font-semibold">{draft.title}</p>
          <p className="mt-1 truncate text-xs text-muted">{draft.branch_name}</p>
        </div>
      ) : null}
      <pre className="mt-3 max-h-64 overflow-auto border border-border bg-background p-3 text-xs leading-5 text-muted">
        {output || "Generated output appears here."}
      </pre>
    </Panel>
  );
}

function Panel({
  title,
  icon: Icon,
  children
}: {
  title: string;
  icon: LucideIcon;
  children: React.ReactNode;
}) {
  return (
    <section className="min-w-0 border border-border bg-panel">
      <div className="flex items-center justify-between border-b border-border px-3 py-3">
        <div className="flex items-center gap-2">
          <Icon aria-hidden className="h-4 w-4 text-accent" />
          <h2 className="text-sm font-semibold">{title}</h2>
        </div>
        <Shield aria-hidden className="h-4 w-4 text-muted" />
      </div>
      <div className="p-3">{children}</div>
    </section>
  );
}

function TaskRow({ task }: { task: WorkspaceTask }) {
  return (
    <article className="flex items-start justify-between gap-3 border-b border-border p-3 last:border-b-0">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{task.title}</p>
        <p className="line-clamp-2 text-xs text-muted">{task.description || "No description"}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <StatusPill label={task.status.replace("_", " ")} tone={task.status === "done" ? "success" : "neutral"} />
        <span className="text-xs text-muted">P{task.priority}</span>
      </div>
    </article>
  );
}

function RowSkeleton({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="border-b border-border p-3">
          <div className="h-4 w-3/4 animate-pulse bg-muted/20" />
          <div className="mt-2 h-3 w-1/2 animate-pulse bg-muted/20" />
        </div>
      ))}
    </>
  );
}

function ErrorStrip({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? `${error.status}: ${error.message}` : "Request failed";
  return <div className="border-b border-border p-3 text-sm text-danger">{message}</div>;
}

function LoaderLine({ label }: { label: string }) {
  return (
    <div className="mt-3 flex items-center gap-2 text-sm text-muted">
      <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
      <span>{label}</span>
    </div>
  );
}

function StatusPill({ label, tone }: { label: string; tone: "success" | "warning" | "danger" | "neutral" }) {
  return (
    <span
      className={cn(
        "inline-flex h-7 items-center gap-1 border px-2 text-xs font-medium",
        tone === "success" && "border-success/40 text-success",
        tone === "warning" && "border-warning/40 text-warning",
        tone === "danger" && "border-danger/40 text-danger",
        tone === "neutral" && "border-border text-muted"
      )}
    >
      {tone === "success" ? <CheckCircle2 aria-hidden className="h-3 w-3" /> : <CircleDot aria-hidden className="h-3 w-3" />}
      {label}
    </span>
  );
}

function statusTone(status: Repository["indexing_status"]) {
  if (status === "indexed") return "success";
  if (status === "failed") return "danger";
  if (status === "indexing") return "warning";
  return "neutral";
}
