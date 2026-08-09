"use client";

import { Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { FailurePlan, ScenarioBuilderConfiguration, ScenarioBuilderGeneratePayload, ScenarioTemplate } from "@/types/api";

export function SavedScenarioTemplates({
  templates,
  config,
  plan,
  records,
  format,
  severity,
  onSave,
  onDelete,
  onLoad,
}: {
  templates: ScenarioTemplate[];
  config: ScenarioBuilderConfiguration | null;
  plan: FailurePlan | null;
  records: number;
  format: "csv" | "json" | "parquet";
  severity: string;
  onSave: (name: string, seedBehavior: "fixed_seed" | "new_seed_each_run") => void;
  onDelete: (templateId: string) => void;
  onLoad: (request: ScenarioBuilderGeneratePayload) => void;
}) {
  return (
    <section className="rounded-3xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Saved Scenario Plans</h3>
          <p className="text-sm text-muted-foreground">Save reusable failure plans without storing generated data.</p>
        </div>
        <Button
          type="button"
          variant="secondary"
          disabled={!config || !plan}
          onClick={() => {
            const name = window.prompt("Template name", config ? `${config.scenario.scenario_name} Plan` : "Scenario Plan");
            if (name) onSave(name, "fixed_seed");
          }}
        >
          <Save className="mr-2 h-4 w-4" /> Save current
        </Button>
      </div>
      <div className="mt-4 space-y-2">
        {templates.length ? templates.map((template) => (
          <div key={template.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-background p-4">
            <div>
              <p className="font-semibold">{template.name}</p>
              <p className="text-sm text-muted-foreground">{template.scenario_id} · {template.failure_count} failures · {template.records} rows</p>
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge>{template.domain}</Badge>
                <Badge>{template.seed_behavior}</Badge>
                <Badge>{template.compatibility.valid ? "Ready" : "Needs updating"}</Badge>
              </div>
            </div>
            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={() => onLoad({
                scenario_id: template.scenario_id,
                records: template.records,
                output_format: template.output_format,
                seed: template.failure_plan.seed,
                severity: template.severity,
                failure_plan: template.failure_plan,
              })}>Load</Button>
              <Button type="button" variant="secondary" aria-label={`Delete template ${template.name}`} onClick={() => onDelete(template.id)}><Trash2 className="h-4 w-4" /></Button>
            </div>
          </div>
        )) : (
          <div className="rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
            No saved templates yet. Configure a scenario and click “Save current”.
          </div>
        )}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">Current setup: {records} rows · {format.toUpperCase()} · {severity}</p>
    </section>
  );
}
