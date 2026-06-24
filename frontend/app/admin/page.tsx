import { AnalyticsDashboard } from "@/components/admin/analytics-dashboard";

export default function AdminPage() {
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-4xl font-bold tracking-tight">Admin Analytics</h1>
        <p className="mt-2 text-muted-foreground">Operational usage and quality analytics from the backend.</p>
      </header>
      <AnalyticsDashboard />
    </div>
  );
}
