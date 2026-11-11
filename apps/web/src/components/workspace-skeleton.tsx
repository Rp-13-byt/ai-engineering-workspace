export function WorkspaceSkeleton() {
  return (
    <main className="min-h-screen bg-background p-4 text-foreground">
      <div className="mx-auto grid max-w-7xl gap-4">
        <div className="h-14 animate-pulse border border-border bg-panel" />
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="h-[720px] animate-pulse border border-border bg-panel" />
          <div className="grid gap-4 md:grid-cols-2">
            <div className="h-80 animate-pulse border border-border bg-panel" />
            <div className="h-80 animate-pulse border border-border bg-panel" />
            <div className="h-80 animate-pulse border border-border bg-panel" />
            <div className="h-80 animate-pulse border border-border bg-panel" />
          </div>
        </div>
      </div>
    </main>
  );
}
