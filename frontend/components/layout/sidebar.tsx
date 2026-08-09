"use client";

import type React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, BookOpenCheck, Boxes, FlaskConical, Gauge, History, Home, Settings, SlidersHorizontal, Sparkles, Waves } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const primaryNav = [
  { href: "/", label: "Home", icon: Home },
  { href: "/generator", label: "Data Generator", icon: Boxes },
  { href: "/scenarios", label: "Scenario Library", icon: BookOpenCheck },
  { href: "/streams", label: "Stream APIs", icon: Waves },
  { href: "/test-packages", label: "Test Packages", icon: FlaskConical, soon: true },
  { href: "/dashboards", label: "Dashboards", icon: BarChart3, soon: true },
  { href: "/history", label: "Run History", icon: History },
  { href: "/admin", label: "Admin Analytics", icon: Gauge },
];

const secondaryNav = [
  { href: "/personalization", label: "Personalization", icon: SlidersHorizontal },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-[280px] overflow-hidden border-r border-border bg-white/88 px-4 py-5 backdrop-blur-xl lg:flex lg:flex-col">
      <Link href="/" className="flex items-center gap-3 rounded-2xl px-2 py-2">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-glow">
          <Sparkles className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="text-lg font-bold tracking-tight">DataForge</div>
          <div className="text-xs text-muted-foreground">Quality data workbench</div>
        </div>
      </Link>

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <div className="my-6 h-px bg-border" />
        <nav className="space-y-1">
          {primaryNav.map((item) => (
            <NavItem key={item.href} active={item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)} {...item} />
          ))}
        </nav>
        <div className="my-6 h-px bg-border" />
        <nav className="space-y-1">
          {secondaryNav.map((item) => (
            <NavItem key={item.href} active={pathname.startsWith(item.href)} {...item} />
          ))}
        </nav>
      </div>

      <div className="mt-4 shrink-0 rounded-2xl border border-border bg-muted/60 p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Version</p>
        <p className="mt-2 text-2xl font-bold">v0.9 beta</p>
        <p className="mt-1 text-xs text-muted-foreground">Batch + scenarios ready</p>
      </div>
    </aside>
  );
}

export function MobileNav() {
  const pathname = usePathname();
  const navItems = [...primaryNav, ...secondaryNav];

  return (
    <div className="sticky top-0 z-30 border-b border-border bg-white/90 px-4 py-3 backdrop-blur-xl lg:hidden">
      <div className="flex min-w-0 items-center gap-3">
        <Link href="/" className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-glow">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-base font-bold tracking-tight">DataForge</div>
            <div className="truncate text-xs text-muted-foreground">Quality data workbench</div>
          </div>
        </Link>
      </div>
      <nav className="mt-3 flex gap-2 overflow-x-auto pb-1 [-webkit-overflow-scrolling:touch]">
        {navItems.map((item) => (
          <MobileNavItem key={item.href} active={item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)} {...item} />
        ))}
      </nav>
    </div>
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
      <span className="flex min-w-0 items-center gap-3">
        <Icon className="h-4 w-4 shrink-0" />
        <span className="truncate">{label}</span>
      </span>
      {soon ? <Badge>Soon</Badge> : null}
    </Link>
  );
}

function MobileNavItem({
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
        "inline-flex h-10 shrink-0 items-center gap-2 rounded-xl border border-border bg-card px-3 text-xs font-semibold text-muted-foreground transition hover:text-foreground",
        active && "border-primary/30 bg-primary/10 text-primary",
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span>{label}</span>
      {soon ? <Badge>Soon</Badge> : null}
    </Link>
  );
}
