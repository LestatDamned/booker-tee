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
import { sessionSchema } from "../../../api/session-schema";
import { parseApiError, requestJson } from "../../../api/transport";

export type WorkspaceDirectoryDto =
  components["schemas"]["WorkspaceDirectoryApiResponse"];
export type WorkspaceDirectoryItemDto =
  components["schemas"]["WorkspaceDirectoryItemApiResponse"];
export type WorkspaceType = WorkspaceDirectoryItemDto["type"];

const workspaceTypeSchema = z.enum([
  "personal",
  "family",
  "business",
  "property_management",
  "project",
  "other",
]);
const workspaceRoleSchema = z.enum([
  "owner",
  "admin",
  "editor",
  "viewer",
  "uploader",
  "analyst",
]);

const workspaceItemSchema: z.ZodType<WorkspaceDirectoryItemDto> = z.object({
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
  isCurrent: z.boolean(),
  capabilities: z.object({
    canSelect: z.boolean(),
    canUpdate: z.boolean(),
    canManageMembers: z.boolean(),
    canInvite: z.boolean(),
    canLeave: z.boolean(),
    canDeactivate: z.boolean(),
    canRestore: z.boolean(),
  }),
  blockingReasonCodes: z.array(
    z.enum(["workspace_current", "workspace_inactive"]),
  ),
});

export const workspaceDirectorySchema: z.ZodType<WorkspaceDirectoryDto> =
  z.object({
    currentWorkspaceId: z.uuid(),
    items: z.array(workspaceItemSchema),
    capabilities: z.object({ canCreate: z.boolean() }),
    workspaceTypeOptions: z.array(
      z.object({ value: z.string(), label: z.string() }),
    ),
    currencyOptions: z.array(
      z.object({ value: z.string().length(3), label: z.string() }),
    ),
  });

const navigationOutcomeSchema = z.object({
  kind: z.literal("workspace_changed"),
  href: z.literal("/app/workspaces"),
  boundary: z.literal("hard_reload"),
});

const createResponseSchema = z.object({
  workspace: workspaceItemSchema,
  session: sessionSchema,
  navigationOutcome: navigationOutcomeSchema,
  replayed: z.boolean(),
});

const selectResponseSchema = z.object({
  session: sessionSchema,
  navigationOutcome: navigationOutcomeSchema,
});

export type WorkspaceDirectoryLoadResult =
  | { status: "success"; directory: WorkspaceDirectoryDto }
  | ApiUnauthenticatedFailure
  | ApiLoadError;

export type CreateWorkspaceDraft = {
  name: string;
  workspaceType: WorkspaceType;
  defaultCurrency: string;
};

export type CreateWorkspaceResult =
  | {
      status: "success";
      href: "/app/workspaces";
      workspace: WorkspaceDirectoryItemDto;
    }
  | ApiUnauthenticatedFailure
  | { status: "conflict"; message: string }
  | ApiMutationError;

export type SelectWorkspaceResult =
  | { status: "success"; href: "/app/workspaces" }
  | ApiUnauthenticatedFailure
  | { status: "not_found"; message: string }
  | { status: "conflict"; message: string }
  | ApiMutationError;

export async function loadWorkspaces(
  signal?: AbortSignal,
): Promise<WorkspaceDirectoryLoadResult> {
  const response = await requestJson("/api/v1/workspaces", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = workspaceDirectorySchema.safeParse(response.body);
  if (!parsed.success) {
    return apiLoadError("API вернул пространства неожиданного формата.");
  }
  return { status: "success", directory: parsed.data };
}

export async function createWorkspace({
  csrfToken,
  draft,
  idempotencyKey,
}: {
  csrfToken: string;
  draft: CreateWorkspaceDraft;
  idempotencyKey: string;
}): Promise<CreateWorkspaceResult> {
  const response = await requestJson("/api/v1/workspaces", {
    body: JSON.stringify(draft),
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      "X-CSRF-Token": csrfToken,
    },
    method: "POST",
  });
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message:
        error?.message ?? "Ключ создания уже использован с другими данными.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "workspace_create_failed",
      fallbackMessage: "Не удалось создать пространство.",
    });
  }
  const parsed = createResponseSchema.safeParse(response.body);
  if (!parsed.success) {
    return apiMutationError(null, {
      fallbackCode: "invalid_workspace_response",
      fallbackMessage:
        "API вернул созданное пространство неожиданного формата.",
    });
  }
  return {
    status: "success",
    href: parsed.data.navigationOutcome.href,
    workspace: parsed.data.workspace,
  };
}

export async function selectWorkspace({
  csrfToken,
  currentWorkspaceId,
  workspaceId,
}: {
  csrfToken: string;
  currentWorkspaceId: string;
  workspaceId: string;
}): Promise<SelectWorkspaceResult> {
  const response = await requestJson(
    `/api/v1/workspaces/${workspaceId}/select`,
    {
      body: JSON.stringify({ expectedCurrentWorkspaceId: currentWorkspaceId }),
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
      message: error?.message ?? "Пространство больше недоступно.",
    };
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: error?.message ?? "Текущий workspace уже изменился.",
    };
  }
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "workspace_switch_failed",
      fallbackMessage: "Не удалось переключить пространство.",
    });
  }
  const parsed = selectResponseSchema.safeParse(response.body);
  if (!parsed.success) {
    return apiMutationError(null, {
      fallbackCode: "invalid_workspace_switch_response",
      fallbackMessage: "API вернул состояние сессии неожиданного формата.",
    });
  }
  return { status: "success", href: parsed.data.navigationOutcome.href };
}
