"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock3, Database } from "lucide-react";
import { getRuns } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber, titleCase } from "@/lib/utils";

export default function RunHistoryPage() {
  const runsQuery = useQuery({ queryKey: ["runs", 25, 0], queryFn: () => getRuns(25, 0) });

  if (runsQuery.isLoading) {
    return <div className="space-y-6">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-28" />)}</div>;
  }

  if (runsQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Run history unavailable</CardTitle>
          <CardDescription>{runsQuery.error.message}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const runs = runsQuery.data?.items ?? [];

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-primary">History</p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight">Run History</h1>
          <p className="mt-2 text-muted-foreground">Review completed dataset generation runs and reopen their result pages.</p>
        </div>
        <Link href="/generator">
          <Button>Generate New Dataset</Button>
        </Link>
      </header>

      <div className="grid gap-4 md:grid-cols-3">
        <Metric label="Total Runs" value={formatNumber(runsQuery.data?.total ?? 0)} />
        <Metric label="Displayed" value={formatNumber(runs.length)} />
        <Metric label="Latest Status" value={runs[0]?.status ? titleCase(runs[0].status) : "No runs"} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Runs</CardTitle>
          <CardDescription>Most recent DataForge generation jobs persisted by the backend.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {runs.length ? runs.map((run) => (
            <Link
              key={run.id}
              href={`/runs/${run.id}`}
              className="flex flex-col gap-4 rounded-2xl border border-border bg-muted/30 p-4 transition hover:border-primary/50 hover:bg-primary/5 md:flex-row md:items-center md:justify-between"
            >
              <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Database className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold">{titleCase(run.domain)} · {titleCase(run.load_type)}</p>
                    <Badge>{run.status}</Badge>
                  </div>
                  <p className="mt-1 break-all text-sm text-muted-foreground">{run.id}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {run.format.toUpperCase()} · {formatNumber(run.record_count)} records
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-between gap-4 md:min-w-[260px]">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Clock3 className="h-4 w-4" />
                  {formatDateTime(run.completed_at ?? run.started_at)}
                </div>
                <ArrowRight className="h-4 w-4 text-primary" />
              </div>
            </Link>
          )) : (
            <div className="rounded-2xl border border-dashed border-border p-8 text-center">
              <p className="font-semibold">No run history yet.</p>
              <p className="mt-2 text-sm text-muted-foreground">Generate a dataset to create your first run history entry.</p>
              <Link href="/generator" className="mt-4 inline-block">
                <Button>Go to Generator</Button>
              </Link>
            </div>
          )}
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
