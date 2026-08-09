import { CheckCircle2, Loader2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { formatNumber, titleCase } from "@/lib/utils";
import type { DatabaseType, Domain, LoadType, OutputFormat } from "@/types/api";

const steps = ["Generating", "Injecting Issues", "Validating", "Exporting", "Saving Metadata", "Completed"];

export function GenerationProgress({
  active,
  domain,
  loadType,
  format,
  databaseType,
  records,
  tableCount,
}: {
  active: boolean;
  domain?: Domain;
  loadType?: LoadType;
  format?: OutputFormat;
  databaseType?: DatabaseType;
  records?: number;
  tableCount?: number;
}) {
  if (!active) return null;
  return (
    <div className="mx-auto flex min-h-[52vh] max-w-3xl items-center justify-center px-4">
      <div className="w-full rounded-3xl border border-border bg-card p-8 text-center shadow-glow">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Loader2 className="h-7 w-7 animate-spin" />
        </div>

        <p className="mt-5 text-xs font-semibold uppercase tracking-[0.24em] text-primary">Live generation</p>
        <h2 className="mt-2 text-3xl font-bold tracking-tight">Generating files...</h2>
        <p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">
          DataForge is creating the selected dataset, running validation, and preparing downloadable files.
        </p>

        <div className="mx-auto mt-5 grid max-w-2xl gap-3 rounded-2xl border border-border bg-muted/30 p-4 text-left sm:grid-cols-2 lg:grid-cols-4">
          {domain ? <SummaryPill label="Domain" value={titleCase(domain)} /> : null}
          {loadType ? <SummaryPill label="Load Type" value={titleCase(loadType)} /> : null}
          {format ? <SummaryPill label="Format" value={format === "database" ? "Database" : format.toUpperCase()} /> : null}
          {databaseType ? <SummaryPill label="Database" value={databaseType === "postgresql" ? "PostgreSQL" : databaseType === "mssql" ? "MSSQL" : "MySQL"} /> : null}
          {records ? <SummaryPill label="Records" value={formatNumber(records)} /> : null}
          {tableCount ? <SummaryPill label="Files" value={`${tableCount} selected`} /> : null}
        </div>

        <Progress value={72} className="mt-6" />
        <div className="mt-5 grid gap-2 text-left md:grid-cols-3">
          {steps.map((step, index) => (
            <div key={step} className="flex items-center gap-2 rounded-xl bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
              {index < 3 ? <CheckCircle2 className="h-4 w-4 text-success" /> : <Loader2 className="h-4 w-4 animate-spin text-primary" />}
              {step}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SummaryPill({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}
