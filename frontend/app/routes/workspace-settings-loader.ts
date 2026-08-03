import { loadSession } from "../api/session";
import { loadWorkspaceSettings } from "../features/workspaces/api/workspace-settings-api";

export async function loadWorkspaceSettingsRoute(
  request: Request,
  workspaceId: string,
) {
  const [session, settings] = await Promise.all([
    loadSession(request.signal),
    loadWorkspaceSettings(workspaceId, request.signal),
  ]);
  return { session, settings };
}
