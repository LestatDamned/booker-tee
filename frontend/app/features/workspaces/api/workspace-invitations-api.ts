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

export type WorkspaceInvitationsDto =
  components["schemas"]["WorkspaceInvitationsApiResponse"];
export type WorkspaceInvitationDto = WorkspaceInvitationsDto["items"][number];
export type PublicWorkspaceInvitationDto =
  components["schemas"]["PublicWorkspaceInvitationApiResponse"];

const invitationSchema: z.ZodType<WorkspaceInvitationDto> = z.object({
  id: z.uuid(),
  role: workspaceRoleSchema,
  status: z.enum(["pending", "accepted", "expired", "revoked"]),
  expiresAt: z.iso.datetime({ offset: true }),
  createdAt: z.iso.datetime({ offset: true }),
  updatedAt: z.iso.datetime({ offset: true }),
  capabilities: z.object({ canRevoke: z.boolean() }),
  blockingReasonCodes: z.array(
    z.enum([
      "workspace_inactive",
      "invitation_management_forbidden",
      "invitation_role_forbidden",
    ]),
  ),
});

const invitationsSchema: z.ZodType<WorkspaceInvitationsDto> = z.object({
  workspaceId: z.uuid(),
  items: z.array(invitationSchema),
  capabilities: z.object({
    canCreate: z.boolean(),
    assignableRoles: z.array(workspaceRoleSchema),
  }),
});

const createdInvitationSchema = z.object({
  invitation: invitationSchema,
  invitations: invitationsSchema,
  shareUrl: z.url(),
  replayed: z.boolean(),
});

const publicInvitationSchema: z.ZodType<PublicWorkspaceInvitationDto> =
  z.object({
    workspaceName: z.string(),
    role: workspaceRoleSchema,
    expiresAt: z.iso.datetime({ offset: true }),
  });

const acceptedInvitationSchema = z.object({
  navigationOutcome: z.object({
    kind: z.literal("workspace_changed"),
    href: z.literal("/app/workspaces"),
    boundary: z.literal("hard_reload"),
  }),
});

export type PublicWorkspaceInvitationLoadResult =
  | { status: "success"; invitation: PublicWorkspaceInvitationDto }
  | { status: "not_found" }
  | ApiLoadError;

export type AcceptPublicWorkspaceInvitationResult =
  | { status: "success"; href: "/app/workspaces" }
  | ApiUnauthenticatedFailure
  | { status: "not_found"; message: string }
  | ApiMutationError;

export type WorkspaceInvitationsLoadResult =
  | { status: "success"; invitations: WorkspaceInvitationsDto }
  | ApiUnauthenticatedFailure
  | { status: "not_found" }
  | ApiLoadError;

export type WorkspaceInvitationsMutationResult =
  | { status: "success"; invitations: WorkspaceInvitationsDto }
  | ApiUnauthenticatedFailure
  | { status: "not_found"; message: string }
  | { status: "conflict"; message: string }
  | ApiMutationError;

export async function loadWorkspaceInvitations(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<WorkspaceInvitationsLoadResult> {
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/invitations`,
    signal ? { signal } : undefined,
  );
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = invitationsSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", invitations: parsed.data }
    : apiLoadError("API вернул приглашения неожиданного формата.");
}

export async function loadPublicWorkspaceInvitation(
  invitationToken: string,
  signal?: AbortSignal,
): Promise<PublicWorkspaceInvitationLoadResult> {
  const response = await requestJson(
    `/api/v1/workspaces/invitations/${encodeURIComponent(invitationToken)}`,
    signal ? { signal } : undefined,
  );
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = publicInvitationSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", invitation: parsed.data }
    : apiLoadError("API вернул приглашение неожиданного формата.");
}

export async function acceptPublicWorkspaceInvitation({
  csrfToken,
  invitationToken,
}: {
  csrfToken: string;
  invitationToken: string;
}): Promise<AcceptPublicWorkspaceInvitationResult> {
  const response = await requestJson(
    `/api/v1/workspaces/invitations/${encodeURIComponent(invitationToken)}/accept`,
    {
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (response.httpStatus === 404) {
    return {
      status: "not_found",
      message: error?.message ?? "Приглашение уже недействительно.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "workspace_invitation_accept_failed",
      fallbackMessage: "Не удалось принять приглашение.",
    });
  }
  const parsed = acceptedInvitationSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", href: parsed.data.navigationOutcome.href }
    : apiMutationError(null, {
        fallbackCode: "invalid_workspace_invitation_accept_response",
        fallbackMessage: "API вернул неожиданный результат принятия.",
      });
}

export async function createWorkspaceInvitation({
  csrfToken,
  idempotencyKey,
  role,
  workspaceId,
}: {
  csrfToken: string;
  idempotencyKey: string;
  role: WorkspaceInvitationDto["role"];
  workspaceId: string;
}) {
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/invitations`,
    {
      body: JSON.stringify({ role }),
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
    },
  );
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (response.httpStatus === 404) {
    return {
      status: "not_found" as const,
      message: error?.message ?? "Пространство не найдено.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict" as const,
      message: error?.message ?? "Приглашение уже изменилось.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "workspace_invitation_create_failed",
      fallbackMessage: "Не удалось создать приглашение.",
    });
  }
  const parsed = createdInvitationSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success" as const, ...parsed.data }
    : apiMutationError(null, {
        fallbackCode: "invalid_workspace_invitation_response",
        fallbackMessage: "API вернул приглашение неожиданного формата.",
      });
}

export async function revokeWorkspaceInvitation({
  csrfToken,
  invitation,
  workspaceId,
}: {
  csrfToken: string;
  invitation: WorkspaceInvitationDto;
  workspaceId: string;
}): Promise<WorkspaceInvitationsMutationResult> {
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/invitations/${invitation.id}/revoke`,
    {
      body: JSON.stringify({ expectedUpdatedAt: invitation.updatedAt }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
    },
  );
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (response.httpStatus === 404) {
    return {
      status: "not_found",
      message: error?.message ?? "Приглашение не найдено.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: error?.message ?? "Приглашение уже изменилось.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "workspace_invitation_revoke_failed",
      fallbackMessage: "Не удалось отозвать приглашение.",
    });
  }
  const parsed = invitationsSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", invitations: parsed.data }
    : apiMutationError(null, {
        fallbackCode: "invalid_workspace_invitations_response",
        fallbackMessage: "API вернул приглашения неожиданного формата.",
      });
}
