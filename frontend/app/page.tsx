import Link from "next/link";
import type React from "react";
import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  FileSearch,
  FlaskConical,
  Gauge,
  History,
  Layers3,
  ShieldCheck,
  Sparkles,
  Table2,
  Waves,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const featureCards = [
  {
    title: "Generate Datasets",
    description: "Create realistic domain datasets across Retail, Logistics, Healthcare, Finance, Insurance, and Banking.",
    href: "/generator",
    icon: Database,
    cta: "Open generator",
  },
  {
    title: "Select Tables & Formats",
    description: "Choose one table, selected tables, or all tables, then export CSV, JSON, or Parquet.",
    href: "/generator#dataset-setup",
    icon: Table2,
    cta: "Configure dataset",
  },
  {
    title: "Inject Quality Issues",
    description: "Add nulls, duplicates, malformed data, schema drift, late events, and data format mismatches.",
    href: "/generator#issues",
    icon: FlaskConical,
    cta: "Try issue injection",
  },
  {
    title: "Validate & Score",
    description: "Run standard validation reports with quality scores, checks, issues, and pass/fail status.",
    href: "/history",
    icon: ShieldCheck,
    cta: "Review results",
  },
  {
    title: "Preview & Download Files",
    description: "Inspect generated files in a table preview before downloading them for pipeline testing.",
    href: "/history",
    icon: Download,
    cta: "View generated runs",
  },
  {
    title: "Track Analytics",
    description: "Monitor usage, quality score trends, top domains, formats, load types, and API activity.",
    href: "/admin",
    icon: BarChart3,
    cta: "Open analytics",
  },
];

const useCases = [
  {
    title: "Data Engineering Pipeline Testing",
    description: "Generate source-like files, inject bad records, and verify that ETL, CDC, and warehouse jobs handle real-world data problems.",
    href: "/generator",
    icon: Layers3,
  },
  {
    title: "QA Validation Before Production",
    description: "Use repeatable generated data and validation reports to confirm expected rows, schemas, duplicates, null thresholds, and quality scores.",
    href: "/history",
    icon: CheckCircle2,
  },
  {
    title: "ML & Data Science Experimentation",
    description: "Create controlled datasets for feature engineering, drift testing, missing data handling, and model robustness checks.",
    href: "/generator",
    icon: Sparkles,
  },
  {
    title: "Training & Demo Workflows",
    description: "Produce safe, realistic sample datasets for classroom exercises, workshops, demos, and hands-on data platform training.",
    href: "/generator",
    icon: FileSearch,
  },
];

const workflow = [
  "Select domain",
  "Choose load type",
  "Pick format",
  "Select tables",
  "Set record count",
  "Inject issues",
  "Generate job",
  "Preview/download results",
];

const routeCards = [
  { label: "Data Generator", href: "/generator", icon: Database, status: "Ready" },
  { label: "Run History", href: "/history", icon: History, status: "Ready" },
  { label: "Admin Analytics", href: "/admin", icon: Gauge, status: "Ready" },
  { label: "Stream APIs", href: "/streams", icon: Waves, status: "Soon" },
  { label: "Test Packages", href: "/test-packages", icon: FlaskConical, status: "Soon" },
  { label: "Dashboards", href: "/dashboards", icon: BarChart3, status: "Soon" },
];

export default function HomePage() {
  return (
    <div className="space-y-8">
      <section className="overflow-hidden rounded-[2rem] border border-border bg-card shadow-sm">
        <div className="grid gap-8 p-8 lg:grid-cols-[1.25fr_0.75fr] lg:p-10">
          <div className="max-w-4xl">
            <Badge>DataForge v0.6.0 · Demo-ready backend foundation</Badge>
            <h1 className="mt-5 max-w-4xl text-4xl font-black tracking-tight md:text-6xl">
              Generate, break, validate, preview, and download enterprise test data.
            </h1>
            <p className="mt-5 max-w-3xl text-lg leading-8 text-muted-foreground">
              DataForge helps data engineers, data scientists, ML engineers, QA teams, students, and trainers create realistic synthetic data with controlled quality problems before pipelines reach production.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <PrimaryLink href="/generator">Start generating</PrimaryLink>
              <SecondaryLink href="#features">Explore features</SecondaryLink>
              <SecondaryLink href="/history">View run history</SecondaryLink>
            </div>
          </div>

          <Card className="bg-muted/40">
            <CardHeader>
              <CardTitle>Current platform scope</CardTitle>
              <CardDescription>What is already available in the app today.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {["6 enterprise domains", "CSV, JSON, Parquet exports", "Background generation jobs", "Validation reports + quality scores", "Run history + file preview", "Admin analytics APIs"].map((item) => (
                <div key={item} className="flex items-center gap-3 rounded-2xl bg-card px-4 py-3 text-sm font-semibold">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                  {item}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </section>

      <section id="features" className="space-y-4">
        <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
          <div>
            <Badge>Features</Badge>
            <h2 className="mt-3 text-3xl font-bold tracking-tight">Click into any capability</h2>
            <p className="mt-2 text-muted-foreground">Each card routes to the relevant DataForge screen.</p>
          </div>
          <SecondaryLink href="/generator">Open main workflow</SecondaryLink>
        </div>

        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {featureCards.map((feature) => (
            <FeatureCard key={feature.title} {...feature} />
          ))}
        </div>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <CardHeader>
            <Badge>Workflow</Badge>
            <CardTitle className="mt-2 text-2xl">From setup to usable files</CardTitle>
            <CardDescription>The core flow is intentionally short so users can generate test data quickly.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {workflow.map((step, index) => (
              <div key={step} className="flex items-center gap-3 rounded-2xl border border-border bg-muted/30 p-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">{index + 1}</div>
                <span className="font-semibold">{step}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <div>
            <Badge>Use cases</Badge>
            <h2 className="mt-3 text-3xl font-bold tracking-tight">Highlighted one by one</h2>
            <p className="mt-2 text-muted-foreground">Use these paths to explain the product to beta users and demo audiences.</p>
          </div>

          <div className="space-y-3">
            {useCases.map((useCase, index) => (
              <Link
                key={useCase.title}
                href={useCase.href}
                className="group grid gap-4 rounded-2xl border border-border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md md:grid-cols-[3.5rem_minmax(0,1fr)_auto]"
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <useCase.icon className="h-6 w-6" />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>Use case {index + 1}</Badge>
                    <h3 className="text-lg font-bold">{useCase.title}</h3>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{useCase.description}</p>
                </div>
                <ArrowRight className="hidden h-5 w-5 self-center text-muted-foreground transition group-hover:translate-x-1 group-hover:text-primary md:block" />
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div>
          <Badge>Navigation</Badge>
          <h2 className="mt-3 text-3xl font-bold tracking-tight">Go directly to a feature area</h2>
        </div>
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {routeCards.map((route) => (
            <Link key={route.href} href={route.href} className="group rounded-2xl border border-border bg-card p-5 shadow-sm transition hover:border-primary/50 hover:shadow-md">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary">
                    <route.icon className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-bold">{route.label}</p>
                    <p className="text-xs text-muted-foreground">{route.status === "Ready" ? "Available now" : "Placeholder for future phase"}</p>
                  </div>
                </div>
                <Badge>{route.status}</Badge>
              </div>
            </Link>
          ))}
        </div>
      </section>

      <section className="rounded-[2rem] border border-primary/20 bg-primary/10 p-6 md:p-8">
        <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
          <div>
            <div className="flex items-center gap-2 text-sm font-bold text-primary">
              <Clock3 className="h-4 w-4" />
              Recommended demo path
            </div>
            <h2 className="mt-2 text-2xl font-bold">Generate a small Healthcare JSON dataset, preview a table, then show the run history.</h2>
            <p className="mt-2 text-muted-foreground">This highlights generation, table selection, background jobs, preview, downloads, validation, and history in one smooth story.</p>
          </div>
          <PrimaryLink href="/generator">Run the demo</PrimaryLink>
        </div>
      </section>
    </div>
  );
}

function FeatureCard({
  title,
  description,
  href,
  icon: Icon,
  cta,
}: {
  title: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  cta: string;
}) {
  return (
    <Link href={href} className="group rounded-2xl border border-border bg-card p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-primary/50 hover:shadow-md">
      <div className="flex items-start justify-between gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Icon className="h-6 w-6" />
        </div>
        <ArrowRight className="h-5 w-5 text-muted-foreground transition group-hover:translate-x-1 group-hover:text-primary" />
      </div>
      <h3 className="mt-5 text-xl font-bold">{title}</h3>
      <p className="mt-2 min-h-16 text-sm leading-6 text-muted-foreground">{description}</p>
      <p className="mt-4 text-sm font-bold text-primary">{cta}</p>
    </Link>
  );
}

function PrimaryLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="inline-flex h-11 items-center justify-center rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground transition hover:opacity-90">
      {children}
      <ArrowRight className="ml-2 h-4 w-4" />
    </Link>
  );
}

function SecondaryLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link href={href} className="inline-flex h-11 items-center justify-center rounded-xl border border-border bg-card px-5 text-sm font-semibold transition hover:bg-muted">
      {children}
    </Link>
  );
}
