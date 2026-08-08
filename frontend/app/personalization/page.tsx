"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { domains, formats, loadTypes, recordCounts } from "@/components/generator/options";
import { usePreferencesStore } from "@/store/preferences-store";
import type { Domain, LoadType, OutputFormat } from "@/types/api";
import { titleCase } from "@/lib/utils";

export default function PersonalizationPage() {
  const preferences = usePreferencesStore();
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-4xl font-bold tracking-tight">Personalization</h1>
        <p className="mt-2 text-muted-foreground">Stored locally in your browser for a faster generator workflow.</p>
      </header>
      <Card>
        <CardHeader>
          <CardTitle>Default Generation Preferences</CardTitle>
          <CardDescription>These values help pre-shape future workflows.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5 md:grid-cols-2">
          <Select label="Default Domain" value={preferences.defaultDomain} onChange={(value) => preferences.setPreference("defaultDomain", value as Domain)} options={domains.map((item) => [item.id, item.name])} />
          <Select label="Default Load Type" value={preferences.defaultLoadType} onChange={(value) => preferences.setPreference("defaultLoadType", value as LoadType)} options={loadTypes.map((item) => [item.id, item.name])} />
          <Select label="Default Format" value={preferences.defaultFormat} onChange={(value) => preferences.setPreference("defaultFormat", value as OutputFormat)} options={formats.map((item) => [item.id, item.name])} />
          <Select label="Preferred Record Count" value={String(preferences.preferredRecordCount)} onChange={(value) => preferences.setPreference("preferredRecordCount", Number(value))} options={recordCounts.map((item) => [String(item.value), item.label])} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Recent Domains</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          {preferences.recentDomains.map((domain) => <span key={domain} className="rounded-full border border-border bg-muted px-4 py-2 text-sm font-medium">{titleCase(domain)}</span>)}
        </CardContent>
      </Card>
    </div>
  );
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-semibold">{label}</span>
      <select className="h-12 w-full rounded-xl border border-border bg-card px-3" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([optionValue, optionLabel]) => <option key={optionValue} value={optionValue}>{optionLabel}</option>)}
      </select>
    </label>
  );
}
