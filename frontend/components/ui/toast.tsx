"use client";

import { X } from "lucide-react";
import { useUiStore } from "@/store/ui-store";

export function ToastViewport() {
  const { toasts, dismissToast } = useUiStore();
  return (
    <div className="fixed bottom-5 right-5 z-50 flex w-96 max-w-[calc(100vw-2rem)] flex-col gap-3">
      {toasts.map((toast) => (
        <div key={toast.id} className="rounded-2xl border border-border bg-card p-4 shadow-glow">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold">{toast.title}</p>
              {toast.description ? <p className="mt-1 text-sm text-muted-foreground">{toast.description}</p> : null}
            </div>
            <button onClick={() => dismissToast(toast.id)} className="rounded-lg p-1 hover:bg-muted" aria-label="Dismiss toast">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
