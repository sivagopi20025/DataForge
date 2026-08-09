"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3, Download, FlaskConical, GitCompareArrows } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  compareScenarioBuilderRuns,
  createBenchmark,
  createEvaluation,
  getBenchmarkRun,
  getScenarioGroundTruthUrl,
  launchBenchmarkRun,
  runBenchmark,
  submitBenchmarkDetectorOutput,
  uploadBenchmarkDetectorOutput,
} from "@/lib/api";
import type { BenchmarkDefinition, BenchmarkRun, EvaluationResult, FailurePlan, ScenarioBuilderRunSummary } from "@/types/api";

function pct(value: number | null | undefined) {
  if (value === null || value === undefined) return "n/a";
  return `${Math.round(value * 100)}%`;
}

function parseDetectorJson(text: string): Record<string, unknown>[] {
  if (!text.trim()) return [];
  const payload = JSON.parse(text);
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.detections)) return payload.detections;
  throw new Error("Detector JSON must be an array or an object with detections[].");
}

export function BenchmarkingPanel({ runs }: { runs: ScenarioBuilderRunSummary[] }) {
  const runnable = useMemo(() => runs.filter((run) => run.scenario_id && run.failure_plan), [runs]);
  const [selectedRunId, setSelectedRunId] = useState<string>(runnable[0]?.id ?? "");
  const [compareLeft, setCompareLeft] = useState<string>(runnable[0]?.id ?? "");
  const [compareRight, setCompareRight] = useState<string>(runnable[1]?.id ?? runnable[0]?.id ?? "");
  const [detectorName, setDetectorName] = useState("customer-detector");
  const [detectorJson, setDetectorJson] = useState("[\n  {\n    \"evaluation_unit\": \"entity\",\n    \"evaluation_key\": {\"payment_id\": \"PAY123\"},\n    \"predicted_failure\": true,\n    \"predicted_failure_type\": \"duplicate_payment\",\n    \"confidence\": 0.95\n  }\n]");
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkDefinition | null>(null);
  const [benchmarkRun, setBenchmarkRun] = useState<BenchmarkRun | null>(null);
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedRun = runnable.find((run) => run.id === selectedRunId);

  useEffect(() => {
    if (!selectedRunId && runnable[0]?.id) setSelectedRunId(runnable[0].id);
    if (!compareLeft && runnable[0]?.id) setCompareLeft(runnable[0].id);
    if (!compareRight && runnable[1]?.id) setCompareRight(runnable[1].id);
  }, [runnable, selectedRunId, compareLeft, compareRight]);

  async function evaluate() {
    if (!selectedRun) return;
    setError(null);
    setStatus("Evaluating detector output...");
    try {
      const result = await createEvaluation({
        run_id: selectedRun.id,
        detector_name: detectorName,
        detections: parseDetectorJson(detectorJson),
        label_mapping: { duplicate_payment: "duplication" },
      });
      setEvaluation(result);
      setStatus("Detector evaluation completed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evaluation failed.");
    }
  }

  async function saveBenchmark() {
    if (!selectedRun?.scenario_id || !selectedRun.failure_plan) return;
    setError(null);
    setStatus("Creating benchmark definition...");
    try {
      const created = await createBenchmark({
        name: `${selectedRun.scenario_name ?? selectedRun.scenario_id} Benchmark`,
        description: "Created from Scenario Builder run for detector evaluation.",
        domain: selectedRun.domain,
        scenario_id: selectedRun.scenario_id,
        records: selectedRun.record_count,
        output_format: selectedRun.format as "csv" | "json" | "parquet",
        seed: selectedRun.failure_plan.seed,
        failure_plan: selectedRun.failure_plan as FailurePlan,
        thresholds: { minimum_recall: 0.9, minimum_precision: 0.8 },
      });
      setBenchmark(created);
      setStatus("Benchmark definition saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Benchmark creation failed.");
    }
  }

  async function evaluateAgainstBenchmark() {
    if (!selectedRun || !benchmark) return;
    setError(null);
    setStatus("Running benchmark evaluation...");
    try {
      const result = await runBenchmark(benchmark.id, {
        run_id: selectedRun.id,
        detector_name: detectorName,
        detections: parseDetectorJson(detectorJson),
        label_mapping: { duplicate_payment: "duplication" },
      });
      setEvaluation(result);
      setStatus(`Benchmark ${result.acceptance.status}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Benchmark run failed.");
    }
  }

  async function launchFreshBenchmark(seedMode: "fixed" | "random" = "fixed") {
    if (!benchmark) return;
    setError(null);
    setStatus("Launching fresh benchmark run...");
    try {
      const launched = await launchBenchmarkRun(benchmark.id, { seed: benchmark.seed, seed_mode: seedMode, detector_mode: "manual_upload" }, `ui-${benchmark.id}-${seedMode}-${Date.now()}`);
      setStatus(`Benchmark run queued: ${launched.benchmark_run_id}`);
      await pollBenchmarkRun(launched.benchmark_run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Benchmark launch failed.");
    }
  }

  async function pollBenchmarkRun(benchmarkRunId: string) {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      const current = await getBenchmarkRun(benchmarkRunId);
      setBenchmarkRun(current);
      if (["waiting_for_detector", "completed", "generation_failed", "evaluation_failed", "cancelled"].includes(current.status)) {
        setStatus(`Benchmark run status: ${current.status}`);
        return current;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 1200));
    }
    setStatus("Benchmark run is still processing. Check again from API or refresh later.");
    return null;
  }

  async function submitDetectorForBenchmarkRun() {
    if (!benchmarkRun) return;
    setError(null);
    setStatus("Submitting detector output and running evaluation...");
    try {
      const result = await submitBenchmarkDetectorOutput(benchmarkRun.id, {
        detector_name: detectorName,
        detector_output_format: "json",
        detections: parseDetectorJson(detectorJson),
        label_mapping: { duplicate_payment: "duplication" },
        replace_existing: benchmarkRun.status === "completed" || benchmarkRun.status === "evaluation_failed",
      });
      setBenchmarkRun(result);
      setStatus(`Benchmark run ${result.result ?? result.status}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Detector submission failed.");
    }
  }

  async function uploadDetectorFile(file: File | null) {
    if (!benchmarkRun || !file) return;
    setError(null);
    setStatus("Uploading detector file...");
    try {
      const result = await uploadBenchmarkDetectorOutput(benchmarkRun.id, file, detectorName, benchmarkRun.status === "completed" || benchmarkRun.status === "evaluation_failed");
      setBenchmarkRun(result);
      setStatus(`Benchmark run ${result.result ?? result.status}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Detector upload failed.");
    }
  }

  async function compareRuns() {
    if (!compareLeft || !compareRight || compareLeft === compareRight) return;
    setError(null);
    setStatus("Comparing scenario runs...");
    try {
      const result = await compareScenarioBuilderRuns(compareLeft, compareRight);
      setComparison(result.comparison);
      setStatus("Run comparison loaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run comparison failed.");
    }
  }

  return (
    <section className="rounded-3xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Benchmarking & Detector Evaluation</h3>
          <p className="text-sm text-muted-foreground">
            Export ground truth, compare scenario runs, and score customer detector output against known injected failures.
          </p>
        </div>
        <Badge className="w-fit">Batch 12</Badge>
      </div>

      {!runnable.length ? (
        <div className="mt-4 rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
          Generate a Scenario Builder run first to unlock benchmark exports and detector evaluation.
        </div>
      ) : (
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <div className="space-y-3 rounded-2xl border border-border bg-background p-4">
            <h4 className="font-semibold">Ground Truth Export</h4>
            <select aria-label="Select scenario run for ground truth export" value={selectedRunId} onChange={(event) => setSelectedRunId(event.target.value)} className="h-10 w-full rounded-xl border border-border bg-card px-3 text-sm">
              {runnable.map((run) => (
                <option key={run.id} value={run.id}>{run.scenario_name ?? run.scenario_id} · {run.id.slice(0, 8)}</option>
              ))}
            </select>
            <div className="flex flex-wrap gap-2">
              <a className="inline-flex h-11 items-center justify-center rounded-xl border border-border bg-card px-4 text-sm font-semibold transition hover:bg-muted" href={getScenarioGroundTruthUrl(selectedRunId, "jsonl")}><Download className="mr-2 h-4 w-4" /> JSONL</a>
              <a className="inline-flex h-11 items-center justify-center rounded-xl border border-border bg-card px-4 text-sm font-semibold transition hover:bg-muted" href={getScenarioGroundTruthUrl(selectedRunId, "csv")}><Download className="mr-2 h-4 w-4" /> CSV</a>
              <a className="inline-flex h-11 items-center justify-center rounded-xl border border-border bg-card px-4 text-sm font-semibold transition hover:bg-muted" href={getScenarioGroundTruthUrl(selectedRunId, "json")} target="_blank" rel="noreferrer"><Download className="mr-2 h-4 w-4" /> JSON</a>
            </div>
            <p className="text-xs text-muted-foreground">
              Contract: evaluation_unit + evaluation_key + predicted_failure + predicted_failure_type + confidence.
            </p>
          </div>

          <div className="space-y-3 rounded-2xl border border-border bg-background p-4">
            <h4 className="font-semibold">Side-by-side Run Comparison</h4>
            <div className="grid gap-2 sm:grid-cols-2">
              <select aria-label="Select left scenario run for comparison" value={compareLeft} onChange={(event) => setCompareLeft(event.target.value)} className="h-10 rounded-xl border border-border bg-card px-3 text-sm">
                {runnable.map((run) => <option key={run.id} value={run.id}>{run.id.slice(0, 8)} · seed {run.seed}</option>)}
              </select>
              <select aria-label="Select right scenario run for comparison" value={compareRight} onChange={(event) => setCompareRight(event.target.value)} className="h-10 rounded-xl border border-border bg-card px-3 text-sm">
                {runnable.map((run) => <option key={run.id} value={run.id}>{run.id.slice(0, 8)} · seed {run.seed}</option>)}
              </select>
            </div>
            <Button type="button" variant="secondary" onClick={compareRuns} disabled={compareLeft === compareRight}><GitCompareArrows className="mr-2 h-4 w-4" /> Compare Runs</Button>
            {comparison ? <pre className="max-h-48 overflow-auto rounded-xl bg-muted p-3 text-xs">{JSON.stringify(comparison, null, 2)}</pre> : null}
          </div>

          <div className="space-y-3 rounded-2xl border border-border bg-background p-4 xl:col-span-2">
            <h4 className="font-semibold">Customer Detector Output</h4>
            <input aria-label="Detector name" value={detectorName} onChange={(event) => setDetectorName(event.target.value)} className="h-10 w-full rounded-xl border border-border bg-card px-3 text-sm" placeholder="Detector name" />
            <textarea aria-label="Detector output JSON" value={detectorJson} onChange={(event) => setDetectorJson(event.target.value)} className="min-h-40 w-full rounded-xl border border-border bg-card p-3 font-mono text-xs" />
            <div className="flex flex-wrap gap-2">
              <Button type="button" onClick={evaluate}><FlaskConical className="mr-2 h-4 w-4" /> Evaluate Detector</Button>
              <Button type="button" variant="secondary" onClick={saveBenchmark}>Create Benchmark</Button>
              <Button type="button" variant="secondary" onClick={evaluateAgainstBenchmark} disabled={!benchmark}>Run Benchmark</Button>
              <Button type="button" variant="secondary" onClick={() => launchFreshBenchmark("fixed")} disabled={!benchmark}>Launch Fresh Run</Button>
              <Button type="button" variant="secondary" onClick={() => launchFreshBenchmark("random")} disabled={!benchmark}>Run Again · New Seed</Button>
            </div>
            {benchmarkRun ? (
              <div className="rounded-2xl border border-border p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold">Benchmark Run {benchmarkRun.id.slice(0, 8)}</p>
                    <p className="text-muted-foreground">{benchmarkRun.status} · dataset {benchmarkRun.dataset_status} · detector {benchmarkRun.detector_status}</p>
                  </div>
                  <Badge>{benchmarkRun.result ?? benchmarkRun.status}</Badge>
                </div>
                {benchmarkRun.status === "waiting_for_detector" || benchmarkRun.status === "completed" || benchmarkRun.status === "evaluation_failed" ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button type="button" variant="secondary" onClick={submitDetectorForBenchmarkRun}>Submit JSON Above</Button>
                    <label className="inline-flex h-11 cursor-pointer items-center justify-center rounded-xl border border-border bg-card px-4 text-sm font-semibold transition hover:bg-muted">
                      Upload JSON/JSONL/CSV
                      <input type="file" accept=".json,.jsonl,.csv,application/json,text/csv" className="hidden" onChange={(event) => uploadDetectorFile(event.target.files?.[0] ?? null)} />
                    </label>
                  </div>
                ) : null}
                {benchmarkRun.metrics ? (
                  <div className="mt-3 grid gap-2 sm:grid-cols-5">
                    <span><strong>Precision</strong><br />{pct(benchmarkRun.metrics.precision)}</span>
                    <span><strong>Recall</strong><br />{pct(benchmarkRun.metrics.recall)}</span>
                    <span><strong>F1</strong><br />{pct(benchmarkRun.metrics.f1)}</span>
                    <span><strong>FP</strong><br />{benchmarkRun.metrics.false_positive}</span>
                    <span><strong>FN</strong><br />{benchmarkRun.metrics.false_negative}</span>
                  </div>
                ) : null}
              </div>
            ) : null}
            {evaluation ? (
              <div className="grid gap-2 rounded-2xl border border-border p-3 text-sm sm:grid-cols-5">
                <span><strong>TP</strong><br />{evaluation.metrics.true_positive}</span>
                <span><strong>FP</strong><br />{evaluation.metrics.false_positive}</span>
                <span><strong>FN</strong><br />{evaluation.metrics.false_negative}</span>
                <span><strong>Precision</strong><br />{pct(evaluation.metrics.precision)}</span>
                <span><strong>Recall</strong><br />{pct(evaluation.metrics.recall)}</span>
                <span className="sm:col-span-5"><strong>Acceptance</strong> {evaluation.acceptance.status}</span>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {status ? <p className="mt-3 text-sm text-muted-foreground">{status}</p> : null}
      {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}
    </section>
  );
}
