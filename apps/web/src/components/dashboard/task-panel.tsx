import { CheckCircle2, Plus } from "lucide-react";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { motion, AnimatePresence } from "framer-motion";

import { IconButton } from "@/components/ui/icon-button";
import { api } from "@/lib/api";
import type { Repository, WorkspaceTask } from "@/types/api";

import { Panel, RowSkeleton, StatusPill } from "./shared";

const taskSchema = z.object({
  title: z.string().min(2).max(240),
  description: z.string().max(8000),
  priority: z.coerce.number().min(1).max(5)
});
type TaskForm = z.infer<typeof taskSchema>;

export function TaskPanel({ 
  repository,
  sendEvent,
  subscribe
}: { 
  repository: Repository | null;
  sendEvent?: (event: Record<string, any>) => void;
  subscribe?: (listener: (event: any) => void) => () => void;
}) {
  const queryClient = useQueryClient();
  const form = useForm<TaskForm>({
    resolver: zodResolver(taskSchema),
    defaultValues: { title: "", description: "", priority: 3 }
  });

  // Subscribe to real-time events to invalidate tasks
  useEffect(() => {
    if (!subscribe || !repository) return;
    return subscribe((event) => {
      if (event.type === "task.updated") {
        void queryClient.invalidateQueries({ queryKey: ["tasks", repository.id] });
      }
    });
  }, [subscribe, repository, queryClient]);

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
    onSuccess: (data) => {
      form.reset({ title: "", description: "", priority: 3 });
      void queryClient.invalidateQueries({ queryKey: ["tasks", repository?.id] });
      if (sendEvent) {
        sendEvent({ type: "task.updated", task_id: data.id });
      }
    }
  });

  const tasks = tasksQuery.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <Panel title="Tasks" icon={CheckCircle2}>
      <form
        className="grid gap-3"
        onSubmit={form.handleSubmit((value) => {
          if (!repository) return;
          createTaskMutation.mutate({ repository_id: repository.id, ...value });
        })}
      >
        <div className="grid gap-3 sm:grid-cols-[1fr_88px]">
          <input
            className="glass-input h-10 rounded-lg px-3 text-sm"
            placeholder="Task title"
            {...form.register("title")}
          />
          <input
            className="glass-input h-10 rounded-lg px-3 text-sm text-center"
            type="number"
            min={1}
            max={5}
            aria-label="Priority"
            {...form.register("priority")}
          />
        </div>
        <textarea
          className="glass-input min-h-[80px] resize-y rounded-lg px-3 py-2 text-sm"
          placeholder="Description"
          {...form.register("description")}
        />
        <IconButton icon={Plus} label="Add task" disabled={!repository || createTaskMutation.isPending} type="submit" />
      </form>
      
      <div className="mt-4 max-h-64 overflow-y-auto space-y-2 pr-1">
        {tasksQuery.isLoading ? <RowSkeleton count={3} /> : null}
        
        <AnimatePresence>
          {tasks.map((task) => (
            <motion.article 
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              key={task.id} 
              className="flex items-start justify-between gap-3 rounded-lg border border-border/50 bg-black/5 dark:bg-white/5 p-3 overflow-hidden"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">{task.title}</p>
                <p className="line-clamp-2 text-xs text-muted-foreground mt-1">{task.description || "No description"}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <StatusPill label={task.status.replace("_", " ")} tone={task.status === "done" ? "success" : "neutral"} />
                <span className="text-xs font-bold text-muted-foreground bg-black/5 dark:bg-white/10 px-2 py-0.5 rounded-full">P{task.priority}</span>
              </div>
            </motion.article>
          ))}
        </AnimatePresence>

        {tasksQuery.hasNextPage ? (
          <button className="h-10 w-full rounded-lg text-sm font-semibold text-accent hover:bg-accent/10 transition-colors" onClick={() => void tasksQuery.fetchNextPage()}>
            Load more
          </button>
        ) : null}
      </div>
    </Panel>
  );
}
