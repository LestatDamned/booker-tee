import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import {
  parseApiError,
  requestJson,
  setAccessToken,
} from "../../../api/transport";

export type AccountDto = components["schemas"]["AccountApiResponse"];

export type AccountLoadResult =
  | { status: "success"; account: AccountDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export type AccountMutationResult =
  | { status: "success"; account: AccountDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export type PasswordChangeResult =
  | { status: "success"; message: string }
  | { status: "unauthenticated" }
  | {
      status: "error";
      fieldErrors: Record<string, string>;
      message: string;
    };

export type UserSessionDto = components["schemas"]["UserSessionApiResponse"];
export type DeactivationImpactDto =
  components["schemas"]["AccountDeactivationImpactApiResponse"];

export type UserSessionListResult =
  | { status: "success"; sessions: UserSessionDto[] }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export type SessionMutationResult =
  | { status: "success"; revokedCount?: number }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export type AccountActionResult =
  | { status: "success"; message: string }
  | { status: "unauthenticated" }
  | {
      status: "error";
      fieldErrors: Record<string, string>;
      message: string;
    };

export type DeactivationImpactResult =
  | { status: "success"; impact: DeactivationImpactDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

const accountSchema = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string().nullable(),
});

const userSessionSchema = z.object({
  id: z.string(),
  isCurrent: z.boolean(),
  deviceSummary: z.string(),
  createdAt: z.string(),
  lastSeenAt: z.string(),
  expiresAt: z.string(),
});

const userSessionListSchema = z.object({ items: z.array(userSessionSchema) });
const deactivationImpactSchema = z.object({
  canDeactivate: z.boolean(),
  blockers: z.array(
    z.object({
      workspaceId: z.string(),
      workspaceName: z.string(),
      activeOtherMemberCount: z.number().int().min(1),
    }),
  ),
  autoDeactivatedWorkspaceCount: z.number().int().min(0),
});

export async function loadAccount(
  signal?: AbortSignal,
): Promise<AccountLoadResult> {
  const response = await requestJson("/api/v1/account", {
    ...(signal ? { signal } : {}),
  });
  return accountResult(response);
}

export async function updateAccount(
  name: string,
  csrfToken: string,
): Promise<AccountMutationResult> {
  const response = await requestJson("/api/v1/account", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify({ name }),
  });
  return accountResult(response);
}

export async function logout(csrfToken: string): Promise<{
  status: "success" | "unauthenticated" | "error";
  message?: string;
}> {
  void csrfToken;
  const response = await requestJson("/api/v1/auth/logout", {
    auth: false,
    method: "POST",
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    return {
      status: "error",
      message:
        parseApiError(response.body)?.message ??
        `API вернул статус ${response.httpStatus}.`,
    };
  }
  setAccessToken(null);
  return { status: "success" };
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
  csrfToken: string,
): Promise<PasswordChangeResult> {
  const response = await requestJson("/api/v1/account/password", {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify({ currentPassword, newPassword }),
  });
  if (response.status === "network_error") {
    return { status: "error", fieldErrors: {}, message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    const error = parseApiError(response.body);
    return {
      status: "error",
      fieldErrors: Object.fromEntries(
        Object.entries(error?.fieldErrors ?? {}).flatMap(([field, messages]) =>
          messages[0] ? [[field, messages[0]]] : [],
        ),
      ),
      message: error?.message ?? `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = z.object({ message: z.string() }).safeParse(response.body);
  return parsed.success
    ? { status: "success", message: parsed.data.message }
    : {
        status: "error",
        fieldErrors: {},
        message: "API вернул неожиданный ответ.",
      };
}

export async function requestEmailChange(
  targetEmail: string,
  currentPassword: string,
  csrfToken: string,
): Promise<AccountActionResult> {
  return accountAction(
    "/api/v1/account/email-change-requests",
    { targetEmail, currentPassword },
    csrfToken,
  );
}

export async function confirmEmailChange(
  token: string,
  csrfToken: string,
): Promise<AccountActionResult> {
  return accountAction("/api/v1/account/email-changes", { token }, csrfToken);
}

export async function loadDeactivationImpact(
  signal?: AbortSignal,
): Promise<DeactivationImpactResult> {
  const response = await requestJson("/api/v1/account/deactivation-impact", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    return {
      status: "error",
      message:
        parseApiError(response.body)?.message ??
        `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = deactivationImpactSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", impact: parsed.data }
    : { status: "error", message: "API вернул неожиданные последствия." };
}

export async function deactivateAccount(
  currentPassword: string,
  confirmation: string,
  csrfToken: string,
): Promise<AccountActionResult> {
  return accountAction(
    "/api/v1/account/deactivation",
    { currentPassword, confirmation },
    csrfToken,
  );
}

export async function loadUserSessions(
  signal?: AbortSignal,
): Promise<UserSessionListResult> {
  const response = await requestJson("/api/v1/account/sessions", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    return {
      status: "error",
      message:
        parseApiError(response.body)?.message ??
        `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = userSessionListSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", sessions: parsed.data.items }
    : { status: "error", message: "API вернул неожиданный список сессий." };
}

export async function revokeUserSession(
  sessionId: string,
  csrfToken: string,
): Promise<SessionMutationResult> {
  return sessionMutation(`/api/v1/account/sessions/${sessionId}`, csrfToken);
}

export async function revokeOtherUserSessions(
  csrfToken: string,
): Promise<SessionMutationResult> {
  const response = await requestJson("/api/v1/account/sessions/others", {
    method: "DELETE",
    headers: { "X-CSRF-Token": csrfToken },
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  const result = parseSessionMutation(response);
  if (result.status !== "success") return result;
  const parsed = z
    .object({ revokedCount: z.number().int().min(0) })
    .safeParse(response.body);
  return parsed.success
    ? { status: "success", revokedCount: parsed.data.revokedCount }
    : { status: "error", message: "API вернул неожиданный ответ." };
}

async function sessionMutation(
  path: string,
  csrfToken: string,
): Promise<SessionMutationResult> {
  return parseSessionMutation(
    await requestJson(path, {
      method: "DELETE",
      headers: { "X-CSRF-Token": csrfToken },
    }),
  );
}

function parseSessionMutation(
  response: Awaited<ReturnType<typeof requestJson>>,
): SessionMutationResult {
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    return {
      status: "error",
      message:
        parseApiError(response.body)?.message ??
        `API вернул статус ${response.httpStatus}.`,
    };
  }
  return { status: "success" };
}

async function accountAction(
  path: string,
  body: Record<string, string>,
  csrfToken: string,
): Promise<AccountActionResult> {
  const response = await requestJson(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(body),
  });
  if (response.status === "network_error") {
    return { status: "error", fieldErrors: {}, message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    const error = parseApiError(response.body);
    return {
      status: "error",
      fieldErrors: Object.fromEntries(
        Object.entries(error?.fieldErrors ?? {}).flatMap(([field, messages]) =>
          messages[0] ? [[field, messages[0]]] : [],
        ),
      ),
      message: error?.message ?? `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = z.object({ message: z.string() }).safeParse(response.body);
  return parsed.success
    ? { status: "success", message: parsed.data.message }
    : {
        status: "error",
        fieldErrors: {},
        message: "API вернул неожиданный ответ.",
      };
}

function accountResult(
  response: Awaited<ReturnType<typeof requestJson>>,
): AccountLoadResult {
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    return {
      status: "error",
      message:
        parseApiError(response.body)?.message ??
        `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = accountSchema.safeParse(response.body);
  if (!parsed.success) {
    return { status: "error", message: "API вернул неожиданный профиль." };
  }
  return { status: "success", account: parsed.data };
}
