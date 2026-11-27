"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ChangeAnalysisRequest } from "@/types/api";

export const changeLensKeys = {
  all: ["changelens"] as const,
  listByRepo: (repositoryId: string | null) => ["changelens", "repo", repositoryId] as const,
  detail: (analysisId: string | null) => ["changelens", "detail", analysisId] as const
};

export function useChangeAnalyses(repositoryId: string | null, limit = 20, offset = 0) {
  return useQuery({
    queryKey: changeLensKeys.listByRepo(repositoryId),
    queryFn: () => {
      if (!repositoryId) {
        return Promise.resolve({ items: [], total: 0 });
      }
      return api.listChangeAnalyses(repositoryId, limit, offset);
    },
    enabled: Boolean(repositoryId)
  });
}

export function useChangeAnalysis(analysisId: string | null) {
  return useQuery({
    queryKey: changeLensKeys.detail(analysisId),
    queryFn: () => {
      if (!analysisId) {
        throw new Error("analysisId is required");
      }
      return api.getChangeAnalysis(analysisId);
    },
    enabled: Boolean(analysisId)
  });
}

export function useAnalyzeChangeMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: ChangeAnalysisRequest) => api.analyzeChange(payload),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({
        queryKey: changeLensKeys.listByRepo(created.repository_id)
      });
    }
  });
}

export function useDeleteChangeAnalysisMutation(repositoryId: string | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (analysisId: string) => api.deleteChangeAnalysis(analysisId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: changeLensKeys.listByRepo(repositoryId)
      });
    }
  });
}
