import { Bug, FileText, GitPullRequest, TestTube2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { motion, AnimatePresence } from "framer-motion";

import { IconButton } from "@/components/ui/icon-button";
import { api } from "@/lib/api";
import type { PullRequestDraft, Repository } from "@/types/api";

import { LoaderLine, Panel } from "./shared";

const generationSchema = z.object({
  target: z.string().min(2).max(500)
});
type GenerationForm = z.infer<typeof generationSchema>;

export function GenerationPanel({ repository }: { repository: Repository | null }) {
  const form = useForm<GenerationForm>({
    resolver: zodResolver(generationSchema),
    defaultValues: { target: "authentication and repository import" }
  });
  
  const [draft, setDraft] = useState<PullRequestDraft | null>(null);
  const [output, setOutput] = useState("");
  
  const docsMutation = useMutation({
    mutationFn: api.generateDocs,
    onSuccess: (response) => { setOutput(response.markdown); setDraft(null); }
  });
  const testsMutation = useMutation({
    mutationFn: api.generateTests,
    onSuccess: (response) => { setOutput(response.test_plan); setDraft(null); }
  });
  const bugsMutation = useMutation({
    mutationFn: api.detectBugs,
    onSuccess: (response) => { 
      setOutput(response.findings.map((finding) => `${finding.severity}: ${finding.path} - ${finding.message}`).join("\n") || "No findings.");
      setDraft(null);
    }
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
    <Panel title="AI Generation" icon={GitPullRequest}>
      <form className="grid gap-3" onSubmit={run}>
        <input 
          className="glass-input h-10 rounded-lg px-4 text-sm" 
          placeholder="Target (e.g. filename or feature)"
          {...form.register("target")} 
        />
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
      
      {pending ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <LoaderLine label="Generating..." />
        </motion.div>
      ) : null}
      
      <AnimatePresence>
        {draft ? (
          <motion.div 
            initial={{ opacity: 0, y: -10 }} 
            animate={{ opacity: 1, y: 0 }} 
            className="mt-4 rounded-lg border border-success/30 bg-success/5 p-3"
          >
            <p className="truncate text-sm font-bold text-success">{draft.title}</p>
            <p className="mt-1 truncate text-xs font-mono text-success/80">{draft.branch_name}</p>
          </motion.div>
        ) : null}
      </AnimatePresence>
      
      <div className="mt-4 relative group">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent to-background/10 pointer-events-none rounded-lg" />
        <pre className="max-h-64 overflow-auto rounded-lg border border-border/50 bg-black/5 dark:bg-white/5 p-4 text-[11px] leading-5 text-muted-foreground font-mono">
          {output || "Generated output appears here."}
        </pre>
      </div>
    </Panel>
  );
}
