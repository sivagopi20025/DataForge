"use client";

import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatNumber } from "@/lib/utils";
import type { ScenarioBuilderGeneratePayload, ScenarioBuilderRunSummary } from "@/types/api";

export function ScenarioRunHistory({
  runs,
  onRerun,
}: {
  runs: ScenarioBuilderRunSummary[];
  onRerun: (request: ScenarioBuilderGeneratePayload) => void;
}) {
  return (
    <section className="rounded-3xl border border-border bg-card p-5">
      <div>
        <h3 className="text-lg font-semibold">Recent Scenario Builder Runs</h3>
        <p className="text-sm text-muted-foreground">Compact history with failure-plan snapshots and detection metrics.</p>
      </div>
      <div className="mt-4 space-y-2">
        {runs.length ? runs.slice(0, 8).map((run) => (
          <div key={run.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-background p-4">
            <div>
              <p className="font-semibold">{run.scenario_name ?? run.scenario_id}</p>
              <p className="text-sm text-muted-foreground">{run.domain} · {formatNumber(run.record_count)} rows · seed {run.seed ?? "n/a"}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge>{run.ground_truth_summary.failure_count} failures</Badge>
                <Badge>{formatNumber(run.ground_truth_summary.actual_count)} actual</Badge>
                <Badge>{formatNumber(run.ground_truth_summary.detected_count)} detected</Badge>
                <Badge>{Math.round(run.ground_truth_summary.detection_rate * 100)}% detected</Badge>
              </div>
            </div>
            <Button type="button" variant="secondary" onClick={() => run.failure_plan && onRerun({
              scenario_id: run.scenario_id ?? "",
              records: run.record_count,
              output_format: run.format as "csv" | "json" | "parquet",
              seed: run.failure_plan.seed,
              severity: run.scenario_severity ?? "medium",
              failure_plan: run.failure_plan,
            })} disabled={!run.failure_plan}>
              <RotateCcw className="mr-2 h-4 w-4" /> Re-run
            </Button>
          </div>
        )) : (
          <div className="rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
            No Scenario Builder runs yet. Generate one to see reproducibility metadata here.
          </div>
        )}
      </div>
    </section>
  );
}
