import { loadSession } from "../api/session";
import { loadImportReview } from "../features/import-review/api/import-review-api";

export async function loadImportReviewRoute(
  documentId: string,
  signal?: AbortSignal,
) {
  const [session, review] = await Promise.all([
    loadSession(signal),
    loadImportReview(documentId, signal),
  ]);
  return { session, review };
}
