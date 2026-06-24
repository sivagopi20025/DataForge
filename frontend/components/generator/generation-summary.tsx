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
  onGenerate,
}: {
  domain: Domain;
  loadType: LoadType;
  format: OutputFormat;
  records: number;
  tables: string[];
  issues: Record<string, IssueConfig>;
  generating: boolean;
  onGenerate: () => void;
}) {
  const enabledIssues = Object.entries(issues).filter(([, config]) => config.enabled);
  return (
    <Card className="sticky top-6">
      <CardHeader>
        <CardTitle>Generation Summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <SummaryRow label="Domain" value={titleCase(domain)} />
        <SummaryRow label="Load Type" value={titleCase(loadType)} />
        <SummaryRow label="Format" value={format.toUpperCase()} />
        <SummaryRow label="Records" value={formatNumber(records)} />
        <SummaryRow label="Selected Tables" value={tables.length ? `${tables.length} tables` : "All tables"} />
        <SummaryRow label="Estimated Files" value={`${Math.max(tables.length, 1)} files`} />
        <SummaryRow label="Estimated Size" value={`${estimateSize(records, tables.length || 6, format).toFixed(1)} MB`} />

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

        <Button className="h-[52px] w-full text-base" onClick={onGenerate} disabled={generating}>
          {generating ? "Generating..." : "Generate Dataset"}
        </Button>
      </CardContent>
    </Card>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-right text-sm font-semibold">{value}</span>
    </div>
  );
}
