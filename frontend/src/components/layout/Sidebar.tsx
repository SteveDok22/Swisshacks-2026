"use client";

import { cn } from "@/lib/utils";
import {
  LayoutGrid,
  ShieldAlert,
  FileSearch,
  Scale,
  Settings,
  Info,
  Activity,
} from "lucide-react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";

interface NavItem {
  id: string;
  label: string;
  icon: typeof LayoutGrid;
  active: boolean;
  enabled: boolean;
  href?: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    id: "queue",
    label: "Case Queue",
    icon: LayoutGrid,
    active: false,
    enabled: true,
    href: "/",
  },
  {
    id: "drift",
    label: "Drift Engine",
    icon: Activity,
    active: false,
    enabled: true,
    href: "/drift",
  },
  {
    id: "audit",
    label: "Audit Log",
    icon: FileSearch,
    active: false,
    enabled: true,
    href: "/audit",
  },
  {
    id: "alerts",
    label: "Live Alerts",
    icon: ShieldAlert,
    active: false,
    enabled: false,
  },
  {
    id: "jurisdictions",
    label: "Jurisdictions",
    icon: Scale,
    active: false,
    enabled: false,
  },
];

/**
 * Left sidebar navigation.
 *
 * MVP scope: only Case Queue is functional. Other nav items are
 * deliberately disabled with a "Soon" badge — honest about scope
 * rather than fake-interactive buttons that lead nowhere.
 *
 * Each disabled item has a tooltip on hover explaining what it will be.
 */
export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 shrink-0 border-r border-paper-line bg-paper-raised flex flex-col">
      {/* Wordmark */}
      <Link
        href="/"
        className="h-16 flex items-center px-5 border-b border-paper-line hover:bg-paper-sunken transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <Image
            src="/assets/logo.png"
            alt="Sentinel logo"
            width={28}
            height={28}
            className="h-7 w-7 rounded object-contain"
            priority
          />
          <div className="leading-tight">
            <div className="font-semibold text-sm text-ink">Sentinel</div>
            <div className="text-2xs text-ink-muted">Risk Intelligence</div>
          </div>
        </div>
      </Link>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = item.href === pathname;

          if (!item.enabled) {
            return (
              <div
                key={item.id}
                title="Coming soon — backend APIs ready, UI in development"
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 rounded text-sm",
                  "text-ink-faint cursor-not-allowed select-none",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" strokeWidth={2} />
                <span className="flex-1">{item.label}</span>
                <span className="text-2xs px-1.5 py-0.5 rounded bg-paper-sunken text-ink-muted font-medium">
                  Soon
                </span>
              </div>
            );
          }

          if (isActive) {
            return (
              <Link
                key={item.id}
                href={item.href ?? "/"}
                className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm font-medium relative bg-accent-bg text-accent"
              >
                <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-r bg-accent" />
                <Icon className="h-4 w-4 shrink-0" strokeWidth={2} />
                {item.label}
              </Link>
            );
          }

          return (
            <Link
              key={item.id}
              href={item.href ?? "/"}
              className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm font-medium text-ink-soft hover:bg-paper-sunken hover:text-ink transition-colors"
            >
              <Icon className="h-4 w-4 shrink-0" strokeWidth={2} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-paper-line">
        <Link
          href="/about"
          className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm font-medium text-ink-soft hover:bg-paper-sunken hover:text-ink transition-colors"
        >
          <Info className="h-4 w-4" strokeWidth={2} />
          About Sentinel
        </Link>
        <div
          title="Coming soon"
          className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm font-medium text-ink-faint cursor-not-allowed select-none"
        >
          <Settings className="h-4 w-4" strokeWidth={2} />
          Settings
        </div>
        <div className="mt-3 px-3 flex items-center gap-2">
          <div className="h-7 w-7 rounded-full bg-paper-sunken flex items-center justify-center">
            <span className="text-2xs font-semibold text-ink-soft">AM</span>
          </div>
          <div className="leading-tight">
            <div className="text-xs font-medium text-ink">Anna Müller</div>
            <div className="text-2xs text-ink-muted">Compliance Officer</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
