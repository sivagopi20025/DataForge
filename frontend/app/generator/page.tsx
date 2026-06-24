"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { AlertCircle, Database, Info } from "lucide-react";
import { generateDataset, getCatalogTables, waitForJob } from "@/lib/api";
import { useGeneratorStore } from "@/store/generator-store";
import { usePreferencesStore } from "@/store/preferences-store";
import { useUiStore } from "@/store/ui-store";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { SelectionCard } from "@/components/generator/selection-card";
import { GenerationSummary } from "@/components/generator/generation-summary";
import { GenerationProgress } from "@/components/generator/generation-progress";
import { domains, formats, issueLabels, loadTypes, recordCounts } from "@/components/generator/options";
import { cn, estimateSize, titleCase } from "@/lib/utils";

export default function GeneratorPage() {
  const router = useRouter();
  const { toast } = useUiStore();
  const { addRecentDomain } = usePreferencesStore();
  const store = useGeneratorStore();

  const catalogQuery = useQuery({
    queryKey: ["catalog", store.domain],
    queryFn: () => getCatalogTables(store.domain),
  });

  const selectedTables = store.selectedTables.length ? store.selectedTables : catalogQuery.data?.tables.map((table) => table.name) ?? [];
  const selectedIssues = Object.fromEntries(
    Object.entries(store.issues).filter(([, config]) => config.enabled).map(([issue, config]) => [issue, config.percentage]),
  );

  const generateMutation = useMutation({
    mutationFn: async () => {
      const response = await generateDataset({
        domain: store.domain,
        load_type: store.loadType,
        format: store.format,
        records: store.records,
        selected_tables: selectedTables,
        issues: selectedIssues,
      });
      return response.run_id ? response : waitForJob(response.job_id);
    },
    onSuccess: (response) => {
      addRecentDomain(store.domain);
      if (!response.run_id) {
        throw new Error("Generation completed without a run id.");
      }
      toast({ title: "Dataset generated", description: `Run ${response.run_id} completed successfully.` });
      router.push(`/runs/${response.run_id}`);
    },
    onError: (error) => toast({ title: "Generation failed", description: error.message }),
  });

  function toggleTable(table: string) {
    const current = store.selectedTables.length ? store.selectedTables : catalogQuery.data?.tables.map((item) => item.name) ?? [];
    store.setSelectedTables(current.includes(table) ? current.filter((item) => item !== table) : [...current, table]);
  }

  return (
    <div className="space-y-8">
      <header className="rounded-3xl border border-border bg-white/70 p-8 shadow-sm backdrop-blur">
        <Badge>Phase 1 · Functional</Badge>
        <h1 className="mt-4 text-4xl font-bold tracking-tight">Generate Enterprise Datasets</h1>
        <p className="mt-3 max-w-3xl text-lg text-muted-foreground">
          Generate realistic datasets, inject issues, validate quality, and export results.
        </p>
      </header>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-8">
          <Card>
            <CardHeader>
              <CardTitle>1. Domain Selection</CardTitle>
              <CardDescription>Choose the business shape for the dataset.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {domains.map((domain) => (
                <SelectionCard
                  key={domain.id}
                  selected={store.domain === domain.id}
                  title={domain.name}
                  description={domain.description}
                  icon={<domain.icon className="h-5 w-5" />}
                  onClick={() => store.setDomain(domain.id)}
                />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>2. Load Type</CardTitle>
              <CardDescription>Match the way your pipeline receives data.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2 2xl:grid-cols-5">
              {loadTypes.map((loadType) => (
                <SelectionCard
                  key={loadType.id}
                  selected={store.loadType === loadType.id}
                  title={loadType.name}
                  description={loadType.description}
                  onClick={() => store.setLoadType(loadType.id)}
                />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>3. Format</CardTitle>
              <CardDescription>Pick the export format for generated files.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              {formats.map((format) => (
                <SelectionCard
                  key={format.id}
                  selected={store.format === format.id}
                  title={format.name}
                  description={format.description}
                  onClick={() => store.setFormat(format.id)}
                />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>4. Table Selection</CardTitle>
              <CardDescription>Loaded dynamically from the backend domain catalog.</CardDescription>
            </CardHeader>
            <CardContent>
              {catalogQuery.isLoading ? (
                <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-24" />)}</div>
              ) : catalogQuery.isError ? (
                <div className="flex items-center gap-3 rounded-2xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
                  <AlertCircle className="h-4 w-4" />
                  <span>
                    Unable to load table catalog. Make sure the FastAPI backend is running at{" "}
                    <code className="rounded bg-white/70 px-1.5 py-0.5">http://127.0.0.1:8010</code>.
                  </span>
                </div>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                  {catalogQuery.data?.tables.map((table) => (
                    <button
                      key={table.name}
                      type="button"
                      onClick={() => toggleTable(table.name)}
                      className={cn(
                        "rounded-2xl border bg-card p-4 text-left transition hover:shadow-glow",
                        selectedTables.includes(table.name) ? "border-primary ring-4 ring-primary/10" : "border-border",
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <div className="rounded-xl bg-muted p-2 text-muted-foreground"><Database className="h-4 w-4" /></div>
                        <div>
                          <p className="font-semibold">{titleCase(table.name)}</p>
                          <p className="mt-1 text-xs text-muted-foreground">PK: {table.primary_key} · {table.columns.length} columns</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>5. Record Count</CardTitle>
              <CardDescription>Estimate: {estimateSize(store.records, selectedTables.length || 6, store.format).toFixed(1)} MB output.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-4">
              {recordCounts.map((count) => (
                <SelectionCard
                  key={count.value}
                  selected={store.records === count.value}
                  title={count.label}
                  description={`${count.value.toLocaleString()} records`}
                  onClick={() => store.setRecords(count.value)}
                />
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>6. Issue Injection</CardTitle>
              <CardDescription>Inject realistic quality problems before validation.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 lg:grid-cols-2">
              {Object.entries(store.issues).map(([issue, config]) => (
                <div key={issue} className="rounded-2xl border border-border bg-muted/30 p-4">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="font-semibold">{issueLabels[issue]}</p>
                      <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground"><Info className="h-3 w-3" /> {config.percentage}% target rate</p>
                    </div>
                    <button
                      onClick={() => store.toggleIssue(issue)}
                      className={cn("h-7 w-12 rounded-full p-1 transition", config.enabled ? "bg-primary" : "bg-border")}
                      aria-label={`Toggle ${issueLabels[issue]}`}
                    >
                      <span className={cn("block h-5 w-5 rounded-full bg-white transition", config.enabled && "translate-x-5")} />
                    </button>
                  </div>
                  <input
                    className="mt-4 w-full accent-primary"
                    type="range"
                    min={1}
                    max={15}
                    value={config.percentage}
                    disabled={!config.enabled}
                    onChange={(event) => store.setIssuePercentage(issue, Number(event.target.value))}
                  />
                </div>
              ))}
            </CardContent>
          </Card>

          <GenerationProgress active={generateMutation.isPending} />
        </div>

        <GenerationSummary
          domain={store.domain}
          loadType={store.loadType}
          format={store.format}
          records={store.records}
          tables={selectedTables}
          issues={store.issues}
          generating={generateMutation.isPending}
          onGenerate={() => generateMutation.mutate()}
        />
      </div>
    </div>
  );
}
