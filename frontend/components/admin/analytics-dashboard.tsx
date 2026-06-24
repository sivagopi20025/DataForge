"use client";

import type React from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getAnalyticsMap, getAnalyticsOverview, getQualityRuns, getQualityTrends } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber, titleCase } from "@/lib/utils";

export function AnalyticsDashboard() {
  const overview = useQuery({ queryKey: ["analytics", "overview"], queryFn: getAnalyticsOverview });
  const domains = useQuery({ queryKey: ["analytics", "domains"], queryFn: () => getAnalyticsMap("domains") });
  const formats = useQuery({ queryKey: ["analytics", "formats"], queryFn: () => getAnalyticsMap("formats") });
  const loadTypes = useQuery({ queryKey: ["analytics", "load-types"], queryFn: () => getAnalyticsMap("load-types") });
  const trends = useQuery({ queryKey: ["analytics", "quality-trends"], queryFn: getQualityTrends });
  const lowest = useQuery({ queryKey: ["analytics", "lowest"], queryFn: () => getQualityRuns("lowest") });
  const highest = useQuery({ queryKey: ["analytics", "highest"], queryFn: () => getQualityRuns("highest") });

  if (overview.isLoading) return <div className="grid gap-4 md:grid-cols-3">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-32" />)}</div>;

  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-3 2xl:grid-cols-6">
        <Metric label="Datasets Generated" value={formatNumber(overview.data?.datasets_generated)} />
        <Metric label="Validation Runs" value={formatNumber(overview.data?.validation_runs)} />
        <Metric label="Avg Quality" value={`${Math.round(overview.data?.average_quality_score ?? 0)}`} />
        <Metric label="Top Domain" value={titleCase(overview.data?.most_used_domain ?? "none")} />
        <Metric label="Top Format" value={(overview.data?.most_used_format ?? "none").toUpperCase()} />
        <Metric label="Top Load Type" value={titleCase(overview.data?.most_used_load_type ?? "none")} />
      </div>

      <div className="grid gap-8 xl:grid-cols-2">
        <ChartCard title="Quality Score Trend" description="Average quality score over time.">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trends.data ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Line type="monotone" dataKey="average_quality_score" stroke="hsl(var(--primary))" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Domain Usage" description="Most generated domains.">
          <BarDataChart data={mapToRows(domains.data)} />
        </ChartCard>
        <ChartCard title="Format Usage" description="CSV, JSON, and Parquet generation split.">
          <BarDataChart data={mapToRows(formats.data)} />
        </ChartCard>
        <ChartCard title="Load Type Usage" description="Bulk, incremental, delta, CDC, and event stream split.">
          <BarDataChart data={mapToRows(loadTypes.data)} />
        </ChartCard>
      </div>

      <div className="grid gap-8 xl:grid-cols-2">
        <RunList title="Lowest Quality Runs" rows={lowest.data ?? []} />
        <RunList title="Highest Quality Runs" rows={highest.data ?? []} />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
        <p className="mt-2 truncate text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

function ChartCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function BarDataChart({ data }: { data: { name: string; value: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" />
        <YAxis />
        <Tooltip />
        <Bar dataKey="value" fill="hsl(var(--primary))" radius={[8, 8, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function RunList({ title, rows }: { title: string; rows: { run_id: string; domain: string; load_type: string; quality_score: number }[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {rows.length ? rows.map((row) => (
          <div key={row.run_id} className="flex items-center justify-between gap-4 rounded-2xl border border-border bg-muted/30 p-4">
            <div>
              <p className="font-semibold">{row.run_id}</p>
              <p className="text-sm text-muted-foreground">{titleCase(row.domain)} · {titleCase(row.load_type)}</p>
            </div>
            <p className="text-2xl font-bold">{Math.round(row.quality_score)}</p>
          </div>
        )) : <p className="text-sm text-muted-foreground">No quality runs yet.</p>}
      </CardContent>
    </Card>
  );
}

function mapToRows(data?: Record<string, number>) {
  return Object.entries(data ?? {}).map(([name, value]) => ({ name: titleCase(name), value }));
}
