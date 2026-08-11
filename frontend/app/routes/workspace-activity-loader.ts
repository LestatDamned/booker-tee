import { loadSession } from "../api/session";
import {
  loadWorkspaceActivity,
  type WorkspaceActivityScope,
} from "../features/workspaces/api/workspace-activity-api";

export async function loadWorkspaceActivityRoute(
  request: Request,
  workspaceId: string,
) {
  const scope = activityScope(new URL(request.url).searchParams.get("scope"));
  const [session, activity] = await Promise.all([
    loadSession(request.signal),
    loadWorkspaceActivity(workspaceId, undefined, request.signal, scope),
  ]);
  return { activity, scope, session, workspaceId };
}

function activityScope(value: string | null): WorkspaceActivityScope {
  return value === "finance" || value === "team" ? value : "all";
}
