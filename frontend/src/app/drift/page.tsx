import { DriftWorkspace } from "@/components/drift/DriftWorkspace";

/**
 * Drift Engine index — lands here, then auto-selects the highest-risk
 * customer and reflects it in the URL (`/drift/<drift_id>`).
 */
export default function DriftPage() {
  return <DriftWorkspace />;
}
