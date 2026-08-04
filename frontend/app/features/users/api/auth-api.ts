import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

export type LoginDraft = components["schemas"]["LoginApiRequest"];
export type SignupDraft = components["schemas"]["SignupApiRequest"];

export type AuthMutationResult =
  | { status: "success"; nextPath: string }
  | {
      status: "error";
      fieldErrors: Record<string, string>;
      message: string;
    };

export type AuthConfigResult =
  | { status: "success"; allowSignups: boolean }
  | { status: "error"; message: string };

const authenticatedSchema = z.object({ nextPath: z.string() });
const configSchema = z.object({ allowSignups: z.boolean() });

export async function loadAuthConfig(
  signal?: AbortSignal,
): Promise<AuthConfigResult> {
  const response = await requestJson("/api/v1/auth/config", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  const parsed = configSchema.safeParse(response.body);
  if (!response.ok || !parsed.success) {
    return { status: "error", message: "Не удалось проверить регистрацию." };
  }
  return { status: "success", allowSignups: parsed.data.allowSignups };
}

export function login(draft: LoginDraft): Promise<AuthMutationResult> {
  return authenticate("/api/v1/auth/login", draft);
}

export function signup(draft: SignupDraft): Promise<AuthMutationResult> {
  return authenticate("/api/v1/auth/signup", draft);
}

async function authenticate(
  path: string,
  draft: LoginDraft | SignupDraft,
): Promise<AuthMutationResult> {
  const response = await requestJson(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (response.status === "network_error") {
    return { status: "error", fieldErrors: {}, message: "Backend недоступен." };
  }
  if (!response.ok) {
    const error = parseApiError(response.body);
    return {
      status: "error",
      fieldErrors: firstFieldErrors(error?.fieldErrors ?? {}),
      message: error?.message ?? `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = authenticatedSchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      fieldErrors: {},
      message: "API вернул данные неожиданного формата.",
    };
  }
  return { status: "success", nextPath: parsed.data.nextPath };
}

function firstFieldErrors(
  errors: Record<string, string[]>,
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(errors).flatMap(([field, messages]) =>
      messages[0] ? [[field, messages[0]]] : [],
    ),
  );
}
