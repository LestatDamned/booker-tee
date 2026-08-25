import { loadSession } from "../api/session";
import { loadCoordinateOverview } from "../features/import-coordinate-mapping/api";

export async function loadImportCoordinateMappingRoute(
  documentId: string | undefined,
  signal?: AbortSignal,
) {
  if (!documentId)
    return {
      overview: { status: "not_found" as const },
      session: await loadSession(signal),
    };
  const [session, overview] = await Promise.all([
    loadSession(signal),
    loadCoordinateOverview(documentId, signal),
  ]);
  return { overview, session };
}
