import { CheckCircle2, Loader2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";

const steps = ["Generating", "Injecting Issues", "Validating", "Exporting", "Saving Metadata", "Completed"];

export function GenerationProgress({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <div className="rounded-3xl border border-border bg-card p-5 shadow-glow">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-semibold">Generation in progress</p>
          <p className="text-sm text-muted-foreground">DataForge is running the backend workflow.</p>
        </div>
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
      </div>
      <Progress value={72} className="mt-4" />
      <div className="mt-4 grid gap-2 md:grid-cols-3">
        {steps.map((step, index) => (
          <div key={step} className="flex items-center gap-2 text-sm text-muted-foreground">
            {index < 3 ? <CheckCircle2 className="h-4 w-4 text-success" /> : <Loader2 className="h-4 w-4 animate-spin text-primary" />}
            {step}
          </div>
        ))}
      </div>
    </div>
  );
}
