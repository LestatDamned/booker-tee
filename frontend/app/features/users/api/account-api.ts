import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

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

const accountSchema = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string().nullable(),
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
  const response = await requestJson("/api/v1/auth/session", {
    method: "DELETE",
    headers: { "X-CSRF-Token": csrfToken },
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
