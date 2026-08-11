import { loadSession } from "../api/session";
import { loadWorkspaceSettings } from "../features/workspaces/api/workspace-settings-api";
import { loadWorkspaceMembers } from "../features/workspaces/api/workspace-members-api";
import { loadWorkspaceInvitations } from "../features/workspaces/api/workspace-invitations-api";

export async function loadWorkspaceSettingsRoute(
  request: Request,
  workspaceId: string,
) {
  const [session, settings] = await Promise.all([
    loadSession(request.signal),
    loadWorkspaceSettings(workspaceId, request.signal),
  ]);
  if (settings.status !== "success") {
    return {
      session,
      settings,
      members: null,
      invitations: null,
    };
  }
  const canViewTeam =
    settings.settings.workspace.capabilities.canViewMemberDirectory;
  const team = canViewTeam
    ? await Promise.all([
        loadWorkspaceMembers(workspaceId, request.signal),
        loadWorkspaceInvitations(workspaceId, request.signal),
      ])
    : null;
  return {
    session,
    settings,
    members: team?.[0] ?? null,
    invitations: team?.[1] ?? null,
  };
}
