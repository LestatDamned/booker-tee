import type { components } from "./generated/schema";
import { sessionSchema } from "./session-schema";

export type SessionDto = components["schemas"]["SessionApiResponse"];

export type SessionLoadResult =
  | { status: "loading" }
  | { status: "authenticated"; session: SessionDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

export async function loadSession(): Promise<SessionLoadResult> {
  try {
    const response = await fetch("/api/v1/session", {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });

    if (response.status === 401) {
      return { status: "unauthenticated" };
    }
    if (!response.ok) {
      return {
        status: "error",
        message: `API вернул статус ${response.status}.`,
      };
    }

    const payload: unknown = await response.json();
    const parsed = sessionSchema.safeParse(payload);
    if (!parsed.success) {
      return {
        status: "error",
        message: "API вернул данные неожиданного формата.",
      };
    }

    return { status: "authenticated", session: parsed.data };
  } catch {
    return { status: "error", message: "Backend недоступен." };
  }
}
