"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, FileArchive, ShieldCheck } from "lucide-react";
import { getDownloadUrl, getRun } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { QualityRing } from "@/components/results/quality-ring";
import { formatNumber, titleCase } from "@/lib/utils";

export default function RunDetailPage() {
  const params = useParams<{ run_id: string }>();
  const runQuery = useQuery({ queryKey: ["run", params.run_id], queryFn: () => getRun(params.run_id) });

  if (runQuery.isLoading) {
    return <div className="space-y-6">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-32" />)}</div>;
  }

  if (runQuery.isError || !runQuery.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Run unavailable</CardTitle>
          <CardDescription>{runQuery.error?.message ?? "The run could not be loaded."}</CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/generator"><Button>Back to Generator</Button></Link>
        </CardContent>
      </Card>
    );
  }

  const run = runQuery.data;
  const qualityScore = run.validation_results.find((item) => item.quality_score !== null)?.quality_score ?? 100;
  const started = new Date(run.started_at).getTime();
  const completed = run.completed_at ? new Date(run.completed_at).getTime() : started;
  const duration = Math.max(0, (completed - started) / 1000).toFixed(2);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <Link href="/generator" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> Back to generator
          </Link>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Run Results</h1>
          <p className="mt-2 text-muted-foreground">Run ID: {run.id}</p>
        </div>
        <Badge>{run.status}</Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-3 2xl:grid-cols-6">
        <Metric label="Domain" value={titleCase(run.domain)} />
        <Metric label="Load Type" value={titleCase(run.load_type)} />
        <Metric label="Format" value={run.format.toUpperCase()} />
        <Metric label="Records" value={formatNumber(run.record_count)} />
        <Metric label="Generation Time" value={`${duration}s`} />
        <Metric label="Quality Score" value={`${Math.round(qualityScore)}`} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-primary" /> Quality Score</CardTitle>
        </CardHeader>
        <CardContent>
          <QualityRing score={qualityScore} status={qualityScore >= 80 ? "PASS" : "FAIL"} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Validation Results</CardTitle>
          <CardDescription>Expected vs actual checks emitted by the backend validation framework.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
              <tr>
                <th className="border-b border-border py-3">Check</th>
                <th className="border-b border-border py-3">Expected</th>
                <th className="border-b border-border py-3">Actual</th>
                <th className="border-b border-border py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {run.validation_results.length ? run.validation_results.map((check) => (
                <tr key={check.id}>
                  <td className="border-b border-border py-4 font-medium">{titleCase(check.validation_name)}</td>
                  <td className="border-b border-border py-4 text-muted-foreground">{check.expected_value}</td>
                  <td className="border-b border-border py-4 text-muted-foreground">{check.actual_value}</td>
                  <td className="border-b border-border py-4"><Badge className={check.status === "PASS" ? "text-success" : "text-danger"}>{check.status}</Badge></td>
                </tr>
              )) : (
                <tr><td className="py-6 text-muted-foreground" colSpan={4}>No validation rows persisted for this run.</td></tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <div className="grid gap-8 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Issues Injected</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2">
            {run.issue_manifest.length ? run.issue_manifest.map((issue) => (
              <div key={issue.id} className="rounded-2xl border border-border bg-muted/30 p-4">
                <p className="font-semibold">{titleCase(issue.issue_type)}</p>
                <p className="mt-2 text-2xl font-bold">{formatNumber(issue.issue_count)}</p>
                <p className="text-sm text-muted-foreground">{issue.issue_percentage}% target</p>
              </div>
            )) : <p className="text-sm text-muted-foreground">No issues were injected.</p>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Generated Files</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {run.generated_files.map((file) => (
              <div key={file.id} className="flex items-center justify-between gap-4 rounded-2xl border border-border bg-muted/30 p-4">
                <div className="flex items-center gap-3">
                  <FileArchive className="h-5 w-5 text-primary" />
                  <div>
                    <p className="font-semibold">{file.file_name}</p>
                    <p className="text-sm text-muted-foreground">{file.file_format.toUpperCase()} · {file.file_size_mb.toFixed(3)} MB</p>
                  </div>
                </div>
                <a href={getDownloadUrl(run.id, file.id)} download>
                  <Button variant="secondary">
                    <Download className="mr-2 h-4 w-4" /> Download
                  </Button>
                </a>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
        <p className="mt-2 text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}
