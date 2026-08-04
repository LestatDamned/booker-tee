import { z } from "zod";

import {
  apiLoadError,
  apiLoadNetworkError,
  apiMutationError,
  apiMutationNetworkError,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
  type ApiLoadError,
  type ApiMutationError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";
import { workspaceRoleSchema } from "./workspaces-api";

export type WorkspaceMembersDto =
  components["schemas"]["WorkspaceMembersApiResponse"];
export type WorkspaceMemberDto = WorkspaceMembersDto["items"][number];

const workspaceMembersSchema: z.ZodType<WorkspaceMembersDto> = z.object({
  workspaceId: z.uuid(),
  capabilities: z.object({ canManageMembers: z.boolean() }),
  items: z.array(
    z.object({
      id: z.uuid(),
      userId: z.uuid(),
      name: z.string().nullable(),
      email: z.email(),
      role: workspaceRoleSchema,
      status: z.enum(["pending", "active", "disabled", "removed"]),
      joinedAt: z.iso.datetime({ offset: true }).nullable(),
      updatedAt: z.iso.datetime({ offset: true }),
      isSelf: z.boolean(),
      capabilities: z.object({
        canUpdateRole: z.boolean(),
        canDisable: z.boolean(),
        canReactivate: z.boolean(),
        canTransferOwnership: z.boolean(),
        canLeave: z.boolean(),
        assignableRoles: z.array(workspaceRoleSchema),
      }),
      blockingReasonCodes: z.array(
        z.enum([
          "workspace_inactive",
          "member_self",
          "member_owner",
          "member_active",
          "member_disabled",
          "member_management_forbidden",
          "workspace_fallback_required",
        ]),
      ),
    }),
  ),
});

export type WorkspaceMembersLoadResult =
  | { status: "success"; members: WorkspaceMembersDto }
  | ApiUnauthenticatedFailure
  | { status: "not_found" }
  | ApiLoadError;

export type WorkspaceMembersMutationResult =
  | { status: "success"; members: WorkspaceMembersDto }
  | ApiUnauthenticatedFailure
  | { status: "not_found"; message: string }
  | { status: "conflict"; message: string }
  | ApiMutationError;

export async function loadWorkspaceMembers(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<WorkspaceMembersLoadResult> {
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/members`,
    signal ? { signal } : undefined,
  );
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = workspaceMembersSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", members: parsed.data }
    : apiLoadError("API вернул участников неожиданного формата.");
}

export async function updateWorkspaceMemberRole({
  csrfToken,
  member,
  role,
  workspaceId,
}: {
  csrfToken: string;
  member: WorkspaceMemberDto;
  role: WorkspaceMemberDto["role"];
  workspaceId: string;
}): Promise<WorkspaceMembersMutationResult> {
  return mutateMember(
    `/api/v1/workspaces/${workspaceId}/members/${member.id}/role`,
    csrfToken,
    "PUT",
    { role, expectedUpdatedAt: member.updatedAt },
  );
}

export async function transitionWorkspaceMember({
  action,
  csrfToken,
  member,
  workspaceId,
}: {
  action: "disable" | "reactivate";
  csrfToken: string;
  member: WorkspaceMemberDto;
  workspaceId: string;
}): Promise<WorkspaceMembersMutationResult> {
  return mutateMember(
    `/api/v1/workspaces/${workspaceId}/members/${member.id}/${action}`,
    csrfToken,
    "POST",
    { expectedUpdatedAt: member.updatedAt },
  );
}

export type WorkspaceBoundaryMutationResult =
  | { status: "success"; href: string; members?: WorkspaceMembersDto }
  | ApiUnauthenticatedFailure
  | { status: "not_found"; message: string }
  | { status: "conflict"; message: string }
  | ApiMutationError;

export async function transferWorkspaceOwnership({
  csrfToken,
  expectedWorkspaceUpdatedAt,
  member,
  workspaceId,
}: {
  csrfToken: string;
  expectedWorkspaceUpdatedAt: string;
  member: WorkspaceMemberDto;
  workspaceId: string;
}): Promise<WorkspaceBoundaryMutationResult> {
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/transfer-ownership`,
    {
      body: JSON.stringify({
        recipientMemberId: member.id,
        expectedWorkspaceUpdatedAt,
        expectedRecipientUpdatedAt: member.updatedAt,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
    },
  );
  return parseBoundaryMutation(response, true);
}

export async function leaveWorkspace({
  csrfToken,
  currentWorkspaceId,
  member,
  workspaceId,
}: {
  csrfToken: string;
  currentWorkspaceId: string;
  member: WorkspaceMemberDto;
  workspaceId: string;
}): Promise<WorkspaceBoundaryMutationResult> {
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/leave`,
    {
      body: JSON.stringify({
        expectedMemberUpdatedAt: member.updatedAt,
        expectedCurrentWorkspaceId: currentWorkspaceId,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
    },
  );
  return parseBoundaryMutation(response, false);
}

async function mutateMember(
  href: string,
  csrfToken: string,
  method: "POST" | "PUT",
  body: object,
): Promise<WorkspaceMembersMutationResult> {
  const response = await requestJson(href, {
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method,
  });
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (response.httpStatus === 404) {
    return {
      status: "not_found",
      message: error?.message ?? "Участник не найден.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: error?.message ?? "Участник уже изменён.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "workspace_member_update_failed",
      fallbackMessage: "Не удалось изменить доступ участника.",
    });
  }
  const parsed = workspaceMembersSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", members: parsed.data }
    : apiMutationError(null, {
        fallbackCode: "invalid_workspace_members_response",
        fallbackMessage: "API вернул участников неожиданного формата.",
      });
}

function parseBoundaryMutation(
  response: Awaited<ReturnType<typeof requestJson>>,
  includeMembers: boolean,
): WorkspaceBoundaryMutationResult {
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (response.httpStatus === 404) {
    return {
      status: "not_found",
      message: error?.message ?? "Пространство или участник не найдены.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: error?.message ?? "Состояние пространства уже изменилось.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "workspace_authority_update_failed",
      fallbackMessage: "Не удалось изменить доступ к пространству.",
    });
  }
  const payload = response.body as {
    members?: unknown;
    navigationOutcome?: { href?: unknown };
  };
  const href = payload.navigationOutcome?.href;
  const parsedMembers = includeMembers
    ? workspaceMembersSchema.safeParse(payload.members)
    : null;
  if (typeof href !== "string" || (parsedMembers && !parsedMembers.success)) {
    return apiMutationError(null, {
      fallbackCode: "invalid_workspace_authority_response",
      fallbackMessage: "API вернул результат неожиданного формата.",
    });
  }
  return {
    status: "success",
    href,
    ...(parsedMembers?.success ? { members: parsedMembers.data } : {}),
  };
}
