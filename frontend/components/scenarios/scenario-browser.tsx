"use client";

import { Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { titleCase } from "@/lib/utils";
import type { Domain, ScenarioLibrarySummary } from "@/types/api";

const domains: ("all" | Domain)[] = ["all", "retail", "banking", "healthcare", "manufacturing", "telecommunications", "logistics", "finance", "insurance", "education", "ecommerce"];

export function ScenarioBrowser({
  scenarios,
  selectedId,
  domain,
  onDomainChange,
  onSelect,
}: {
  scenarios: ScenarioLibrarySummary[];
  selectedId?: string;
  domain: "all" | Domain;
  onDomainChange: (domain: "all" | Domain) => void;
  onSelect: (scenarioId: string) => void;
}) {
  return (
    <section className="rounded-3xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="min-w-0 flex-1 text-sm">
          <span className="sr-only">Scenario search</span>
          <div className="flex h-11 items-center gap-2 rounded-2xl border border-border bg-background px-3 text-muted-foreground">
            <Search className="h-4 w-4" />
            <span className="text-sm">Executable / V1-ready scenarios</span>
          </div>
        </label>
        <label className="text-sm">
          <span className="sr-only">Filter by domain</span>
          <select value={domain} onChange={(event) => onDomainChange(event.target.value as "all" | Domain)} className="h-11 w-full rounded-2xl border border-border bg-background px-3 sm:w-56">
            {domains.map((item) => (
              <option key={item} value={item}>{item === "all" ? "All domains" : titleCase(item)}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-4 grid max-h-[560px] gap-3 overflow-y-auto pr-1">
        {scenarios.map((scenario) => (
          <button
            key={scenario.scenario_id}
            onClick={() => onSelect(scenario.scenario_id)}
            className={`rounded-2xl border p-4 text-left transition hover:border-primary ${selectedId === scenario.scenario_id ? "border-primary bg-primary/5" : "border-border bg-background"}`}
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-semibold">{scenario.scenario_name}</p>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{scenario.description}</p>
              </div>
              <Badge>{titleCase(scenario.domain)}</Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              <Badge>{titleCase(scenario.business_process)}</Badge>
              <Badge>{scenario.failure_display_name}</Badge>
              <Badge>{scenario.v1_ready ? "V1 Ready" : "Experimental"}</Badge>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
