import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export function ComingSoon({ phase, title, description, features }: { phase: string; title: string; description: string; features: string[] }) {
  return (
    <div className="grid min-h-[calc(100vh-4rem)] place-items-center">
      <Card className="max-w-3xl overflow-hidden">
        <CardContent className="p-10">
          <Badge>{phase}</Badge>
          <h1 className="mt-5 text-5xl font-bold tracking-tight">{title}</h1>
          <p className="mt-4 text-lg text-muted-foreground">{description}</p>
          <div className="mt-8 grid gap-3 md:grid-cols-2">
            {features.map((feature) => (
              <div key={feature} className="rounded-2xl border border-border bg-muted/40 p-4 font-medium">{feature}</div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
