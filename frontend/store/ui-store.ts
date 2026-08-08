"use client";

import { create } from "zustand";

type Toast = { id: string; title: string; description?: string };

type UiState = {
  toasts: Toast[];
  toast: (toast: Omit<Toast, "id">) => void;
  dismissToast: (id: string) => void;
};

export const useUiStore = create<UiState>((set) => ({
  toasts: [],
  toast: (toast) => {
    const id = crypto.randomUUID();
    set((state) => ({ toasts: [...state.toasts, { ...toast, id }] }));
    window.setTimeout(() => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })), 5000);
  },
  dismissToast: (id) => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })),
}));
