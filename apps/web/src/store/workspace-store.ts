import { create } from "zustand";

type WorkspaceState = {
  selectedRepositoryId: string | null;
  conversationId: string | null;
  darkMode: boolean;
  setSelectedRepositoryId: (repositoryId: string | null) => void;
  setConversationId: (conversationId: string | null) => void;
  toggleDarkMode: () => void;
};

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  selectedRepositoryId: null,
  conversationId: null,
  darkMode: true,
  setSelectedRepositoryId: (selectedRepositoryId) => set({ selectedRepositoryId }),
  setConversationId: (conversationId) => set({ conversationId }),
  toggleDarkMode: () => set((state) => ({ darkMode: !state.darkMode }))
}));
