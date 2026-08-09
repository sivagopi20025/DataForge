"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { titleCase } from "@/lib/utils";
import type { ScenarioBuilderConfiguration } from "@/types/api";

export function ScenarioOverview({ config }: { config: ScenarioBuilderConfiguration }) {
  const scenario = config.scenario;
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Badge>{scenario.v1_ready ? "V1 Ready" : "Experimental"}</Badge>
            <CardTitle className="mt-3 text-2xl">{scenario.scenario_name}</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">{scenario.description}</p>
          </div>
          <Badge>{titleCase(scenario.domain)}</Badge>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2">
        <Info title="Business rule" value={scenario.business_rule} />
        <Info title="Example failure" value={scenario.example_failure} />
        <Info title="Primary entity" value={titleCase(scenario.entity)} />
        <Info title="Detection strategy" value={scenario.validator_detection_strategy} />
        <details className="rounded-2xl border border-border p-4 md:col-span-2">
          <summary className="cursor-pointer font-semibold">Technical details</summary>
          <div className="mt-3 grid gap-2 text-sm text-muted-foreground md:grid-cols-2">
            <p>Primitive: {scenario.technical_details.primitive_id}</p>
            <p>Validator: {scenario.technical_details.validator_id}</p>
            <p className="md:col-span-2">Semantic mappings: {scenario.technical_details.semantic_mappings.slice(0, 8).join(", ")}</p>
          </div>
        </details>
      </CardContent>
    </Card>
  );
}

function Info({ title, value }: { title: string; value: string }) {
  return (
    <section className="rounded-2xl border border-border bg-muted/30 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{title}</p>
      <p className="mt-2 text-sm">{value}</p>
    </section>
  );
}
