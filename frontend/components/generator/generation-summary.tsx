"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { estimateSize, formatNumber, titleCase } from "@/lib/utils";
import { issueLabels } from "@/components/generator/options";
import type { DatabaseType, Domain, LoadType, OutputFormat } from "@/types/api";
import type { IssueConfig } from "@/store/generator-store";

export function GenerationSummary({
  domain,
  loadType,
  format,
  databaseType,
  records,
  tables,
  issues,
  generating,
  canGenerate = true,
  disabledReason,
  onGenerate,
}: {
  domain: Domain;
  loadType: LoadType;
  format: OutputFormat;
  databaseType?: DatabaseType;
  records: number;
  tables: string[];
  issues: Record<string, IssueConfig>;
  generating: boolean;
  canGenerate?: boolean;
  disabledReason?: string;
  onGenerate: () => void;
}) {
  const enabledIssues = Object.entries(issues).filter(([, config]) => config.enabled);
  return (
    <Card className="xl:sticky xl:top-5">
      <CardHeader className="p-4">
        <CardTitle>Generation Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4 pt-0">
        <SummaryRow label="Domain" value={titleCase(domain)} />
        <SummaryRow label="Load Type" value={titleCase(loadType)} />
        <SummaryRow label="Format" value={format === "database" ? "Database" : format.toUpperCase()} />
        {databaseType ? <SummaryRow label="Database Type" value={databasePackageLabel(databaseType)} /> : null}
        <SummaryRow label="Records" value={formatNumber(records)} />
        <SummaryRow label="Selected Tables" value={tables.length ? `${tables.length} tables` : "0 selected"} />
        <SummaryRow label="Estimated Files" value={format === "database" ? "1 DDL ZIP" : `${tables.length} files`} />
        <SummaryRow label="Estimated Total Size" value={`${estimateSize(records, tables, format, domain).toFixed(1)} MB`} />

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Issues</p>
          <div className="flex flex-wrap gap-2">
            {enabledIssues.length ? (
              enabledIssues.map(([issue, config]) => <Badge key={issue}>{issueLabels[issue]} · {config.percentage}%</Badge>)
            ) : (
              <Badge>Clean dataset</Badge>
            )}
          </div>
        </div>

        <Button className="h-11 w-full text-sm" onClick={onGenerate} disabled={generating || !canGenerate}>
          {generating ? "Generating..." : canGenerate ? "Generate Dataset" : disabledReason ?? "Select tables"}
        </Button>
      </CardContent>
    </Card>
  );
}

function databasePackageLabel(databaseType: DatabaseType) {
  if (databaseType === "postgresql") return "PostgreSQL DDL Package";
  if (databaseType === "mssql") return "MSSQL DDL Package";
  return "MySQL DDL Package";
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-4">
      <span className="shrink-0 text-xs text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate text-right text-xs font-semibold" title={value}>{value}</span>
    </div>
  );
}
