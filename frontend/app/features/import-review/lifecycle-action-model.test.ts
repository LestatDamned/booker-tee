import { describe, expect, it } from "vitest";

import {
  isDangerAction,
  lifecycleActionLabel,
  lifecycleFailure,
  lifecycleRefreshFailure,
  lifecycleSuccessMessage,
} from "./lifecycle-action-model";

describe("lifecycle action model", () => {
  it("keeps danger and restoration semantics explicit", () => {
    expect(isDangerAction("mark_duplicate")).toBe(true);
    expect(isDangerAction("mark_unique")).toBe(false);
    expect(lifecycleActionLabel("needs_review", "duplicate")).toBe(
      "Восстановить на проверку",
    );
    expect(lifecycleSuccessMessage("needs_review", "ignored")).toBe(
      "Строка возвращена на проверку.",
    );
  });

  it("maps recoverable mutation failures to retry or authoritative refresh", () => {
    expect(
      lifecycleFailure(
        { status: "error", message: "Backend недоступен." },
        "mark_unique",
      ),
    ).toEqual({
      message: "Backend недоступен. Проверьте соединение и повторите действие.",
      recovery: { kind: "retry", action: "mark_unique" },
    });
    expect(
      lifecycleFailure(
        { status: "conflict", message: "Строка изменилась." },
        "ignore",
      ).recovery,
    ).toEqual({ kind: "refresh" });
  });

  it("keeps refresh failures recoverable", () => {
    expect(
      lifecycleRefreshFailure({
        status: "error",
        message: "Backend недоступен.",
      }),
    ).toContain("повторите обновление");
  });
});
