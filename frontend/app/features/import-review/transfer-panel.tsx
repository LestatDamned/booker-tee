import { useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import type { ImportReviewDto } from "./api/import-review-api";
import {
  postImportReviewTransfer,
  type ImportReviewTransferRequest,
} from "./api/import-review-mutations";
import styles from "./import-review.module.css";

type TransferPanelProps = {
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onCancel: () => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  onSelectionChange: (selection: string) => void;
  selection: string;
};

export function TransferPanel({
  csrfToken,
  documentId,
  item,
  onCancel,
  onReviewReconciled,
  onSelectionChange,
  selection,
}: TransferPanelProps) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const idempotencyKey = useRef(crypto.randomUUID());

  function changeSelection(value: string) {
    onSelectionChange(value);
    setError(null);
    idempotencyKey.current = crypto.randomUUID();
  }

  async function submit() {
    const request = transferRequest(selection);
    if (!request) {
      setError("Выберите счёт или подходящий перевод.");
      return;
    }
    setPending(true);
    setError(null);
    const result = await postImportReviewTransfer(
      documentId,
      item.id,
      request,
      csrfToken,
      idempotencyKey.current,
    );
    setPending(false);
    if (result.status === "success") {
      const current = result.data.reviews.find(
        (review) => review.document.id === result.data.primaryDocumentId,
      );
      if (!current) {
        setError("Backend не вернул обновлённое состояние документа.");
        return;
      }
      onReviewReconciled(current);
      return;
    }
    if (result.status === "conflict") {
      setError(`${result.message} Обновите выбор и попробуйте снова.`);
      return;
    }
    if (result.status === "validation_error") {
      setError(result.message);
      return;
    }
    if (result.status === "unauthenticated") {
      setError("Сессия завершилась. Войдите снова.");
      return;
    }
    if (result.status === "forbidden") {
      setError("Недостаточно прав для проведения перевода.");
      return;
    }
    setError(
      result.status === "error"
        ? result.message
        : "Операцию не удалось выполнить.",
    );
  }

  return (
    <section aria-label="Параметры перевода" className={styles.transferPanel}>
      <div className={styles.transferPreview}>
        <span>Направление</span>
        <strong>{directionLabel(item, selection)}</strong>
      </div>
      <label>
        Второй счёт или готовая пара
        <select
          disabled={pending}
          onChange={(event) => changeSelection(event.target.value)}
          value={selection}
        >
          <option value="">Выберите вариант</option>
          {item.transfer.accounts.length ? (
            <optgroup label="Создать перевод">
              {item.transfer.accounts.map((account) => (
                <option key={account.id} value={`account:${account.id}`}>
                  Новый перевод · {account.name} · {account.currency}
                </option>
              ))}
            </optgroup>
          ) : null}
          {item.transfer.rawRowCandidates.length ? (
            <optgroup label="Парная строка выписки">
              {item.transfer.rawRowCandidates.map((candidate) => (
                <option
                  key={candidate.itemId}
                  value={`raw:${candidate.itemId}`}
                >
                  Строка {candidate.rowIndex} · {candidate.amount}{" "}
                  {candidate.currency} · {candidate.account.name} ·{" "}
                  {candidate.dayDistance} дн.
                </option>
              ))}
            </optgroup>
          ) : null}
          {item.transfer.existingOperationCandidates.length ? (
            <optgroup label="Ручной перевод">
              {item.transfer.existingOperationCandidates.map((candidate) => (
                <option
                  key={candidate.operationId}
                  value={`operation:${candidate.operationId}`}
                >
                  {candidate.operationDate} · {candidate.amount}{" "}
                  {candidate.currency} ·{" "}
                  {candidate.counterpartyAccount?.name ?? "Второй счёт"}
                </option>
              ))}
            </optgroup>
          ) : null}
        </select>
      </label>
      {item.transfer.accounts.length === 0 &&
      item.transfer.rawRowCandidates.length === 0 &&
      item.transfer.existingOperationCandidates.length === 0 ? (
        <p>Подходящих счетов, строк или ручных переводов не найдено.</p>
      ) : null}
      <div className={styles.editorActions}>
        <Button
          disabled={pending || !selection}
          onClick={() => void submit()}
          tone="primary"
        >
          {pending ? "Проводим…" : "Провести перевод"}
        </Button>
        <Button disabled={pending} onClick={onCancel}>
          Отмена
        </Button>
      </div>
      {error ? (
        <p className={styles.draftError} role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}

function transferRequest(
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

function directionLabel(
  item: ImportReviewDto["items"][number],
  selection: string,
): string {
  const source = item.sourceAccount?.name ?? "Счёт выписки";
  const counterparty = selectedCounterparty(item, selection);
  if (item.transfer.direction === "source_to_counterparty") {
    return `${source} → ${counterparty}`;
  }
  if (item.transfer.direction === "counterparty_to_source") {
    return `${counterparty} → ${source}`;
  }
  return "Недостаточно данных";
}

function selectedCounterparty(
  item: ImportReviewDto["items"][number],
  selection: string,
): string {
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
