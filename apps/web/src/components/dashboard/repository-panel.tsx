import { Plus } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { motion, AnimatePresence } from "framer-motion";

import { IconButton } from "@/components/ui/icon-button";
import { cn } from "@/lib/utils";
import type { Repository } from "@/types/api";

import { ErrorStrip, RowSkeleton, StatusPill } from "./shared";

const importSchema = z.object({
  owner: z.string().min(1).max(120),
  name: z.string().min(1).max(160)
});
type ImportForm = z.infer<typeof importSchema>;

export function RepositoryPanel({
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

  const statusTone = (status: Repository["indexing_status"]) => {
    if (status === "indexed") return "success";
    if (status === "failed") return "danger";
    if (status === "indexing") return "warning";
    return "neutral";
  };

  return (
    <aside className="glass-panel flex flex-col min-h-[calc(100vh-7rem)] rounded-xl overflow-hidden">
      <div className="border-b border-border/50 bg-black/5 dark:bg-white/5 p-4">
        <h2 className="text-sm font-semibold tracking-tight">Repositories</h2>
      </div>
      <form
        className="grid gap-3 border-b border-border/50 p-4"
        onSubmit={form.handleSubmit((value) => onImport(value))}
      >
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs font-medium text-muted-foreground flex flex-col gap-1.5">
            Owner
            <input className="glass-input h-10 w-full rounded-lg px-3 text-sm text-foreground" {...form.register("owner")} />
          </label>
          <label className="text-xs font-medium text-muted-foreground flex flex-col gap-1.5">
            Repo
            <input className="glass-input h-10 w-full rounded-lg px-3 text-sm text-foreground" {...form.register("name")} />
          </label>
        </div>
        <IconButton icon={Plus} label={importing ? "Importing" : "Import"} disabled={importing} type="submit" className="w-full justify-center bg-accent text-accent-foreground hover:bg-accent/90" />
      </form>
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {loading ? <div className="p-2"><RowSkeleton count={4} /></div> : null}
        {error ? <div className="p-2"><ErrorStrip error={error} /></div> : null}
        <AnimatePresence>
          {repositories.map((repository) => (
            <motion.button
              layout
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              key={repository.id}
              className={cn(
                "flex w-full items-center justify-between gap-3 rounded-lg px-4 py-3 text-left transition-all duration-200",
                selectedRepositoryId === repository.id 
                  ? "bg-accent/10 shadow-[inset_0_0_0_1px_hsl(var(--accent)/0.2)]" 
                  : "hover:bg-black/5 dark:hover:bg-white/5"
              )}
              onClick={() => onSelect(repository.id)}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-foreground">
                  {repository.owner}/{repository.name}
                </span>
                <span className="block truncate text-xs font-medium text-muted-foreground mt-0.5">{repository.default_branch}</span>
              </span>
              <StatusPill label={repository.indexing_status} tone={statusTone(repository.indexing_status)} />
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </aside>
  );
}
