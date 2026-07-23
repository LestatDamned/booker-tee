import { loadSession } from "../api/session";
import { loadImportDocuments } from "../features/import-documents/api/import-documents-api";

export async function loadImportDocumentsRoute(request: Request) {
  const search = importDocumentApiSearch(new URL(request.url).search);
  const [session, documents] = await Promise.all([
    loadSession(request.signal),
    loadImportDocuments(search, request.signal),
  ]);
  return { documents, session };
}

export function importDocumentApiSearch(currentSearch: string): string {
  const current = new URLSearchParams(currentSearch);
  const allowed = new URLSearchParams();
  for (const key of [
    "state",
    "account_id",
    "period_from",
    "period_to",
    "sort",
    "page",
    "per_page",
  ]) {
    const value = current.get(key);
    if (value) {
      allowed.set(key, value);
    }
  }
  return allowed.size > 0 ? `?${allowed.toString()}` : "";
}
