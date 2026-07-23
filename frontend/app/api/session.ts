import type { components } from "./generated/schema";
import { sessionSchema } from "./session-schema";
import { requestJson } from "./transport";

export type SessionDto = components["schemas"]["SessionApiResponse"];

export type SessionLoadResult =
  | { status: "loading" }
  | { status: "authenticated"; session: SessionDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export async function loadSession(
  signal?: AbortSignal,
): Promise<SessionLoadResult> {
  const response = await requestJson("/api/v1/session", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) {
    return { status: "unauthenticated" };
  }
  if (!response.ok) {
    return {
      status: "error",
      message: `API вернул статус ${response.httpStatus}.`,
    };
  }

  const parsed = sessionSchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      message: "API вернул данные неожиданного формата.",
    };
  }

  return { status: "authenticated", session: parsed.data };
}
