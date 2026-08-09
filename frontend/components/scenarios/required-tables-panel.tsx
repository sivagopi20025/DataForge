"use client";

import { Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { formatNumber } from "@/lib/utils";
import type { ScenarioBuilderConfiguration } from "@/types/api";

export function RequiredTablesPanel({ config }: { config: ScenarioBuilderConfiguration }) {
  return (
    <section className="rounded-3xl border border-border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Dataset / Required Tables</h3>
          <p className="text-sm text-muted-foreground">These tables will be generated for the scenario and validation path.</p>
        </div>
        <Badge>{config.required_tables.length} tables</Badge>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {config.required_tables.map((table) => (
          <div key={table.table} className="rounded-2xl border border-border bg-background p-4">
            <div className="flex items-start gap-3">
              <span className="rounded-xl bg-primary/10 p-2 text-primary"><Database className="h-4 w-4" /></span>
              <div className="min-w-0">
                <p className="font-semibold">{table.table}</p>
                <p className="text-sm text-muted-foreground">{table.business_purpose}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge>{formatNumber(table.estimated_rows)} rows estimated</Badge>
                  <Badge>{table.role}</Badge>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
