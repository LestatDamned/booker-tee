import { describe, expect, it } from "vitest";

import {
  apiForbiddenFailure,
  apiLoadNetworkError,
  apiMutationError,
  apiMutationNetworkError,
  apiResponseErrorMessage,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
} from "./failures";

describe("shared API failures", () => {
  it("creates stable transport failures", () => {
    expect(apiUnauthenticatedFailure()).toEqual({ status: "unauthenticated" });
    expect(apiLoadNetworkError()).toEqual({
      status: "error",
      message: "Backend недоступен.",
    });
    expect(apiUnexpectedStatusError(503)).toEqual({
      status: "error",
      message: "API вернул статус 503.",
    });
    expect(apiMutationNetworkError()).toEqual({
      status: "error",
      code: "network_error",
      fieldErrors: {},
      message: "Backend недоступен. Проверьте соединение и повторите.",
    });
  });

  it("uses a parsed API error before feature fallbacks", () => {
    const error = {
      code: "financial_write_forbidden",
      details: { capability: "canCreate" },
      fieldErrors: { name: ["Недоступно."] },
      message: "Недостаточно прав.",
    };

    expect(apiForbiddenFailure(error, "Fallback")).toEqual({
      status: "forbidden",
      message: "Недостаточно прав.",
    });
    expect(apiResponseErrorMessage(error, 403)).toBe("Недостаточно прав.");
    expect(
      apiMutationError(error, {
        fallbackCode: "fallback_code",
        fallbackMessage: "Fallback",
      }),
    ).toEqual({ status: "error", ...error });
  });

  it("keeps feature-specific fallback copy and codes", () => {
    expect(apiResponseErrorMessage(null, 503)).toBe("API вернул статус 503.");
    expect(apiForbiddenFailure(null, "Создание недоступно.")).toEqual({
      status: "forbidden",
      message: "Создание недоступно.",
    });
    expect(
      apiMutationError(null, {
        fallbackCode: "create_failed",
        fallbackMessage: "Не удалось создать запись.",
      }),
    ).toEqual({
      status: "error",
      code: "create_failed",
      fieldErrors: {},
      message: "Не удалось создать запись.",
    });
  });
});
