"use client";

import {
  Code2,
  GitBranch,
  Moon,
  Sun
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useRealtime } from "@/lib/realtime";
import { useWorkspaceStore } from "@/store/workspace-store";
import { IconButton } from "./ui/icon-button";
import { StatusPill } from "./dashboard/shared";

// Extracted dashboard panels
import { RepositoryPanel } from "./dashboard/repository-panel";
import { SemanticSearchPanel } from "./dashboard/semantic-search-panel";
import { ChatPanel } from "./dashboard/chat-panel";
import { TaskPanel } from "./dashboard/task-panel";
import { GenerationPanel } from "./dashboard/generation-panel";

const DEMO_ORG_ID = "22222222-2222-2222-2222-222222222222";

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
    <main className="min-h-screen bg-background text-foreground transition-colors duration-500">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-6 p-4 sm:p-6 lg:p-8">
        
        {/* MAANG-level Glassmorphism Header */}
        <header className="flex min-h-[4.5rem] flex-wrap items-center justify-between gap-4 rounded-2xl glass-panel px-5 py-3 shadow-sm sticky top-4 z-10">
          <div className="flex min-w-0 items-center gap-4">
            <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-accent to-purple-600 shadow-md">
              <Code2 aria-hidden className="h-6 w-6 text-white" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-bold tracking-tight">AI Engineering Workspace</h1>
              <p className="truncate text-sm font-medium text-muted-foreground mt-0.5">
                {selectedRepository ? `${selectedRepository.owner}/${selectedRepository.name}` : "No repository selected"}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <StatusPill label={realtime.status} tone={realtime.status === "online" ? "success" : "warning"} />
            <StatusPill label={`${realtime.onlineCount} online`} tone="neutral" />
            
            <div className="h-6 w-px bg-border/60 mx-1" />
            
            {selectedRepository ? (
              <IconButton
                icon={GitBranch}
                label={reindexMutation.isPending ? "Queueing..." : "Reindex"}
                variant="secondary"
                disabled={reindexMutation.isPending}
                onClick={() => reindexMutation.mutate(selectedRepository.id)}
                className="bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10"
              />
            ) : null}
            <IconButton
              icon={darkMode ? Sun : Moon}
              label={darkMode ? "Light Mode" : "Dark Mode"}
              variant="ghost"
              onClick={toggleDarkMode}
              className="text-muted-foreground hover:text-foreground"
            />
          </div>
        </header>

        {/* Dashboard Grid */}
        <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)] items-start">
          
          <RepositoryPanel
            repositories={repositories}
            selectedRepositoryId={selectedRepository?.id ?? null}
            loading={repositoriesQuery.isLoading}
            error={repositoriesQuery.error}
            importing={importMutation.isPending}
            onSelect={setSelectedRepositoryId}
            onImport={(value) => importMutation.mutate(value)}
          />

          <section className="grid min-w-0 gap-6 xl:grid-cols-2">
            <SemanticSearchPanel repository={selectedRepository} />
            <ChatPanel repository={selectedRepository} />
            <TaskPanel 
              repository={selectedRepository} 
              sendEvent={realtime.sendEvent} 
              subscribe={realtime.subscribe} 
            />
            <GenerationPanel repository={selectedRepository} />
          </section>
          
        </div>
      </div>
    </main>
  );
}
