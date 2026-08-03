import { useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { FormActions } from "../../ui/field/form-layout";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type { ImportReviewDto } from "./api/import-review-api";
import { postImportReviewTransfer } from "./api/import-review-mutations";
import { reviewForDocument } from "./review-reconciliation";
import styles from "./transfer-panel.module.css";
import {
  transferDirectionLabel,
  transferFailure,
  transferRequest,
  type TransferItem,
} from "./transfer-model";
import { useImportReviewActionFeedback } from "./use-import-review-action-feedback";

type TransferPanelProps = {
  csrfToken: string;
  documentId: string;
  item: ImportReviewDto["items"][number];
  onCancel: () => void;
  onReviewReconciled: (review: ImportReviewDto) => void;
  onSelectionChange: (selection: string) => void;
  onSuccess: (message: string) => void;
  selection: string;
};

export function TransferPanel({
  csrfToken,
  documentId,
  item,
  onCancel,
  onReviewReconciled,
  onSelectionChange,
  onSuccess,
  selection,
}: TransferPanelProps) {
  const [pending, setPending] = useState(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const { alertRef, clearFeedback, error, recovery, showFailure } =
    useImportReviewActionFeedback<"retry">();

  function changeSelection(value: string) {
    onSelectionChange(value);
    clearFeedback();
    idempotencyKey.current = crypto.randomUUID();
  }

  async function submit() {
    const request = transferRequest(selection);
    if (!request) {
      showFailure("Выберите счёт или подходящий перевод.");
      return;
    }
    setPending(true);
    clearFeedback();
    const result = await postImportReviewTransfer(
      documentId,
      item.id,
      request,
      csrfToken,
      idempotencyKey.current,
    );
    setPending(false);
    if (result.status === "success") {
      const current = reviewForDocument(
        result.data.reviews,
        result.data.primaryDocumentId,
      );
      if (!current) {
        showFailure(
          "Backend не вернул обновлённое состояние документа.",
          "retry",
        );
        return;
      }
      onReviewReconciled(current);
      onSuccess("Перевод проведён.");
      return;
    }
    const failure = transferFailure(result);
    showFailure(failure.message, failure.canRetry ? "retry" : null);
  }

  return (
    <section aria-label="Параметры перевода" className={styles.transferPanel}>
      <TransferFields
        item={item}
        onSelectionChange={changeSelection}
        pending={pending}
        selection={selection}
      />
      <FormActions layout="split">
        <Button disabled={pending} onClick={onCancel} tone="secondary">
          Отмена
        </Button>
        <Button
          disabled={pending || !selection}
          icon="transfer"
          onClick={() => void submit()}
          tone="primary"
        >
          {pending ? "Проводим…" : "Провести перевод"}
        </Button>
      </FormActions>
      {error ? (
        <InlineNotice
          action={
            selection && recovery === "retry" ? (
              <Button
                disabled={pending}
                icon="retry"
                onClick={() => void submit()}
                tone="secondary"
              >
                Повторить перевод
              </Button>
            ) : undefined
          }
          ref={alertRef}
          role="alert"
          tabIndex={-1}
          title="Не удалось провести перевод"
          tone="danger"
        >
          {error}
        </InlineNotice>
      ) : null}
    </section>
  );
}

function TransferFields({
  item,
  onSelectionChange,
  pending,
  selection,
}: {
  item: TransferItem;
  onSelectionChange: (selection: string) => void;
  pending: boolean;
  selection: string;
}) {
  const hasOptions =
    item.transfer.accounts.length > 0 ||
    item.transfer.rawRowCandidates.length > 0 ||
    item.transfer.existingOperationCandidates.length > 0;

  return (
    <>
      <div className={styles.transferPreview}>
        <span>Направление</span>
        <strong>{transferDirectionLabel(item, selection)}</strong>
      </div>
      <Field
        htmlFor={`transfer-selection-${item.id}`}
        label="Второй счёт или готовая пара"
      >
        <select
          disabled={pending}
          id={`transfer-selection-${item.id}`}
          onChange={(event) => onSelectionChange(event.target.value)}
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
      </Field>
      {!hasOptions ? (
        <p>Подходящих счетов, строк или ручных переводов не найдено.</p>
      ) : null}
    </>
  );
}
