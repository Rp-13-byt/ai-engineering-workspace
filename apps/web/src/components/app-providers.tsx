"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import { useWorkspaceStore } from "@/store/workspace-store";

export function AppProviders({ children }: { children: React.ReactNode }) {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30000,
            retry: 1,
            refetchOnWindowFocus: false
          }
        }
      }),
    []
  );
  const darkMode = useWorkspaceStore((state) => state.darkMode);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
  }, [darkMode]);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
