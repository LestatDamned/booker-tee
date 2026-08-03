import { loadSession } from "../api/session";
import { loadWorkspaces } from "../features/workspaces/api/workspaces-api";

export async function loadWorkspacesRoute(request: Request) {
  const [session, workspaces] = await Promise.all([
    loadSession(request.signal),
    loadWorkspaces(request.signal),
  ]);
  return { session, workspaces };
}
