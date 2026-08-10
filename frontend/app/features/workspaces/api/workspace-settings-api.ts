import { z } from "zod";

import {
  apiForbiddenFailure,
  apiLoadError,
  apiLoadNetworkError,
  apiMutationError,
  apiMutationNetworkError,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
  type ApiForbiddenFailure,
  type ApiLoadError,
  type ApiMutationError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import type { components } from "../../../api/generated/schema";
import { sessionSchema } from "../../../api/session-schema";
import { parseApiError, requestJson } from "../../../api/transport";
import { workspaceRoleSchema, workspaceTypeSchema } from "./workspaces-api";

export type WorkspaceSettingsDto =
  components["schemas"]["WorkspaceSettingsApiResponse"];
export type WorkspaceSettingsDraft = {
  name: string;
  workspaceType: WorkspaceSettingsDto["workspace"]["type"];
  defaultCurrency: string;
};

export const workspaceSettingsSchema: z.ZodType<WorkspaceSettingsDto> =
  z.object({
    workspace: z.object({
      id: z.uuid(),
      name: z.string(),
      type: workspaceTypeSchema,
      defaultCurrency: z.string().length(3),
      isActive: z.boolean(),
      archivedAt: z.iso.datetime({ offset: true }).nullable(),
      updatedAt: z.iso.datetime({ offset: true }),
      membership: z.object({
        role: workspaceRoleSchema,
        status: z.enum(["pending", "active", "disabled", "removed"]),
        updatedAt: z.iso.datetime({ offset: true }),
      }),
      capabilities: z.object({
        canUpdate: z.boolean(),
        canViewMemberDirectory: z.boolean(),
        canViewWorkspaceActivity: z.boolean(),
        canManageMembers: z.boolean(),
        canInvite: z.boolean(),
        canDeactivate: z.boolean(),
        canRestore: z.boolean(),
      }),
      blockingReasonCodes: z.array(
        z.enum([
          "workspace_current",
          "workspace_inactive",
          "workspace_fallback_required",
        ]),
      ),
    }),
    workspaceTypeOptions: z.array(
      z.object({ value: z.string(), label: z.string() }),
    ),
    currencyOptions: z.array(
      z.object({ value: z.string().length(3), label: z.string() }),
    ),
    lifecycleImpact: z
      .object({
        financialHistoryPreserved: z.boolean(),
        currentSessionCount: z.number().int().nonnegative(),
        pendingInvitationCount: z.number().int().nonnegative(),
        activeIntegrationConnectionCount: z.number().int().nonnegative(),
        activeChatIdentityBindingCount: z.number().int().nonnegative(),
      })
      .nullable(),
  });

export type WorkspaceSettingsLoadResult =
  | { status: "success"; settings: WorkspaceSettingsDto }
  | ApiUnauthenticatedFailure
  | { status: "not_found" }
  | ApiLoadError;

export type WorkspaceSettingsUpdateResult =
  | { status: "success"; settings: WorkspaceSettingsDto }
  | ApiUnauthenticatedFailure
  | ApiForbiddenFailure
  | { status: "not_found"; message: string }
  | { status: "conflict"; message: string }
  | ApiMutationError;

export type WorkspaceLifecycleMutationResult =
  | { status: "success"; href: "/app/workspaces" }
  | ApiUnauthenticatedFailure
  | { status: "not_found"; message: string }
  | { status: "conflict"; message: string }
  | { status: "blocked"; message: string; reasonCodes: string[] }
  | ApiMutationError;

const workspaceLifecycleResponseSchema = z.object({
  session: sessionSchema,
  impact: z.object({
    movedSessionCount: z.number().int().nonnegative(),
    revokedInvitationCount: z.number().int().nonnegative(),
    disabledIntegrationConnectionCount: z.number().int().nonnegative(),
    disabledChatConversationBindingCount: z.number().int().nonnegative(),
    disabledChatIdentityBindingCount: z.number().int().nonnegative(),
    consumedChatConversationStateCount: z.number().int().nonnegative(),
    failedIntegrationDeliveryCount: z.number().int().nonnegative(),
  }),
  navigationOutcome: z.object({
    kind: z.literal("workspace_changed"),
    href: z.literal("/app/workspaces"),
    boundary: z.literal("hard_reload"),
  }),
});

export async function loadWorkspaceSettings(
  workspaceId: string,
  signal?: AbortSignal,
): Promise<WorkspaceSettingsLoadResult> {
  const response = await requestJson(`/api/v1/workspaces/${workspaceId}`, {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = workspaceSettingsSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", settings: parsed.data }
    : apiLoadError("API вернул настройки workspace неожиданного формата.");
}

export async function updateWorkspaceSettings({
  csrfToken,
  draft,
  expectedUpdatedAt,
  workspaceId,
}: {
  csrfToken: string;
  draft: WorkspaceSettingsDraft;
  expectedUpdatedAt: string;
  workspaceId: string;
}): Promise<WorkspaceSettingsUpdateResult> {
  const response = await requestJson(`/api/v1/workspaces/${workspaceId}`, {
    body: JSON.stringify({ ...draft, expectedUpdatedAt }),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    method: "PUT",
  });
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return apiForbiddenFailure(error, "Изменение workspace недоступно.");
  }
  if (response.httpStatus === 404) {
    return {
      status: "not_found",
      message: error?.message ?? "Пространство не найдено.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: error?.message ?? "Workspace уже изменён. Обновите данные.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "workspace_update_failed",
      fallbackMessage: "Не удалось сохранить настройки workspace.",
    });
  }
  const parsed = workspaceSettingsSchema.safeParse(response.body);
  if (!parsed.success) {
    return apiMutationError(null, {
      fallbackCode: "invalid_workspace_settings_response",
      fallbackMessage: "API вернул настройки неожиданного формата.",
    });
  }
  return { status: "success", settings: parsed.data };
}

export async function transitionWorkspaceLifecycle({
  action,
  csrfToken,
  expectedCurrentWorkspaceId,
  expectedWorkspaceUpdatedAt,
  workspaceId,
}: {
  action: "deactivate" | "restore";
  csrfToken: string;
  expectedCurrentWorkspaceId: string;
  expectedWorkspaceUpdatedAt: string;
  workspaceId: string;
}): Promise<WorkspaceLifecycleMutationResult> {
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/${action}`,
    {
      body: JSON.stringify({
        expectedCurrentWorkspaceId,
        expectedWorkspaceUpdatedAt,
      }),
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
      message: error?.message ?? "Пространство не найдено.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: error?.message ?? "Состояние пространства уже изменилось.",
    };
  }
  if (
    response.httpStatus === 422 &&
    error?.code === "workspace_lifecycle_blocked"
  ) {
    const reasonCodes = Array.isArray(error.details?.reasonCodes)
      ? error.details.reasonCodes.filter(
          (value): value is string => typeof value === "string",
        )
      : [];
    return { status: "blocked", message: error.message, reasonCodes };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "workspace_lifecycle_failed",
      fallbackMessage: "Не удалось изменить состояние пространства.",
    });
  }
  const parsed = workspaceLifecycleResponseSchema.safeParse(response.body);
  if (!parsed.success) {
    return apiMutationError(null, {
      fallbackCode: "invalid_workspace_lifecycle_response",
      fallbackMessage: "API вернул результат неожиданного формата.",
    });
  }
  return { status: "success", href: parsed.data.navigationOutcome.href };
}
