import { ComingSoon } from "@/components/layout/coming-soon";

export default function TestPackagesPage() {
  return (
    <ComingSoon
      phase="Phase 3"
      title="Test Packages are coming soon"
      description="Package datasets, issues, validations, and assertions into reusable pipeline tests."
      features={["Scenarios", "Assertions", "Expected vs Actual", "Pipeline Validation"]}
    />
  );
}
