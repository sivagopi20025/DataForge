"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { estimateSize, formatNumber, titleCase } from "@/lib/utils";
import { issueLabels } from "@/components/generator/options";
import type { Domain, LoadType, OutputFormat } from "@/types/api";
import type { IssueConfig } from "@/store/generator-store";

export function GenerationSummary({
  domain,
  loadType,
  format,
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
    <Card className="sticky top-5">
      <CardHeader className="p-4">
        <CardTitle>Generation Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 p-4 pt-0">
        <SummaryRow label="Domain" value={titleCase(domain)} />
        <SummaryRow label="Load Type" value={titleCase(loadType)} />
        <SummaryRow label="Format" value={format.toUpperCase()} />
        <SummaryRow label="Records" value={formatNumber(records)} />
        <SummaryRow label="Selected Tables" value={tables.length ? `${tables.length} tables` : "0 selected"} />
        <SummaryRow label="Estimated Files" value={`${tables.length} files`} />
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

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-right text-xs font-semibold">{value}</span>
    </div>
  );
}
