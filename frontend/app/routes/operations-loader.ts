import { loadSession } from "../api/session";
import { loadOperations } from "../features/operations/api/operations-api";

export async function loadOperationsRoute(request: Request) {
  const search = operationsApiSearch(new URL(request.url).search);
  const [session, operations] = await Promise.all([
    loadSession(request.signal),
    loadOperations(search, request.signal),
  ]);
  return { operations, session };
}

export function operationsApiSearch(currentSearch: string): string {
  const search = new URLSearchParams(currentSearch);
  search.delete("layout");
  return search.size > 0 ? `?${search.toString()}` : "";
}
