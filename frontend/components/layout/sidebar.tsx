"use client";

import type React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Boxes, FlaskConical, Gauge, Settings, SlidersHorizontal, Sparkles, Waves } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const primaryNav = [
  { href: "/generator", label: "Data Generator", icon: Boxes },
  { href: "/streams", label: "Stream APIs", icon: Waves, soon: true },
  { href: "/test-packages", label: "Test Packages", icon: FlaskConical, soon: true },
  { href: "/dashboards", label: "Dashboards", icon: BarChart3, soon: true },
  { href: "/admin", label: "Admin Analytics", icon: Gauge },
];

const secondaryNav = [
  { href: "/personalization", label: "Personalization", icon: SlidersHorizontal },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-[280px] border-r border-border bg-white/88 px-4 py-5 backdrop-blur-xl lg:flex lg:flex-col">
      <Link href="/generator" className="flex items-center gap-3 rounded-2xl px-2 py-2">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-glow">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <div className="text-lg font-bold tracking-tight">DataForge</div>
          <div className="text-xs text-muted-foreground">Quality data workbench</div>
        </div>
      </Link>

      <div className="my-6 h-px bg-border" />
      <nav className="space-y-1">
        {primaryNav.map((item) => (
          <NavItem key={item.href} active={pathname.startsWith(item.href)} {...item} />
        ))}
      </nav>
      <div className="my-6 h-px bg-border" />
      <nav className="space-y-1">
        {secondaryNav.map((item) => (
          <NavItem key={item.href} active={pathname.startsWith(item.href)} {...item} />
        ))}
      </nav>
      <div className="mt-auto rounded-2xl border border-border bg-muted/60 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Version</p>
        <p className="mt-2 text-2xl font-bold">v0.6.0</p>
        <p className="mt-1 text-xs text-muted-foreground">Backend foundation complete</p>
      </div>
    </aside>
  );
}

function NavItem({
  href,
  label,
  icon: Icon,
  soon,
  active,
}: {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  soon?: boolean;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center justify-between rounded-2xl px-3 py-3 text-sm font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground",
        active && "bg-primary/10 text-primary",
      )}
    >
      <span className="flex items-center gap-3">
        <Icon className="h-4 w-4" />
        {label}
      </span>
      {soon ? <Badge>Soon</Badge> : null}
    </Link>
  );
}
