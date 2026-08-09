"use client";

import type { GroundTruthRow } from "@/types/api";

export function EvidenceRenderer({ row }: { row: GroundTruthRow }) {
  const primitive = row.primitive_id;
  const evidence = row.evidence ?? {};
  if (primitive.includes("duplicate") || primitive.includes("retry")) return <KeyValueEvidence title="Duplicate / Retry Evidence" evidence={evidence} preferred={["duplicate_key_count", "retry_baseline_count", "duplicate_sequence_key_count", "table", "key_columns", "detectors"]} />;
  if (primitive.includes("threshold") || primitive.includes("negative") || primitive.includes("capacity")) return <ListEvidence title="Threshold Evidence" evidence={evidence} listKeys={["violations"]} preferred={["table", "columns", "threshold", "operator"]} />;
  if (primitive.includes("timeout") || primitive.includes("timestamp") || primitive.includes("stale")) return <ListEvidence title="SLA / Time Evidence" evidence={evidence} listKeys={["sla_violations", "delays", "timestamp_violations"]} preferred={["table", "columns", "threshold"]} />;
  if (primitive.includes("state")) return <ListEvidence title="State Transition Evidence" evidence={evidence} listKeys={["transitions"]} preferred={["table", "status_column"]} />;
  if (primitive.includes("cross_table")) return <ListEvidence title="Cross-table Comparison" evidence={evidence} listKeys={["comparisons"]} preferred={["baseline_table"]} />;
  if (primitive.includes("aggregate")) return <ListEvidence title="Aggregate Balance Evidence" evidence={evidence} listKeys={["groups"]} preferred={["baseline_table"]} />;
  if (primitive.includes("volume")) return <ListEvidence title="Volume Evidence" evidence={evidence} listKeys={["anomalies", "windows"]} preferred={["baseline_method", "anomaly_type"]} />;
  if (primitive.includes("policy")) return <ListEvidence title="Policy Evidence" evidence={evidence} listKeys={["violations"]} preferred={["policy_id", "policy_name", "rule"]} />;
  if (primitive.includes("availability")) return <ListEvidence title="Availability Evidence" evidence={evidence} listKeys={["outages", "violations"]} preferred={["table", "status_column"]} />;
  if (primitive.includes("geographic")) return <ListEvidence title="Geographic Evidence" evidence={evidence} listKeys={["jumps", "violations"]} preferred={["distance", "elapsed_time", "speed"]} />;
  return <KeyValueEvidence title="Evidence Summary" evidence={evidence} preferred={Object.keys(evidence).slice(0, 8)} />;
}

function KeyValueEvidence({ title, evidence, preferred }: { title: string; evidence: Record<string, unknown>; preferred: string[] }) {
  const rows = preferred.filter((key) => key in evidence).slice(0, 8);
  return (
    <div className="rounded-2xl bg-muted/40 p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{title}</p>
      {rows.length ? (
        <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
          {rows.map((key) => <Pair key={key} label={humanize(key)} value={evidence[key]} />)}
        </dl>
      ) : <Fallback evidence={evidence} />}
    </div>
  );
}

function ListEvidence({ title, evidence, listKeys, preferred }: { title: string; evidence: Record<string, unknown>; listKeys: string[]; preferred: string[] }) {
  const listKey = listKeys.find((key) => Array.isArray(evidence[key]));
  const examples = listKey ? (evidence[listKey] as unknown[]).slice(0, 5) : [];
  return (
    <div className="rounded-2xl bg-muted/40 p-3">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{title}</p>
      <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-2">
        {preferred.filter((key) => key in evidence).map((key) => <Pair key={key} label={humanize(key)} value={evidence[key]} />)}
      </dl>
      {examples.length ? (
        <div className="mt-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground">Showing first {examples.length} evidence examples</p>
          {examples.map((item, index) => <pre key={index} className="overflow-auto rounded-xl border border-border bg-background p-2 text-xs whitespace-pre-wrap">{JSON.stringify(item, null, 2)}</pre>)}
        </div>
      ) : <Fallback evidence={evidence} />}
    </div>
  );
}

function Pair({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-xl border border-border bg-background p-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words font-semibold">{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
    </div>
  );
}

function Fallback({ evidence }: { evidence: Record<string, unknown> }) {
  return <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-words text-xs">{JSON.stringify(evidence, null, 2)}</pre>;
}

function humanize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}
