"use client";

import { AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatNumber } from "@/lib/utils";
import type { FailurePlanPreview } from "@/types/api";

export function GenerationPlanPreview({ preview }: { preview: FailurePlanPreview | null }) {
  if (!preview) {
    return (
      <section className="rounded-3xl border border-dashed border-border bg-card p-5 text-sm text-muted-foreground">
        Preview appears after a scenario and failure plan are loaded.
      </section>
    );
  }
  return (
    <section className="rounded-3xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Generation Plan Preview</h3>
          <p className="text-sm text-muted-foreground">Estimates are not guaranteed actual output; ground truth reconciles the real result after generation.</p>
        </div>
        <Badge>{preview.valid ? "Valid plan" : "Invalid plan"}</Badge>
      </div>
      {preview.errors.length ? (
        <div className="mt-3 rounded-2xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {preview.errors.join("; ")}
        </div>
      ) : null}
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <Summary label="Rows" value={formatNumber(preview.records)} />
        <Summary label="Estimated affected" value={formatNumber(preview.estimated_total_affected_entities)} />
        <Summary label="Overlap" value={preview.overlap_mode === "non_overlapping" ? "Non-overlapping" : "Allow overlap"} />
      </div>
      <div className="mt-4 space-y-2">
        {preview.failures.map((failure) => (
          <div key={`${failure.primitive_id}-${failure.target_table}`} className="rounded-2xl border border-border bg-background p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-semibold">{failure.display_name}</p>
                <p className="text-sm text-muted-foreground">{failure.target_table}{failure.target_column ? ` · ${failure.target_column}` : ""}</p>
              </div>
              <Badge>~{formatNumber(failure.estimated_affected)} affected</Badge>
            </div>
          </div>
        ))}
      </div>
      {preview.warnings.length ? (
        <div className="mt-4 flex gap-2 rounded-2xl border border-warning/30 bg-warning/5 p-3 text-sm text-muted-foreground">
          <AlertCircle className="h-4 w-4 shrink-0 text-warning" />
          <span>{preview.warnings.join(" ")}</span>
        </div>
      ) : null}
    </section>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-background p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-lg font-bold">{value}</p>
    </div>
  );
}
