"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { AlertCircle, Database, Info } from "lucide-react";
import { generateDataset, getCatalogTables, waitForJob } from "@/lib/api";
import { useGeneratorStore } from "@/store/generator-store";
import { usePreferencesStore } from "@/store/preferences-store";
import { useUiStore } from "@/store/ui-store";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { GenerationSummary } from "@/components/generator/generation-summary";
import { GenerationProgress } from "@/components/generator/generation-progress";
import { domains, formats, issueLabels, loadTypes } from "@/components/generator/options";
import { cn, estimateSize, titleCase } from "@/lib/utils";
import type { Domain, LoadType, OutputFormat } from "@/types/api";

export default function GeneratorPage() {
  const router = useRouter();
  const { toast } = useUiStore();
  const { addRecentDomain } = usePreferencesStore();
  const store = useGeneratorStore();

  const catalogQuery = useQuery({
    queryKey: ["catalog", store.domain],
    queryFn: () => getCatalogTables(store.domain),
  });

  const selectedTables = store.selectedTables;
  const selectedIssues = Object.fromEntries(
    Object.entries(store.issues).filter(([, config]) => config.enabled).map(([issue, config]) => [issue, config.percentage]),
  );

  const generateMutation = useMutation({
    mutationFn: async () => {
      if (!selectedTables.length) {
        throw new Error("Select at least one table before generating files.");
      }
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
    const current = store.selectedTables;
    store.setSelectedTables(current.includes(table) ? current.filter((item) => item !== table) : [...current, table]);
  }

  if (generateMutation.isPending) {
    return (
      <div className="space-y-5">
        <header className="rounded-2xl border border-border bg-white/70 p-5 text-center shadow-sm backdrop-blur">
          <Badge>Phase 1 · Functional</Badge>
          <h1 className="mt-3 text-3xl font-bold tracking-tight">Generate Enterprise Datasets</h1>
          <p className="mt-2 text-sm text-muted-foreground">Your selected files are being generated now.</p>
        </header>

        <GenerationProgress
          active
          domain={store.domain}
          loadType={store.loadType}
          format={store.format}
          records={store.records}
          tableCount={selectedTables.length}
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header className="rounded-2xl border border-border bg-white/70 p-5 shadow-sm backdrop-blur">
        <Badge>Phase 1 · Functional</Badge>
        <HoverHelp
          className="mt-3"
          title="Generate Enterprise Datasets"
          titleClassName="text-3xl font-bold tracking-tight"
          description="Generate realistic datasets, inject issues, validate quality, and export results."
        />
      </header>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-5">
          <Card id="dataset-setup" className="scroll-mt-6">
            <CardHeader className="p-4">
              <HoverHelp title="1. Dataset Setup" description="Select domain, load type, and format in one place." />
            </CardHeader>
            <CardContent className="grid gap-3 p-4 pt-0 lg:grid-cols-4">
              <ConfigSelect
                label="Domain"
                value={store.domain}
                options={domains}
                onChange={(value) => store.setDomain(value as Domain)}
              />
              <ConfigSelect
                label="Load Type"
                value={store.loadType}
                options={loadTypes}
                onChange={(value) => store.setLoadType(value as LoadType)}
              />
              <ConfigSelect
                label="Format"
                value={store.format}
                options={formats}
                onChange={(value) => store.setFormat(value as OutputFormat)}
              />
              <RecordCountInput value={store.records} onChange={store.setRecords} />
            </CardContent>
          </Card>

          <Card id="tables" className="scroll-mt-6">
            <CardHeader className="p-4">
              <HoverHelp title="2. Table Selection" description="Loaded dynamically from the backend domain catalog." />
            </CardHeader>
            <CardContent className="p-4 pt-0">
              {catalogQuery.isLoading ? (
                <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-20" />)}</div>
              ) : catalogQuery.isError ? (
                <div className="flex items-center gap-3 rounded-2xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
                  <AlertCircle className="h-4 w-4" />
                  <span>
                    Unable to load table catalog. Make sure the FastAPI backend is running at{" "}
                    <code className="rounded bg-white/70 px-1.5 py-0.5">http://127.0.0.1:8010</code>.
                  </span>
                </div>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
                  {catalogQuery.data?.tables.map((table) => {
                    const isSelected = selectedTables.includes(table.name);
                    return (
                      <label
                        key={table.name}
                        className={cn(
                          "timed-hover-group relative rounded-xl border bg-card p-3 text-left transition hover:shadow-glow",
                          isSelected ? "border-primary ring-4 ring-primary/10" : "border-border",
                        )}
                      >
                        <div className="flex items-start gap-2.5">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleTable(table.name)}
                          className="mt-2 h-4 w-4 rounded border-border accent-primary"
                        />
                        <div className="rounded-lg bg-muted p-1.5 text-muted-foreground"><Database className="h-4 w-4" /></div>
                        <div className="relative min-w-0">
                          <p className="text-sm font-semibold">{titleCase(table.name)}</p>
                          <p className="timed-hover-popup pointer-events-none absolute left-0 top-full z-30 mt-2 w-max max-w-64 rounded-xl border border-border bg-popover px-3 py-2 text-xs leading-5 text-popover-foreground shadow-lg">
                            PK: {table.primary_key} · {table.columns.length} columns
                          </p>
                        </div>
                      </div>
                    </label>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          <Card id="issues" className="scroll-mt-6">
            <CardHeader className="p-4">
              <HoverHelp title="3. Issue Injection" description="Inject realistic quality problems before validation." />
            </CardHeader>
            <CardContent className="grid gap-3 p-4 pt-0 lg:grid-cols-2">
              {Object.entries(store.issues).map(([issue, config]) => (
                <div key={issue} className="rounded-xl border border-border bg-muted/30 p-3">
                  <div className="flex items-center justify-between gap-4">
                    <div className="timed-hover-group relative">
                      <p className="font-semibold">{issueLabels[issue]}</p>
                      <p className="timed-hover-popup pointer-events-none absolute left-0 top-full z-30 mt-2 flex w-max max-w-64 items-center gap-1 rounded-xl border border-border bg-popover px-3 py-2 text-xs leading-5 text-popover-foreground shadow-lg">
                        <Info className="h-3 w-3" /> {config.percentage}% target rate
                      </p>
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
                    className="mt-3 w-full accent-primary"
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
        </div>

        <GenerationSummary
          domain={store.domain}
          loadType={store.loadType}
          format={store.format}
          records={store.records}
          tables={selectedTables}
          issues={store.issues}
          generating={generateMutation.isPending}
          canGenerate={selectedTables.length > 0}
          disabledReason="Select at least one table"
          onGenerate={() => generateMutation.mutate()}
        />
      </div>
    </div>
  );
}

function RecordCountInput({ value, onChange }: { value: number; onChange: (records: number) => void }) {
  const presetValues = [1000, 10000, 100000, 500000];
  const [customMode, setCustomMode] = useState(!presetValues.includes(value));
  const selectedPreset = customMode || !presetValues.includes(value) ? "custom" : String(value);

  function updateRecords(rawValue: string) {
    const parsed = Math.floor(Number(rawValue));
    if (!Number.isFinite(parsed)) return;
    onChange(Math.min(500_000, Math.max(1, parsed)));
  }

  return (
    <label className="timed-hover-group relative block rounded-xl border border-border bg-muted/20 p-3">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Record Count</span>
      <div className="mt-2 grid gap-2">
        <select
          className="h-11 w-full rounded-xl border border-border bg-card px-3 text-sm font-semibold text-foreground outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10"
          value={selectedPreset}
          onChange={(event) => {
            if (event.target.value === "custom") {
              setCustomMode(true);
              return;
            }
            setCustomMode(false);
            updateRecords(event.target.value);
          }}
        >
          {presetValues.map((preset) => (
            <option key={preset} value={preset}>
              {preset}
            </option>
          ))}
          <option value="custom">Custom</option>
        </select>
        {selectedPreset === "custom" ? (
          <input
            className="h-11 w-full rounded-xl border border-border bg-card px-3 text-sm font-semibold text-foreground outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10"
            type="number"
            min={1}
            max={500000}
            step={1}
            value={value}
            onChange={(event) => updateRecords(event.target.value)}
            aria-label="Custom record count"
          />
        ) : null}
      </div>
      <span className="timed-hover-popup pointer-events-none absolute left-3 top-full z-40 mt-2 block w-max max-w-72 rounded-xl border border-border bg-popover px-3 py-2 text-xs leading-5 text-popover-foreground shadow-lg">
        Pick 1000, 10000, 100000, 500000, or enter a custom value from 1 to 500000.
      </span>
    </label>
  );
}

function HoverHelp({
  title,
  description,
  className,
  titleClassName = "text-lg font-semibold tracking-tight",
}: {
  title: string;
  description: string;
  className?: string;
  titleClassName?: string;
}) {
  return (
    <div className={cn("timed-hover-group relative inline-block", className)}>
      <CardTitle className={titleClassName}>{title}</CardTitle>
      <p className="timed-hover-popup pointer-events-none absolute left-0 top-full z-40 mt-2 w-max max-w-80 rounded-xl border border-border bg-popover px-3 py-2 text-xs leading-5 text-popover-foreground shadow-lg">
        {description}
      </p>
    </div>
  );
}

function ConfigSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { id: string; name: string; description: string }[];
  onChange: (value: string) => void;
}) {
  const selected = options.find((option) => option.id === value);

  return (
    <label className="timed-hover-group relative block rounded-xl border border-border bg-muted/20 p-3">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      <select
        className="mt-2 h-11 w-full rounded-xl border border-border bg-card px-3 text-sm font-semibold text-foreground outline-none transition focus:border-primary focus:ring-4 focus:ring-primary/10"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
      {selected ? (
        <span className="timed-hover-popup pointer-events-none absolute left-3 top-full z-40 mt-2 block w-max max-w-72 rounded-xl border border-border bg-popover px-3 py-2 text-xs leading-5 text-popover-foreground shadow-lg">
          {selected.description}
        </span>
      ) : null}
    </label>
  );
}
