"use client";

import { Badge } from "@/components/ui/badge";
import { formatNumber } from "@/lib/utils";
import type { GroundTruthRow } from "@/types/api";
import { EvidenceRenderer } from "./evidence-renderer";

export function GroundTruthSummary({ rows }: { rows: GroundTruthRow[] }) {
  if (!rows.length) return null;
  return (
    <section className="rounded-3xl border border-border bg-card p-5">
      <div>
        <h3 className="text-lg font-semibold">Ground Truth + Detection</h3>
        <p className="text-sm text-muted-foreground">Requested / Expected / Selected / Actual / Detected are separated so this can become a benchmark later.</p>
      </div>
      <div className="mt-4 space-y-3">
        {rows.map((row) => (
          <details key={row.primitive_id} className="rounded-2xl border border-border bg-background p-4" open>
            <summary className="cursor-pointer list-none">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-semibold">{row.display_name}</p>
                  <p className="text-sm text-muted-foreground">{row.target.table}{row.target.column ? ` · ${row.target.column}` : ""}</p>
                </div>
                <Badge>{row.reconciliation_status}</Badge>
              </div>
            </summary>
            <div className="mt-4 grid gap-3 sm:grid-cols-5">
              <Metric label="Expected" value={row.expected_count} />
              <Metric label="Selected" value={row.selected_count} />
              <Metric label="Actual" value={row.actual_count} />
              <Metric label="Detected" value={row.detected_count} />
              <Metric label="Detection" value={`${Math.round(row.detection_rate * 100)}%`} />
            </div>
            <div className="mt-4 rounded-2xl bg-muted/40 p-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Affected entities</p>
              <p className="mt-1 text-sm text-muted-foreground">{formatNumber(row.affected_entities.length)} examples retained in the report. Showing compact evidence below.</p>
            </div>
            <div className="mt-3"><EvidenceRenderer row={row} /></div>
          </details>
        ))}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-border p-3">
      <p className="text-[0.65rem] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-1 font-bold">{typeof value === "number" ? formatNumber(value) : value}</p>
    </div>
  );
}
