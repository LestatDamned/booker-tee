import { loadSession } from "../api/session";
import { loadImportMapping } from "../features/import-mapping/api/import-mapping-api";

export async function loadImportMappingRoute(
  documentId: string | undefined,
  signal?: AbortSignal,
) {
  if (!documentId) {
    return {
      mapping: { status: "not_found" as const },
      session: await loadSession(signal),
    };
  }
  const [session, mapping] = await Promise.all([
    loadSession(signal),
    loadImportMapping(documentId, signal),
  ]);
  return { mapping, session };
}
