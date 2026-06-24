"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { usePreferencesStore } from "@/store/preferences-store";

export default function SettingsPage() {
  const preferences = usePreferencesStore();
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-4xl font-bold tracking-tight">Settings</h1>
        <p className="mt-2 text-muted-foreground">Local UI preferences and API connection details.</p>
      </header>
      <Card>
        <CardHeader>
          <CardTitle>Application Settings</CardTitle>
          <CardDescription>Functional Phase 1 settings stored locally.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-semibold">Theme</span>
            <select className="h-12 w-full rounded-xl border border-border bg-card px-3" value={preferences.theme} onChange={(event) => preferences.setPreference("theme", event.target.value as "system" | "light" | "dark")}>
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-sm font-semibold">API Endpoint</span>
            <input className="h-12 w-full rounded-xl border border-border bg-card px-3" value={preferences.apiEndpoint} onChange={(event) => preferences.setPreference("apiEndpoint", event.target.value)} />
          </label>
          <Toggle label="Notification Preferences" checked={preferences.notifications} onChange={(value) => preferences.setPreference("notifications", value)} />
          <Toggle label="Export Manifest Preference" checked={preferences.exportManifest} onChange={(value) => preferences.setPreference("exportManifest", value)} />
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-6">
          <p className="text-sm text-muted-foreground">Version</p>
          <p className="mt-1 text-3xl font-bold">v0.6.0</p>
        </CardContent>
      </Card>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <div className="flex h-12 items-center justify-between rounded-xl border border-border bg-card px-4">
      <span className="text-sm font-semibold">{label}</span>
      <button onClick={() => onChange(!checked)} className={`h-7 w-12 rounded-full p-1 transition ${checked ? "bg-primary" : "bg-border"}`}>
        <span className={`block h-5 w-5 rounded-full bg-white transition ${checked ? "translate-x-5" : ""}`} />
      </button>
    </div>
  );
}
