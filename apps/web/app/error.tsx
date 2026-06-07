"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";

import { IconButton } from "@/components/ui/icon-button";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-6 text-foreground">
      <section className="w-full max-w-md border border-border bg-panel p-6">
        <div className="mb-4 flex items-center gap-3">
          <AlertTriangle aria-hidden className="h-5 w-5 text-danger" />
          <h1 className="text-lg font-semibold">Workspace unavailable</h1>
        </div>
        <p className="mb-5 text-sm text-muted">The interface hit an unexpected error.</p>
        <IconButton icon={RotateCcw} label="Retry" onClick={reset} />
      </section>
    </main>
  );
}
