"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertCircle, Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FailurePlanEditor } from "@/components/scenarios/failure-plan-editor";
import { BenchmarkingPanel } from "@/components/scenarios/benchmarking-panel";
import { GenerationPlanPreview } from "@/components/scenarios/generation-plan-preview";
import { GroundTruthSummary } from "@/components/scenarios/ground-truth-summary";
import { RequiredTablesPanel } from "@/components/scenarios/required-tables-panel";
import { SavedScenarioTemplates } from "@/components/scenarios/saved-scenario-templates";
import { ScenarioBrowser } from "@/components/scenarios/scenario-browser";
import { ScenarioOverview } from "@/components/scenarios/scenario-overview";
import { ScenarioRunHistory } from "@/components/scenarios/scenario-run-history";
import { createScenarioTemplate, deleteScenarioTemplate, generateScenarioBuilderDataset, getRun, getScenarioBuilderConfiguration, getScenarioBuilderRuns, getScenarioLibraryItems, getScenarioTemplates, previewFailurePlan, waitForJob } from "@/lib/api";
import type { Domain, FailurePlan, FailurePlanPreview, GroundTruthRow, OutputFormat, ScenarioBuilderConfiguration, ScenarioBuilderGeneratePayload, ScenarioBuilderRunSummary, ScenarioLibrarySummary, ScenarioTemplate } from "@/types/api";

export default function ScenarioBuilderPage() {
  const [domain, setDomain] = useState<"all" | Domain>("all");
  const [scenarios, setScenarios] = useState<ScenarioLibrarySummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [config, setConfig] = useState<ScenarioBuilderConfiguration | null>(null);
  const [records, setRecords] = useState(10000);
  const [format, setFormat] = useState<"csv" | "json" | "parquet">("csv");
  const [seed, setSeed] = useState(42);
  const [severity, setSeverity] = useState("medium");
  const [advanced, setAdvanced] = useState(false);
  const [plan, setPlan] = useState<FailurePlan | null>(null);
  const [preview, setPreview] = useState<FailurePlanPreview | null>(null);
  const [groundTruth, setGroundTruth] = useState<GroundTruthRow[]>([]);
  const [templates, setTemplates] = useState<ScenarioTemplate[]>([]);
  const [runs, setRuns] = useState<ScenarioBuilderRunSummary[]>([]);
  const [pendingRestore, setPendingRestore] = useState<ScenarioBuilderGeneratePayload | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshReusableState() {
    const [templateData, runData] = await Promise.all([getScenarioTemplates(), getScenarioBuilderRuns()]);
    setTemplates(templateData.items);
    setRuns(runData.items);
  }

  useEffect(() => {
    refreshReusableState().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setError(null);
    getScenarioLibraryItems({
      domain: domain === "all" ? undefined : domain,
      v1_ready: true,
      execution_status: "executable",
      limit: 100,
    })
      .then((data) => {
        setScenarios(data.items);
        if (!selectedId || !data.items.some((item) => item.scenario_id === selectedId)) {
          setSelectedId(data.items[0]?.scenario_id ?? null);
        }
      })
      .catch((err) => setError(err.message));
  }, [domain]);

  useEffect(() => {
    if (!selectedId) return;
    setError(null);
    setConfig(null);
    setPreview(null);
    setGroundTruth([]);
    getScenarioBuilderConfiguration(selectedId, records)
      .then((data) => {
        setConfig(data);
        if (pendingRestore?.scenario_id === data.scenario.scenario_id) {
          setPlan(pendingRestore.failure_plan);
          setPendingRestore(null);
        } else {
          setSeverity(data.scenario.severity);
          setPlan({
            scenario_id: data.default_failure_plan.scenario_id,
            seed,
            overlap_mode: data.default_failure_plan.overlap_mode,
            failures: data.default_failure_plan.failures.map((failure) => ({
              primitive_id: failure.primitive_id,
              mode: failure.mode,
              value: failure.value,
              table: failure.target_table,
              column: failure.target_column,
            })),
          });
        }
      })
      .catch((err) => setError(err.message));
  }, [selectedId]);

  useEffect(() => {
    if (!config || !plan) return;
    const nextPlan = { ...plan, seed };
    const timer = window.setTimeout(() => {
      previewFailurePlan(config.scenario.scenario_id, records, nextPlan)
        .then(setPreview)
        .catch((err) => setError(err.message));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [config, plan, records, seed]);

  const selectedScenario = useMemo(() => scenarios.find((item) => item.scenario_id === selectedId), [scenarios, selectedId]);

  async function generate() {
    if (!config || !plan || !preview?.valid) return;
    setError(null);
    setGroundTruth([]);
    setStatus("Starting scenario generation...");
    const job = await generateScenarioBuilderDataset({
      scenario_id: config.scenario.scenario_id,
      records,
      output_format: format,
      seed,
      severity,
      failure_plan: { ...plan, seed },
    });
    setStatus("Generating data, injecting failures, validating evidence...");
    const completed = await waitForJob(job.job_id, 180000);
    if (!completed.run_id) throw new Error("Generation completed without a run id.");
    const run = await getRun(completed.run_id);
    const report = run.scenario_reports["scenario_execution_report.json"] as { ground_truth?: GroundTruthRow[] } | undefined;
    setGroundTruth(report?.ground_truth ?? []);
    setStatus(`Scenario generated. Run ID: ${completed.run_id}`);
    refreshReusableState().catch(() => undefined);
  }

  async function saveTemplate(name: string, seedBehavior: "fixed_seed" | "new_seed_each_run") {
    if (!config || !plan) return;
    const template = await createScenarioTemplate({
      name,
      scenario_id: config.scenario.scenario_id,
      records,
      output_format: format,
      severity,
      seed_behavior: seedBehavior,
      failure_plan: { ...plan, seed },
    });
    setTemplates((current) => [template, ...current.filter((item) => item.id !== template.id)]);
    setStatus(`Saved template: ${template.name}`);
  }

  async function removeTemplate(templateId: string) {
    await deleteScenarioTemplate(templateId);
    setTemplates((current) => current.filter((item) => item.id !== templateId));
  }

  function restoreRequest(request: ScenarioBuilderGeneratePayload) {
    setDomain("all");
    setSelectedId(request.scenario_id);
    setRecords(request.records);
    setFormat(request.output_format);
    setSeed(request.seed);
    setSeverity(request.severity);
    setPendingRestore(request);
    setPlan(request.failure_plan);
    setStatus("Configuration restored. Review or modify it, then click Generate.");
  }

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <Card>
        <CardHeader>
          <Badge className="w-fit">Scenario Builder · Batch 11</Badge>
          <CardTitle className="text-3xl">Build Failure-Injected Test Datasets</CardTitle>
          <CardDescription>
            Choose a V1-ready scenario, preview required tables and failure ground truth, then generate a benchmarkable dataset.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[430px_minmax(0,1fr)]">
        <ScenarioBrowser scenarios={scenarios} selectedId={selectedId ?? undefined} domain={domain} onDomainChange={setDomain} onSelect={setSelectedId} />

        <main className="min-w-0 space-y-5">
          {error ? (
            <div className="flex gap-2 rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          ) : null}

          {selectedScenario && !config ? (
            <section className="rounded-3xl border border-border bg-card p-8 text-muted-foreground">Loading scenario configuration...</section>
          ) : null}

          {config && plan ? (
            <>
              <ScenarioOverview config={config} />

              <section className="rounded-3xl border border-border bg-card p-5">
                <h3 className="text-lg font-semibold">Simple Setup</h3>
                <p className="text-sm text-muted-foreground">You can accept these defaults and generate immediately.</p>
                <div className="mt-4 grid gap-3 md:grid-cols-4">
                  <label className="text-sm">
                    <span className="text-muted-foreground">Records</span>
                    <input type="number" min={0} max={500000} value={records} onChange={(event) => setRecords(Number(event.target.value))} className="mt-1 h-10 w-full rounded-xl border border-border bg-card px-3" />
                  </label>
                  <label className="text-sm">
                    <span className="text-muted-foreground">Format</span>
                    <select value={format} onChange={(event) => setFormat(event.target.value as OutputFormat as "csv" | "json" | "parquet")} className="mt-1 h-10 w-full rounded-xl border border-border bg-card px-3">
                      <option value="csv">CSV</option>
                      <option value="json">JSON</option>
                      <option value="parquet">Parquet</option>
                    </select>
                  </label>
                  <label className="text-sm">
                    <span className="text-muted-foreground">Seed</span>
                    <input type="number" min={0} value={seed} onChange={(event) => setSeed(Number(event.target.value))} className="mt-1 h-10 w-full rounded-xl border border-border bg-card px-3" />
                  </label>
                  <label className="text-sm">
                    <span className="text-muted-foreground">Severity</span>
                    <select value={severity} onChange={(event) => setSeverity(event.target.value)} className="mt-1 h-10 w-full rounded-xl border border-border bg-card px-3">
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="stress">Stress</option>
                    </select>
                  </label>
                </div>
              </section>

              <RequiredTablesPanel config={config} />
              <FailurePlanEditor config={config} plan={plan} advanced={advanced} onAdvancedChange={setAdvanced} onPlanChange={setPlan} />
              <GenerationPlanPreview preview={preview} />
              <SavedScenarioTemplates templates={templates} config={config} plan={plan} records={records} format={format} severity={severity} onSave={saveTemplate} onDelete={removeTemplate} onLoad={restoreRequest} />

              <div className="flex flex-wrap items-center gap-3">
                <Button type="button" onClick={generate} disabled={!preview?.valid}><Play className="mr-2 h-4 w-4" /> Generate Scenario Dataset</Button>
                {status ? <p className="text-sm text-muted-foreground">{status}</p> : null}
                {status?.includes("Run ID") ? <Link href="/history" className="text-sm font-semibold text-primary">Open Run History</Link> : null}
              </div>

              <GroundTruthSummary rows={groundTruth} />
              <ScenarioRunHistory runs={runs} onRerun={restoreRequest} />
              <BenchmarkingPanel runs={runs} />
            </>
          ) : null}

          {!selectedScenario && !error ? (
            <section className="rounded-3xl border border-border bg-card p-8 text-muted-foreground">
              No executable V1-ready scenarios found for this filter.
            </section>
          ) : null}
        </main>
      </div>
    </div>
  );
}
