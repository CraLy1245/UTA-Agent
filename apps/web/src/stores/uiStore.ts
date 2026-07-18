import { create } from "zustand";

type UiState = {
  conversationsCollapsed: boolean;
  statusCollapsed: boolean;
  toggleConversations: () => void;
  toggleStatus: () => void;
};

export const useUiStore = create<UiState>((set) => ({
  conversationsCollapsed: false,
  statusCollapsed: false,
  toggleConversations: () =>
    set((state) => ({ conversationsCollapsed: !state.conversationsCollapsed })),
  toggleStatus: () =>
    set((state) => ({ statusCollapsed: !state.statusCollapsed })),
}));
