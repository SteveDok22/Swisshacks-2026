"use client";

import { cn } from "@/lib/utils";
import {
  LayoutGrid,
  ShieldAlert,
  FileSearch,
  Scale,
  Settings,
} from "lucide-react";
import { useState } from "react";

const NAV_ITEMS = [
  { id: "queue", label: "Case Queue", icon: LayoutGrid, active: true },
  { id: "alerts", label: "Live Alerts", icon: ShieldAlert, active: false },
  { id: "audit", label: "Audit Log", icon: FileSearch, active: false },
  { id: "jurisdictions", label: "Jurisdictions", icon: Scale, active: false },
];

/**
 * Left sidebar navigation.
 *
 * Design: narrow, icon-forward, with the AMINA-style wordmark up top.
 * The active state uses a left-edge accent bar — a precise, Swiss touch.
 */
export function Sidebar() {
  const [active, setActive] = useState("queue");

  return (
    <aside className="w-60 shrink-0 border-r border-paper-line bg-paper-raised flex flex-col">
      {/* Wordmark */}
      <div className="h-16 flex items-center px-5 border-b border-paper-line">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded bg-accent flex items-center justify-center">
            <span className="text-paper-raised font-semibold text-sm">S</span>
          </div>
          <div className="leading-tight">
            <div className="font-semibold text-sm text-ink">Sentinel</div>
            <div className="text-2xs text-ink-muted">Risk Intelligence</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActive(item.id)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2 rounded text-sm font-medium relative transition-colors",
                isActive
                  ? "bg-accent-bg text-accent"
                  : "text-ink-soft hover:bg-paper-sunken hover:text-ink",
              )}
            >
              {isActive && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-r bg-accent" />
              )}
              <Icon className="h-4 w-4 shrink-0" strokeWidth={2} />
              {item.label}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-3 py-4 border-t border-paper-line">
        <button className="w-full flex items-center gap-3 px-3 py-2 rounded text-sm font-medium text-ink-soft hover:bg-paper-sunken hover:text-ink transition-colors">
          <Settings className="h-4 w-4" strokeWidth={2} />
          Settings
        </button>
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
