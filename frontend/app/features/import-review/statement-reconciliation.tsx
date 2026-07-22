import { MoneyValue } from "../../ui/money-value/money-value";
import type { ImportReviewDto } from "./api/import-review-api";
import styles from "./import-review.module.css";

type Validation = ImportReviewDto["validation"];
type PresentValidation = NonNullable<Validation>;

export function StatementReconciliation({
  validation,
}: {
  validation: Validation;
}) {
  if (!validation) {
    return (
      <section className={styles.reconciliation} data-tone="neutral">
        <div className={styles.reconciliationOutcome}>
          <span className={styles.reconciliationStatus}>
            <span aria-hidden="true">–</span>
            Недостаточно данных для сверки
          </span>
          <p>Итоги выписки пока недоступны.</p>
        </div>
      </section>
    );
  }

  const presentation = reconciliationPresentation(validation);
  return (
    <section
      aria-labelledby="import-review-validation-title"
      className={styles.reconciliation}
      data-tone={presentation.tone}
    >
      <div className={styles.reconciliationOverview}>
        <FlowTotal
          amount={
            validation.statementTotalInflow ?? validation.calculatedTotalInflow
          }
          currency={validation.currency}
          label="Поступления"
          tone="income"
        />
        <FlowTotal
          amount={
            validation.statementTotalOutflow ??
            validation.calculatedTotalOutflow
          }
          currency={validation.currency}
          label="Списания"
          tone="expense"
        />
        <div className={styles.reconciliationOutcome}>
          <span className={styles.reconciliationStatus}>
            <span aria-hidden="true">{statusSymbol(presentation.tone)}</span>
            <h2 id="import-review-validation-title">{presentation.label}</h2>
          </span>
          <p>{presentation.description}</p>
        </div>
      </div>

      <details className={styles.reconciliationDetails}>
        <summary>Подробнее о сверке</summary>
        <div className={styles.reconciliationDetailsBody}>
          <div className={styles.flowComparisons}>
            <FlowComparison
              calculated={validation.calculatedTotalInflow}
              currency={validation.currency}
              ignored={validation.ignoredTotalInflow}
              label="Сверка поступлений"
              statement={validation.statementTotalInflow}
              tone="income"
              unexplained={validation.unexplainedInflowDifference}
            />
            <FlowComparison
              calculated={validation.calculatedTotalOutflow}
              currency={validation.currency}
              ignored={validation.ignoredTotalOutflow}
              label="Сверка списаний"
              statement={validation.statementTotalOutflow}
              tone="expense"
              unexplained={validation.unexplainedOutflowDifference}
            />
          </div>
          <p className={styles.balanceChain}>
            <strong>Цепочка остатков:</strong>{" "}
            {balanceChainLabel(validation.balanceChain)}
          </p>
          <details className={styles.technicalReconciliationDetails}>
            <summary>Технические данные</summary>
            <dl className={styles.validationCounts}>
              <ValidationCount
                label="Строк извлечено"
                value={validation.extractedCount}
              />
              <ValidationCount
                label="Нормализовано"
                value={validation.normalizedCount}
              />
              <ValidationCount
                label="Требуют проверки"
                value={validation.needsReviewCount}
              />
            </dl>
          </details>
        </div>
      </details>
    </section>
  );
}

function FlowTotal({
  amount,
  currency,
  label,
  tone,
}: {
  amount: string;
  currency: string | null;
  label: string;
  tone: "income" | "expense";
}) {
  return (
    <section className={styles.flowTotal}>
      <h3>{label}</h3>
      <MoneyValue
        amount={formatStatementAmount(amount)}
        currency={currency ?? ""}
        tone={tone}
      />
    </section>
  );
}

function ValidationCount({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function FlowComparison({
  calculated,
  currency,
  ignored,
  label,
  statement,
  tone,
  unexplained,
}: {
  calculated: string;
  currency: string | null;
  ignored: string;
  label: string;
  statement: string | null;
  tone: "income" | "expense";
  unexplained: string | null;
}) {
  return (
    <section className={styles.flowComparison}>
      <h3>{label}</h3>
      <dl>
        <MoneyFact
          amount={calculated}
          currency={currency}
          label="По распознанным строкам"
          tone={tone}
        />
        <MoneyFact
          amount={ignored}
          currency={currency}
          label="Исключённые строки"
        />
        <MoneyFact
          amount={statement}
          currency={currency}
          label="Итог в выписке"
          tone={tone}
        />
        <MoneyFact
          amount={unexplained}
          currency={currency}
          label="Необъяснённая разница"
          warning={unexplained !== null && !isZero(unexplained)}
        />
      </dl>
    </section>
  );
}

function MoneyFact({
  amount,
  currency,
  label,
  tone = "neutral",
  warning = false,
}: {
  amount: string | null;
  currency: string | null;
  label: string;
  tone?: "neutral" | "income" | "expense";
  warning?: boolean;
}) {
  return (
    <div className={warning ? styles.moneyFactWarning : undefined}>
      <dt>{label}</dt>
      <dd>
        {amount === null ? (
          "—"
        ) : (
          <MoneyValue
            amount={formatStatementAmount(amount)}
            currency={currency ?? ""}
            tone={tone}
          />
        )}
      </dd>
    </div>
  );
}

function formatStatementAmount(value: string): string {
  const [integer = value, fraction] = value.split(".", 2);
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  return fraction === undefined
    ? grouped
    : `${grouped},${fraction.padEnd(2, "0").slice(0, 2)}`;
}

function isZero(value: string): boolean {
  return /^-?0+(?:\.0+)?$/.test(value);
}

type ReconciliationTone = "success" | "warning" | "neutral";

function statusSymbol(tone: ReconciliationTone): string {
  if (tone === "success") return "✓";
  if (tone === "warning") return "!";
  return "–";
}

function reconciliationPresentation(validation: PresentValidation): {
  label: string;
  description: string;
  tone: ReconciliationTone;
} {
  if (validation.reasonCode === "totals_match") {
    return {
      label: "Сверка сошлась",
      description: "Суммы строк совпадают с итогами выписки.",
      tone: "success",
    };
  }
  if (validation.reasonCode === "ignored_rows_explain_mismatch") {
    return {
      label: "Разница объяснена",
      description: ignoredRowsDescription(validation),
      tone: "success",
    };
  }
  if (
    validation.reasonCode === "control_totals_unavailable" ||
    validation.reasonCode === "rows_need_review"
  ) {
    return {
      label: "Недостаточно данных для сверки",
      description:
        validation.reasonCode === "rows_need_review"
          ? "Сначала проверьте строки с нераспознанными данными."
          : "Итоги выписки не были распознаны.",
      tone: "neutral",
    };
  }
  return {
    label: "Есть необъяснённая разница",
    description:
      validation.reasonCode === "balance_chain_mismatch"
        ? "Нарушена последовательность остатков между строками."
        : "Суммы строк не совпадают с итогами выписки.",
    tone: "warning",
  };
}

function ignoredRowsDescription(validation: PresentValidation): string {
  const inflowIgnored = !isZero(validation.ignoredTotalInflow);
  const outflowIgnored = !isZero(validation.ignoredTotalOutflow);
  const currency = validation.currency ? ` ${validation.currency}` : "";
  if (
    inflowIgnored &&
    outflowIgnored &&
    validation.ignoredTotalInflow === validation.ignoredTotalOutflow
  ) {
    return `${formatStatementAmount(validation.ignoredTotalInflow)}${currency} исключено из поступлений и списаний.`;
  }
  const parts = [
    inflowIgnored
      ? `${formatStatementAmount(validation.ignoredTotalInflow)}${currency} из поступлений`
      : null,
    outflowIgnored
      ? `${formatStatementAmount(validation.ignoredTotalOutflow)}${currency} из списаний`
      : null,
  ].filter((part): part is string => part !== null);
  return parts.length > 0
    ? `Исключено: ${parts.join(", ")}.`
    : "Разница полностью объяснена исключёнными строками.";
}

function balanceChainLabel(
  balanceChain: PresentValidation["balanceChain"],
): string {
  if (balanceChain.status === "unavailable") return "недостаточно данных";
  if (balanceChain.status === "mismatch") {
    return `несоответствий: ${balanceChain.mismatchCount}; проверено переходов: ${balanceChain.checkedPairCount}`;
  }
  return `расхождений нет; проверено переходов: ${balanceChain.checkedPairCount}`;
}
