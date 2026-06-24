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
        "group rounded-2xl border bg-card p-4 text-left transition hover:-translate-y-0.5 hover:shadow-glow",
        selected ? "border-primary ring-4 ring-primary/10" : "border-border",
      )}
    >
      <div className="flex items-start gap-3">
        {icon ? <div className={cn("rounded-xl bg-muted p-2 text-muted-foreground", selected && "bg-primary text-primary-foreground")}>{icon}</div> : null}
        <div>
          <div className="font-semibold">{title}</div>
          {description ? <p className="mt-1 text-sm leading-5 text-muted-foreground">{description}</p> : null}
        </div>
      </div>
    </button>
  );
}
