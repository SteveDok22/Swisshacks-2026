import { DriftWorkspace } from "@/components/drift/DriftWorkspace";

/**
 * Deep-linkable Drift Engine view — `/drift/<drift_id>`.
 *
 * The selected customer is read from the route by `DriftWorkspace` (via
 * `useParams`), so a case can be shared and cross-referenced against the
 * audit trail by id.
 */
export default function DriftCustomerPage() {
  return <DriftWorkspace />;
}
