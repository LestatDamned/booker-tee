import type { ImportReviewDto } from "./api/import-review-api";
import type {
  ImportReviewCategoryReferenceDto,
  ImportReviewDraftEvaluationDto,
  ImportReviewDraftEvaluationRequest,
  ImportReviewMutationResult,
} from "./api/import-review-mutations";

export type ClassificationItem = ImportReviewDto["items"][number];
export type ClassificationReviewMode = "ordinary" | "transfer";
export type ClassificationMutationFailure = Exclude<
  ImportReviewMutationResult<unknown>,
  { status: "success" }
>;

export function defaultCategoryKind(
  operationType: ImportReviewDraftEvaluationRequest["operationType"],
): ImportReviewCategoryReferenceDto["kind"] {
  return operationType === "income" || operationType === "expense"
    ? operationType
    : "mixed";
}

export function parseCategoryKind(
  value: string,
): ImportReviewCategoryReferenceDto["kind"] {
  if (
    value === "income" ||
    value === "expense" ||
    value === "mixed" ||
    value === "transfer" ||
    value === "adjustment"
  ) {
    return value;
  }
  return "mixed";
}

export function ordinaryOperationType(
  item: ClassificationItem,
): "income" | "expense" | null {
  if (
    item.classification.operationType === "income" ||
    item.classification.operationType === "expense"
  ) {
    return item.classification.operationType;
  }
  return item.transfer.ordinaryOperationType;
}

export function serverClassificationDraft(
  item: ClassificationItem,
): ImportReviewDraftEvaluationRequest {
  return {
    operationType: ordinaryOperationType(item),
    categoryId: item.selection.categoryId,
    propertyId: item.selection.propertyId,
  };
}

export function serverClassificationEvaluation(
  item: ClassificationItem,
): ImportReviewDraftEvaluationDto {
  return {
    itemId: item.id,
    classification: item.classification,
    selection: item.selection,
    confirmability: item.confirmability,
    ruleSuggestion: item.ruleSuggestion,
  };
}

export function ordinaryOperationLabel(item: ClassificationItem): string {
  const operationType = ordinaryOperationType(item);
  if (operationType === "income") return "Доход";
  if (operationType === "expense") return "Расход";
  return "Доход или расход";
}

export function draftMutationError(
  result: ClassificationMutationFailure,
): string {
  if (result.status === "unauthenticated") {
    return "Сессия завершилась. Войдите снова, draft сохранён на странице.";
  }
  if (result.status === "forbidden")
    return "Недостаточно прав для проверки draft.";
  return "message" in result ? result.message : "Draft не удалось проверить.";
}

export function categoryMutationError(
  result: ClassificationMutationFailure,
): string {
  if (result.status === "unauthenticated") {
    return "Сессия завершилась. Название новой категории сохранено в draft.";
  }
  if (result.status === "forbidden")
    return "Недостаточно прав для создания категории.";
  return "message" in result ? result.message : "Категорию не удалось создать.";
}
