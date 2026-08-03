import type { ImportReviewMutationResult } from "./api/import-review-mutations";

type RuleApplicationFailure = Exclude<
  ImportReviewMutationResult<unknown>,
  { status: "success" } | { status: "unauthenticated" }
>;

export function ruleApplicationFailure(result: RuleApplicationFailure): {
  canRetry: boolean;
  message: string;
} {
  if (result.status === "forbidden") {
    return {
      canRetry: false,
      message: "Недостаточно прав для применения правил.",
    };
  }
  return {
    canRetry: true,
    message:
      "message" in result ? result.message : "Не удалось применить правила.",
  };
}

export function ruleApplicationMessage({
  checkedCount,
  suggestedCount,
}: {
  checkedCount: number;
  suggestedCount: number;
}): string {
  if (checkedCount === 0)
    return "Нет строк, к которым можно применить правила.";
  return `Проверено строк: ${checkedCount}. Предложений применено: ${suggestedCount}.`;
}
