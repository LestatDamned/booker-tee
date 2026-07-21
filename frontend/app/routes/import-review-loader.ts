import { loadSession } from "../api/session";
import { loadImportReview } from "../features/import-review/api/import-review-api";

export async function loadImportReviewRoute(documentId: string) {
  const [session, review] = await Promise.all([
    loadSession(),
    loadImportReview(documentId),
  ]);
  return { session, review };
}
