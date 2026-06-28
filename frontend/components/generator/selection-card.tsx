import type React from "react";
import { cn } from "@/lib/utils";

export function SelectionCard({
  selected,
  title,
  description,
  icon,
  onClick,
}: {
  selected: boolean;
  title: string;
  description?: string;
  icon?: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "timed-hover-group relative rounded-xl border bg-card p-3 text-left transition hover:shadow-glow",
        selected ? "border-primary ring-4 ring-primary/10" : "border-border",
      )}
    >
      <div className="flex items-start gap-2.5">
        {icon ? <div className={cn("rounded-lg bg-muted p-1.5 text-muted-foreground", selected && "bg-primary text-primary-foreground")}>{icon}</div> : null}
        <div className="relative min-w-0">
          <div className="text-sm font-semibold">{title}</div>
          {description ? (
            <p className="timed-hover-popup pointer-events-none absolute left-0 top-full z-30 mt-2 w-max max-w-64 rounded-xl border border-border bg-popover px-3 py-2 text-xs leading-5 text-popover-foreground shadow-lg">
              {description}
            </p>
          ) : null}
        </div>
      </div>
    </button>
  );
}
