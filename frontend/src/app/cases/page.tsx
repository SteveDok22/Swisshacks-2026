"use client";

import { useState } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { CaseQueue } from "@/components/cases/CaseQueue";
import { CaseDetailPanel } from "@/components/cases/CaseDetailPanel";
import { WelcomeModal } from "@/components/WelcomeModal";
import { DemoModeBadge } from "@/components/DemoModeBadge";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

/**
 * Main workspace — three-pane layout:
 *   [ Sidebar ] [ Case Queue ] [ Case Detail ]
 *
 * This is the compliance officer's primary screen.
 */
export default function Home() {
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  return (
    <div className="flex h-screen overflow-hidden relative z-10">
      <WelcomeModal />
      <DemoModeBadge />
      <Sidebar />

      {/* Case queue — fixed width middle column */}
      <div className="w-[420px] shrink-0 border-r border-paper-line bg-paper-raised">
        <CaseQueue
          selectedCaseId={selectedCaseId}
          onSelectCase={setSelectedCaseId}
        />
      </div>

      {/* Detail panel — flexible remaining space */}
      <main className="flex-1 min-w-0 bg-paper">
        <ErrorBoundary section="Case detail">
          <CaseDetailPanel caseId={selectedCaseId} />
        </ErrorBoundary>
      </main>
    </div>
  );
}
