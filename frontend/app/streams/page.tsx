import { ComingSoon } from "@/components/layout/coming-soon";

export default function StreamsPage() {
  return (
    <ComingSoon
      phase="Phase 2"
      title="Stream APIs are coming soon"
      description="The next phase will expose generated event streams through production-like API surfaces."
      features={["IoT Streams", "Tracking Events", "Claim Events", "Transaction Events", "Review Events", "Feedback Events"]}
    />
  );
}
