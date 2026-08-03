import type { ImportReviewDto } from "./api/import-review-api";
import type {
  ImportReviewConfirmationRequest,
  ImportReviewDraftEvaluationDto,
  ImportReviewMutationResult,
} from "./api/import-review-mutations";

export type ConfirmedPostingSelection = {
  categoryId: string;
  operationType: "income" | "expense";
  propertyId: string | null;
};

type ImportReviewMutationFailure = Exclude<
  ImportReviewMutationResult<unknown>,
  { status: "success" }
>;

export function confirmedPostingSelection(
  dirty: boolean,
  evaluation: ImportReviewDraftEvaluationDto,
): ConfirmedPostingSelection | null {
  const operationType = evaluation.classification.operationType;
  const categoryId = evaluation.selection.categoryId;
  if (
    dirty ||
    !evaluation.confirmability.canConfirm ||
    (operationType !== "income" && operationType !== "expense") ||
    categoryId === null
  ) {
    return null;
  }
  return {
    categoryId,
    operationType,
    propertyId: evaluation.selection.propertyId,
  };
}

export function normalizedRulePattern(rulePattern: string) {
  const cleanedRulePattern = rulePattern.trim();
  return {
    cleanedRulePattern,
    rememberRule: cleanedRulePattern.length > 0,
  };
}

export function buildPostingConfirmationRequest(
  selection: ConfirmedPostingSelection,
  expectedStatus: ImportReviewDto["items"][number]["status"],
  rulePattern: string,
): ImportReviewConfirmationRequest {
  const { cleanedRulePattern, rememberRule } =
    normalizedRulePattern(rulePattern);
  return {
    operationType: selection.operationType,
    categoryId: selection.categoryId,
    propertyId: selection.propertyId,
    expectedStatus,
    rememberRule,
    rulePattern: rememberRule ? cleanedRulePattern : null,
  };
}

export function postingSelectionFingerprint(
  selection: ConfirmedPostingSelection | null,
  rulePattern: string,
): string {
  const { cleanedRulePattern } = normalizedRulePattern(rulePattern);
  return `${selection?.operationType ?? null}:${selection?.categoryId ?? null}:${selection?.propertyId ?? null}:${cleanedRulePattern}`;
}

export function postingError(result: ImportReviewMutationFailure): string {
  if (result.status === "unauthenticated") {
    return "Сессия завершилась. Войдите снова; операция не показана как проведённая.";
  }
  if (result.status === "forbidden") {
    return "Недостаточно прав для проведения операции.";
  }
  return "message" in result ? result.message : "Операцию не удалось изменить.";
}
