import type { ButtonTone } from "../../ui/button/button";
import type {
  ImportReviewDto,
  ImportReviewLoadResult,
} from "./api/import-review-api";
import type {
  ImportReviewLifecycleRequest,
  ImportReviewMutationResult,
} from "./api/import-review-mutations";

export type LifecycleAction = ImportReviewLifecycleRequest["action"];
export type LifecycleRecovery =
  { kind: "refresh" } | { kind: "retry"; action: LifecycleAction };

type MutationFailure = Exclude<
  ImportReviewMutationResult<unknown>,
  { status: "success" }
>;
type RefreshFailure = Exclude<ImportReviewLoadResult, { status: "success" }>;

export function lifecycleFailure(
  result: MutationFailure,
  action: LifecycleAction,
): { message: string; recovery: LifecycleRecovery | null } {
  if (result.status === "conflict") {
    return {
      message: `${result.message} Загрузите актуальное состояние строки.`,
      recovery: { kind: "refresh" },
    };
  }
  if (result.status === "validation_error") {
    return {
      message: `${result.message} Обновите строку и проверьте данные.`,
      recovery: { kind: "refresh" },
    };
  }
  if (result.status === "error") {
    return {
      message: `${result.message} Проверьте соединение и повторите действие.`,
      recovery: { kind: "retry", action },
    };
  }
  return {
    message:
      result.status === "forbidden"
        ? "Недостаточно прав для изменения строки."
        : "Сессия завершилась. Войдите снова.",
    recovery: null,
  };
}

export function lifecycleRefreshFailure(result: RefreshFailure): string {
  return result.status === "error"
    ? `${result.message} Проверьте соединение и повторите обновление.`
    : "Не удалось обновить состояние import review.";
}

export function isDangerAction(action: LifecycleAction): boolean {
  return action === "mark_duplicate" || action === "ignore";
}

export function lifecycleActionTone(action: LifecycleAction): ButtonTone {
  if (action === "mark_unique") return "primary";
  if (isDangerAction(action)) return "dangerSecondary";
  return "secondary";
}

export function lifecycleActionLabel(
  action: LifecycleAction,
  status: ImportReviewDto["items"][number]["status"],
): string {
  if (action === "mark_unique") return "Это новая операция";
  if (action === "mark_duplicate") return "Отметить дублем";
  if (action === "ignore") return "Игнорировать";
  return status === "ignored" || status === "duplicate"
    ? "Восстановить на проверку"
    : "На проверку";
}

export function lifecycleConfirmationCopy(action: LifecycleAction): string {
  return action === "mark_duplicate"
    ? "Пометить строку дублем? Она не попадёт в официальный ledger."
    : "Игнорировать строку? Она не попадёт в официальный ledger.";
}

export function lifecycleSuccessMessage(
  action: LifecycleAction,
  previousStatus: ImportReviewDto["items"][number]["status"],
): string | null {
  if (action === "mark_duplicate") return "Строка отмечена дублем.";
  if (action === "ignore") return "Строка исключена из обработки.";
  if (
    action === "needs_review" &&
    (previousStatus === "ignored" || previousStatus === "duplicate")
  ) {
    return "Строка возвращена на проверку.";
  }
  return null;
}
