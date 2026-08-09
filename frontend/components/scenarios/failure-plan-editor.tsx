"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { FailurePlan, ScenarioBuilderConfiguration } from "@/types/api";

export function FailurePlanEditor({
  config,
  plan,
  advanced,
  onAdvancedChange,
  onPlanChange,
}: {
  config: ScenarioBuilderConfiguration;
  plan: FailurePlan;
  advanced: boolean;
  onAdvancedChange: (value: boolean) => void;
  onPlanChange: (plan: FailurePlan) => void;
}) {
  const supported = config.compatible_primitives.filter((item) => item.supported);

  function updateFailure(index: number, patch: Partial<FailurePlan["failures"][number]>) {
    onPlanChange({ ...plan, failures: plan.failures.map((failure, current) => (current === index ? { ...failure, ...patch } : failure)) });
  }

  function addFailure() {
    const used = new Set(plan.failures.map((failure) => failure.primitive_id));
    const option = supported.find((item) => !used.has(item.primitive_id)) ?? supported[0];
    if (!option) return;
    onPlanChange({
      ...plan,
      failures: [
        ...plan.failures,
        {
          primitive_id: option.primitive_id,
          mode: "percentage",
          value: option.default_value,
          table: option.target_table,
          column: option.target_column,
        },
      ],
    });
  }

  function removeFailure(index: number) {
    onPlanChange({ ...plan, failures: plan.failures.filter((_, current) => current !== index) });
  }

  return (
    <section className="rounded-3xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Failure Configuration</h3>
          <p className="text-sm text-muted-foreground">Simple mode lets you change intensity. Advanced mode adds compatible failure primitives.</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={advanced} onChange={(event) => onAdvancedChange(event.target.checked)} />
          Advanced mode
        </label>
      </div>

      <div className="mt-4 space-y-3">
        {plan.failures.map((failure, index) => {
          const option = supported.find((item) => item.primitive_id === failure.primitive_id);
          return (
            <div key={`${failure.primitive_id}-${index}`} className="rounded-2xl border border-border bg-background p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="font-semibold">{option?.display_name ?? failure.primitive_id}</p>
                  <p className="text-sm text-muted-foreground">Target: {failure.table ?? option?.target_table} {failure.column ? `· ${failure.column}` : ""}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge>{option?.validator ?? "Validator"}</Badge>
                  {advanced && plan.failures.length > 1 ? (
                    <Button type="button" variant="secondary" onClick={() => removeFailure(index)}><Trash2 className="h-4 w-4" /></Button>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                {advanced ? (
                  <label className="text-sm">
                    <span className="text-muted-foreground">Failure</span>
                    <select value={failure.primitive_id} onChange={(event) => {
                      const next = supported.find((item) => item.primitive_id === event.target.value);
                      updateFailure(index, { primitive_id: event.target.value, table: next?.target_table, column: next?.target_column });
                    }} className="mt-1 h-10 w-full rounded-xl border border-border bg-card px-3">
                      {supported.map((item) => <option key={item.primitive_id} value={item.primitive_id}>{item.display_name}</option>)}
                    </select>
                  </label>
                ) : null}
                <label className="text-sm">
                  <span className="text-muted-foreground">Mode</span>
                  <select value={failure.mode} onChange={(event) => updateFailure(index, { mode: event.target.value as "percentage" | "exact_count", value: event.target.value === "percentage" ? 0.03 : 10 })} className="mt-1 h-10 w-full rounded-xl border border-border bg-card px-3">
                    <option value="percentage">Percentage</option>
                    <option value="exact_count">Exact count</option>
                  </select>
                </label>
                <label className="text-sm">
                  <span className="text-muted-foreground">{failure.mode === "percentage" ? "Rate" : "Count"}</span>
                  <input
                    type="number"
                    min={failure.mode === "percentage" ? 0.001 : 1}
                    max={failure.mode === "percentage" ? 0.1 : undefined}
                    step={failure.mode === "percentage" ? 0.001 : 1}
                    value={failure.value}
                    onChange={(event) => updateFailure(index, { value: Number(event.target.value) })}
                    className="mt-1 h-10 w-full rounded-xl border border-border bg-card px-3"
                  />
                </label>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <label className="text-sm">
          <span className="text-muted-foreground">Overlap behavior</span>
          <select value={plan.overlap_mode} onChange={(event) => onPlanChange({ ...plan, overlap_mode: event.target.value as "non_overlapping" | "allow_overlap" })} className="mt-1 h-10 w-full rounded-xl border border-border bg-card px-3">
            <option value="non_overlapping">Non-overlapping</option>
            <option value="allow_overlap">Allow overlap</option>
          </select>
        </label>
        {advanced ? <Button type="button" variant="secondary" onClick={addFailure}><Plus className="mr-2 h-4 w-4" /> Add failure</Button> : null}
      </div>
    </section>
  );
}
