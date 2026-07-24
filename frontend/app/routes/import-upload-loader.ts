import { loadSession } from "../api/session";
import { loadImportUploadReference } from "../features/import-upload/api/import-upload-api";

export async function loadImportUploadRoute(request: Request) {
  const [session, reference] = await Promise.all([
    loadSession(request.signal),
    loadImportUploadReference(request.signal),
  ]);
  return { reference, session };
}
