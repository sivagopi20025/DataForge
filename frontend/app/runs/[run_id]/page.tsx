"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, FileArchive } from "lucide-react";
import { getDownloadUrl, getRun } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
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
  const generatedAt = formatDateTime(run.completed_at ?? run.started_at);

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
        <div className="flex items-center gap-3">
          <Link href="/history">
            <Button variant="secondary">View history</Button>
          </Link>
          <Badge>{run.status}</Badge>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3 2xl:grid-cols-6">
        <Metric label="Domain" value={titleCase(run.domain)} />
        <Metric label="Load Type" value={titleCase(run.load_type)} />
        <Metric label="Format" value={run.format.toUpperCase()} />
        <Metric label="Records" value={formatNumber(run.record_count)} />
        <Metric label="Generated At" value={generatedAt} />
        <Metric label="Quality Score" value={`${Math.round(qualityScore)}`} />
      </div>

      <Card className="mx-auto max-w-4xl">
        <CardHeader className="text-center">
          <CardTitle>Generated Files</CardTitle>
          <CardDescription>Download the files created for this run.</CardDescription>
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

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
