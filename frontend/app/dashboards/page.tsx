import { ComingSoon } from "@/components/layout/coming-soon";

export default function DashboardsPage() {
  return (
    <ComingSoon
      phase="Phase 4"
      title="Dashboards are coming soon"
      description="Operational and business views will sit here once Phase 1 generation is fully productized."
      features={["Business KPIs", "Validation Trends", "Quality Analytics", "Usage Analytics"]}
    />
  );
}
