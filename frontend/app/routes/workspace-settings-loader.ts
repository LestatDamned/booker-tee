import { loadSession } from "../api/session";
import { loadWorkspaceSettings } from "../features/workspaces/api/workspace-settings-api";
import { loadWorkspaceMembers } from "../features/workspaces/api/workspace-members-api";

export async function loadWorkspaceSettingsRoute(
  request: Request,
  workspaceId: string,
) {
  const [session, settings, members] = await Promise.all([
    loadSession(request.signal),
    loadWorkspaceSettings(workspaceId, request.signal),
    loadWorkspaceMembers(workspaceId, request.signal),
  ]);
  return { session, settings, members };
}
