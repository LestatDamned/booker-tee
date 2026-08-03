import type { ImportReviewDto } from "./api/import-review-api";
import type {
  ImportReviewMutationResult,
  ImportReviewTransferRequest,
} from "./api/import-review-mutations";

export type TransferItem = ImportReviewDto["items"][number];

type TransferMutationFailure = Exclude<
  ImportReviewMutationResult<unknown>,
  { status: "success" }
>;

export function transferRequest(
  selection: string,
): ImportReviewTransferRequest | null {
  const [kind, id] = selection.split(":", 2);
  if (!id) return null;
  if (kind === "account") {
    return { kind: "new_transfer", counterpartyAccountId: id };
  }
  if (kind === "raw") {
    return { kind: "raw_row_match", matchedItemId: id };
  }
  if (kind === "operation") {
    return { kind: "existing_operation_link", operationId: id };
  }
  return null;
}

export function transferDirectionLabel(
  item: TransferItem,
  selection: string,
): string {
  const source =
    item.transfer.sourceAccount?.name ??
    item.sourceAccount?.name ??
    "Счёт выписки";
  const counterparty = selectedCounterparty(item, selection);
  if (item.transfer.direction === "source_to_counterparty") {
    return `${source} → ${counterparty}`;
  }
  if (item.transfer.direction === "counterparty_to_source") {
    return `${counterparty} → ${source}`;
  }
  return "Недостаточно данных";
}

export function transferFailure(result: TransferMutationFailure): {
  canRetry: boolean;
  message: string;
} {
  if (result.status === "conflict") {
    return {
      canRetry: false,
      message: `${result.message} Обновите выбор и попробуйте снова.`,
    };
  }
  if (result.status === "validation_error") {
    return { canRetry: false, message: result.message };
  }
  if (result.status === "unauthenticated") {
    return { canRetry: false, message: "Сессия завершилась. Войдите снова." };
  }
  if (result.status === "forbidden") {
    return {
      canRetry: false,
      message: "Недостаточно прав для проведения перевода.",
    };
  }
  return {
    canRetry: true,
    message:
      result.status === "error"
        ? result.message
        : "Операцию не удалось выполнить.",
  };
}

function selectedCounterparty(item: TransferItem, selection: string): string {
  if (!selection) return "Не выбран второй счёт";
  const [kind, id] = selection.split(":", 2);
  if (kind === "account") {
    return (
      item.transfer.accounts.find((account) => account.id === id)?.name ??
      "Второй счёт"
    );
  }
  if (kind === "raw") {
    return (
      item.transfer.rawRowCandidates.find(
        (candidate) => candidate.itemId === id,
      )?.account.name ?? "Второй счёт"
    );
  }
  return (
    item.transfer.existingOperationCandidates.find(
      (candidate) => candidate.operationId === id,
    )?.counterpartyAccount?.name ?? "Второй счёт"
  );
}
