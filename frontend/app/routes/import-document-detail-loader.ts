import { loadSession } from "../api/session";
import { loadImportDocumentDetail } from "../features/import-document-detail/api/import-document-detail-api";

export async function loadImportDocumentDetailRoute(
  documentId: string | undefined,
  signal?: AbortSignal,
) {
  if (!documentId) {
    return {
      document: { status: "not_found" as const },
      session: await loadSession(signal),
    };
  }
  const [session, document] = await Promise.all([
    loadSession(signal),
    loadImportDocumentDetail(documentId, signal),
  ]);
  return { document, session };
}
