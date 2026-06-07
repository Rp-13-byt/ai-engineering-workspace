import { Search } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { motion, AnimatePresence } from "framer-motion";

import { IconButton } from "@/components/ui/icon-button";
import { api } from "@/lib/api";
import type { Repository, SearchResult } from "@/types/api";

import { ErrorStrip, Panel, RowSkeleton } from "./shared";

const searchSchema = z.object({
  query: z.string().min(2).max(2000)
});
type SearchForm = z.infer<typeof searchSchema>;

export function SemanticSearchPanel({ repository }: { repository: Repository | null }) {
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
        className="flex gap-3"
        onSubmit={form.handleSubmit((value) => {
          if (repository) searchMutation.mutate({ repository_id: repository.id, query: value.query, limit: 8 });
        })}
      >
        <input
          className="glass-input h-10 min-w-0 flex-1 rounded-lg px-4 text-sm"
          aria-label="Search query"
          placeholder="Ask a question about the code..."
          {...form.register("query")}
        />
        <IconButton icon={Search} label="Search" disabled={!repository || searchMutation.isPending} type="submit" />
      </form>
      
      <div className="mt-4 max-h-72 overflow-y-auto space-y-2 pr-1">
        {searchMutation.isPending ? <RowSkeleton count={3} /> : null}
        {searchMutation.error ? <ErrorStrip error={searchMutation.error} /> : null}
        
        <AnimatePresence>
          {results.map((result, idx) => (
            <motion.article 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
              key={`${result.path}-${result.start_line}`} 
              className="rounded-lg border border-border bg-black/5 dark:bg-white/5 p-3 overflow-hidden"
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="truncate text-sm font-semibold text-accent">{result.path}</p>
                <span className="text-xs font-bold text-muted-foreground bg-black/5 dark:bg-white/10 px-2 py-0.5 rounded-full">{Math.round(result.score * 100)}%</span>
              </div>
              <pre className="max-h-32 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-muted-foreground font-mono">
                {result.content}
              </pre>
            </motion.article>
          ))}
        </AnimatePresence>
      </div>
    </Panel>
  );
}
