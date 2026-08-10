import { z } from "zod";

import {
  apiLoadError,
  apiLoadNetworkError,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
  type ApiLoadError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import type { components } from "../../../api/generated/schema";
import { requestJson } from "../../../api/transport";
import { workspaceRoleSchema, workspaceTypeSchema } from "./workspaces-api";

export type WorkspaceActivityDto =
  components["schemas"]["WorkspaceActivityApiResponse"];
export type WorkspaceActivityItemDto = WorkspaceActivityDto["items"][number];
export type WorkspaceActivityCursorDto = NonNullable<
  WorkspaceActivityDto["nextCursor"]
>;

const eventTypeSchema = z.enum([
  "workspace_created",
  "workspace_updated",
  "workspace_deactivated",
  "workspace_restored",
  "invitation_created",
  "invitation_accepted",
  "invitation_revoked",
  "member_role_changed",
  "member_disabled",
  "member_reactivated",
  "member_left",
  "ownership_transferred",
]);
const memberStatusSchema = z.enum(["pending", "active", "disabled", "removed"]);
const actorSchema = z.object({ id: z.uuid(), displayName: z.string() });
const cursorSchema = z.object({
  beforeCreatedAt: z.iso.datetime({ offset: true }),
  beforeId: z.uuid(),
});

export const workspaceActivitySchema: z.ZodType<WorkspaceActivityDto> =
  z.object({
    workspaceId: z.uuid(),
    items: z.array(
      z.object({
        id: z.uuid(),
        eventType: eventTypeSchema,
        actor: actorSchema.nullable(),
        target: actorSchema.nullable(),
        summaryCode: eventTypeSchema,
        details: z.object({
          role: workspaceRoleSchema.nullable(),
          inviteeEmail: z.string().nullable(),
          oldRole: workspaceRoleSchema.nullable(),
          newRole: workspaceRoleSchema.nullable(),
          oldStatus: memberStatusSchema.nullable(),
          newStatus: memberStatusSchema.nullable(),
          oldName: z.string().nullable(),
          newName: z.string().nullable(),
          oldType: workspaceTypeSchema.nullable(),
          newType: workspaceTypeSchema.nullable(),
          oldDefaultCurrency: z.string().nullable(),
          newDefaultCurrency: z.string().nullable(),
          movedSessionCount: z.number().int().nonnegative().nullable(),
          revokedInvitationCount: z.number().int().nonnegative().nullable(),
        }),
        createdAt: z.iso.datetime({ offset: true }),
      }),
    ),
    nextCursor: cursorSchema.nullable(),
  });

export type WorkspaceActivityLoadResult =
  | { status: "success"; activity: WorkspaceActivityDto }
  | ApiUnauthenticatedFailure
  | { status: "forbidden" | "not_found"; message: string }
  | ApiLoadError;

export async function loadWorkspaceActivity(
  workspaceId: string,
  cursor?: WorkspaceActivityCursorDto,
  signal?: AbortSignal,
): Promise<WorkspaceActivityLoadResult> {
  const search = new URLSearchParams();
  if (cursor) {
    search.set("beforeCreatedAt", cursor.beforeCreatedAt);
    search.set("beforeId", cursor.beforeId);
  }
  const suffix = search.size ? `?${search}` : "";
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/activity${suffix}`,
    signal ? { signal } : undefined,
  );
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 403) {
    return { status: "forbidden", message: "Активность workspace недоступна." };
  }
  if (response.httpStatus === 404) {
    return { status: "not_found", message: "Workspace больше недоступен." };
  }
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = workspaceActivitySchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", activity: parsed.data }
    : apiLoadError("API вернул активность workspace неожиданного формата.");
}
