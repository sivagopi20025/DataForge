import { cn } from "@/lib/utils";

export function QualityRing({ score, status }: { score: number; status: string }) {
  const safeScore = Math.max(0, Math.min(100, Math.round(score)));
  const color = safeScore >= 85 ? "text-success" : safeScore >= 70 ? "text-warning" : "text-danger";
  return (
    <div className="flex items-center gap-6">
      <div
        className="grid h-36 w-36 place-items-center rounded-full"
        style={{ background: `conic-gradient(currentColor ${safeScore * 3.6}deg, hsl(var(--muted)) 0deg)` }}
      >
        <div className="grid h-28 w-28 place-items-center rounded-full bg-card">
          <div className="text-center">
            <div className={cn("text-4xl font-bold", color)}>{safeScore}</div>
            <div className="text-xs font-semibold text-muted-foreground">QUALITY</div>
          </div>
        </div>
      </div>
      <div>
        <div className={cn("text-3xl font-bold", color)}>{status}</div>
        <p className="mt-2 max-w-sm text-sm text-muted-foreground">Weighted quality score from validation checks and business rules.</p>
      </div>
    </div>
  );
}
