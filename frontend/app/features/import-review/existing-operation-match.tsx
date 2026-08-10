import { useState } from "react";

import { formatIsoDate } from "../../shared/date/format-date";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { Button } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { MoneyValue } from "../../ui/money-value/money-value";
import type { ImportReviewDto } from "./api/import-review-api";
import { linkImportReviewExistingOperation } from "./api/import-review-mutations";
import styles from "./duplicate-comparison.module.css";

type ReviewItem = ImportReviewDto["items"][number];

export function ExistingOperationComparison({
  item,
  onSelect,
  selectedOperationId,
}: {
  item: ReviewItem;
  onSelect: (operationId: string) => void;
  selectedOperationId: string;
}) {
  if (item.existingOperationCandidates.length === 0) return null;
  const amount = item.normalized.amount ?? item.raw.amount;
  const currency = item.normalized.currency ?? item.raw.currency ?? "";
  const operationDate = item.normalized.operationDate;

  return (
    <section
      aria-labelledby={`existing-operation-${item.id}`}
      className={styles.duplicateComparison}
    >
      <header>
        <div>
          <span>Сверка с журналом</span>
          <h3 id={`existing-operation-${item.id}`}>
            Возможно, операция уже учтена
          </h3>
        </div>
        <p>
          Совпали счёт, сумма и валюта; дата отличается не более чем на 3 дня.
        </p>
      </header>
      <div className={styles.duplicatePair}>
        <article className={styles.duplicateFacts}>
          <span>Строка выписки</span>
          <strong>
            {item.normalized.description ??
              item.raw.description ??
              "Без описания"}
          </strong>
          <dl>
            <div>
              <dt>Дата</dt>
              <dd>
                {operationDate ? formatIsoDate(operationDate) : "Не определена"}
              </dd>
            </div>
            <div>
              <dt>Сумма</dt>
              <dd>
                {amount ? (
                  <MoneyValue
                    amount={formatMoneyAmount(
                      amount,
                      item.classification.operationType,
                    )}
                    currency={currency}
                  />
                ) : (
                  "—"
                )}
              </dd>
            </div>
          </dl>
        </article>
        <div className={styles.candidateList}>
          {item.existingOperationCandidates.map((candidate) => (
            <label
              className={styles.candidateChoice}
              key={candidate.operationId}
            >
              <input
                checked={selectedOperationId === candidate.operationId}
                name={`existing-operation-candidate-${item.id}`}
                onChange={() => onSelect(candidate.operationId)}
                type="radio"
                value={candidate.operationId}
              />
              <span>
                <small>Существующая ручная операция</small>
                <strong>{candidate.description ?? "Без описания"}</strong>
                <span>
                  {formatIsoDate(candidate.operationDate)} ·{" "}
                  <MoneyValue
                    amount={formatMoneyAmount(
                      candidate.amount,
                      item.classification.operationType,
                    )}
                    currency={candidate.currency}
                  />
                </span>
                {candidate.categoryName ? (
                  <span>{candidate.categoryName}</span>
                ) : null}
              </span>
            </label>
          ))}
        </div>
      </div>
    </section>
  );
}

export function ExistingOperationLinkAction({
  csrfToken,
  documentId,
  item,
  onReviewReconciled,
  onSuccess,
  operationId,
}: {
  csrfToken: string;
  documentId: string;
  item: ReviewItem;
  onReviewReconciled: (review: ImportReviewDto) => void;
  onSuccess: (message: string) => void;
  operationId: string;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function link() {
    setPending(true);
    setError(null);
    const result = await linkImportReviewExistingOperation(
      documentId,
      item.id,
      { operationId, expectedStatus: item.status },
      csrfToken,
    );
    setPending(false);
    if (result.status === "success") {
      onReviewReconciled(result.data.review);
      onSuccess("Строка выписки связана с существующей операцией.");
      return;
    }
    setError(
      result.status === "conflict"
        ? result.message
        : "Не удалось связать операцию. Повторите действие.",
    );
  }

  return (
    <section aria-label="Связывание с существующей операцией">
      <Button isLoading={pending} onClick={() => void link()} tone="primary">
        Связать с существующей операцией
      </Button>
      {error ? (
        <InlineNotice
          action={
            <Button onClick={() => void link()} tone="secondary">
              Повторить
            </Button>
          }
          role="alert"
          title="Не удалось связать операцию"
          tone="danger"
        >
          {error}
        </InlineNotice>
      ) : null}
    </section>
  );
}
