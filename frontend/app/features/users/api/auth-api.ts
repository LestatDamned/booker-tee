import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

export type LoginDraft = components["schemas"]["LoginApiRequest"];
export type SignupDraft = components["schemas"]["SignupApiRequest"];
export type EmailVerificationDraft =
  components["schemas"]["EmailVerificationApiRequest"];
export type EmailVerificationRequestDraft =
  components["schemas"]["EmailVerificationRequestApiRequest"];

export type AuthMutationResult =
  | { status: "success"; nextPath: string }
  | {
      status: "error";
      fieldErrors: Record<string, string>;
      message: string;
    };

export type AuthConfigResult =
  | {
      status: "success";
      allowSignups: boolean;
      passwordMinLength: number;
    }
  | { status: "error"; message: string };

export type VerificationRequestResult =
  | { status: "success"; message: string; retryAfterSeconds: number }
  | {
      status: "error";
      fieldErrors: Record<string, string>;
      message: string;
      retryAfterSeconds?: number;
    };

const authenticatedSchema = z.object({ nextPath: z.string() });
const configSchema = z.object({
  allowSignups: z.boolean(),
  passwordMinLength: z.number().int().min(8),
});
const verificationRequestedSchema = z.object({
  message: z.string(),
  retryAfterSeconds: z.number().int().nonnegative(),
});

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
  return { status: "success", ...parsed.data };
}

export function login(draft: LoginDraft): Promise<AuthMutationResult> {
  return authenticate("/api/v1/auth/login", draft);
}

export function signup(draft: SignupDraft): Promise<VerificationRequestResult> {
  return requestVerification("/api/v1/auth/signup", draft);
}

export function resendEmailVerification(
  draft: EmailVerificationRequestDraft,
): Promise<VerificationRequestResult> {
  return requestVerification("/api/v1/auth/email-verification-requests", draft);
}

export function verifyEmail(
  draft: EmailVerificationDraft,
): Promise<AuthMutationResult> {
  return authenticate("/api/v1/auth/email-verifications", draft);
}

async function authenticate(
  path: string,
  draft: LoginDraft | EmailVerificationDraft,
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

async function requestVerification(
  path: string,
  draft: SignupDraft | EmailVerificationRequestDraft,
): Promise<VerificationRequestResult> {
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
      ...(response.httpStatus === 429
        ? { retryAfterSeconds: retryAfterDetails(error?.details) }
        : {}),
    };
  }
  const parsed = verificationRequestedSchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      fieldErrors: {},
      message: "API вернул данные неожиданного формата.",
    };
  }
  return { status: "success", ...parsed.data };
}

function retryAfterDetails(details?: Record<string, unknown>): number {
  const seconds = Number(details?.retryAfterSeconds);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : 60;
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
