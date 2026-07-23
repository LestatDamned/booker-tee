import { MoneyValue } from "../../ui/money-value/money-value";
import type { ImportReviewDto } from "./api/import-review-api";
import styles from "./import-review.module.css";

type Validation = ImportReviewDto["validation"];
type PresentValidation = NonNullable<Validation>;

export function ReconciliationStatus({
  validation,
}: {
  validation: Validation;
}) {
  const presentation = validation
    ? reconciliationPresentation(validation)
    : {
        label: "Недостаточно данных для сверки",
        description: "Итоги выписки пока недоступны.",
        tone: "neutral" as const,
      };

  return (
    <section
      aria-labelledby="import-review-validation-title"
      className={styles.reconciliationSummary}
      data-tone={presentation.tone}
    >
      <p className={styles.reconciliationEyebrow}>Сверка итогов</p>
      <div className={styles.reconciliationOutcome}>
        <span className={styles.reconciliationStatus}>
          <span aria-hidden="true">{statusSymbol(presentation.tone)}</span>
          <h2 id="import-review-validation-title">{presentation.label}</h2>
        </span>
        <p>{presentation.description}</p>
      </div>
    </section>
  );
}

export function StatementReconciliation({
  validation,
}: {
  validation: Validation;
}) {
  if (!validation) return null;

  return (
    <section
      aria-label="Суммы поступлений и списаний"
      className={styles.reconciliation}
    >
      <table className={styles.flowTable}>
        <caption className={styles.flowTableCaption}>
          Контрольные суммы выписки
        </caption>
        <thead>
          <tr>
            <th scope="col">Движение</th>
            <th scope="col">По распознанным строкам</th>
            <th aria-hidden="true" className={styles.flowOperatorColumn} />
            <th scope="col">Исключённые строки</th>
            <th aria-hidden="true" className={styles.flowOperatorColumn} />
            <th scope="col">Итог в выписке</th>
            <th className={styles.flowDifferenceColumn} scope="col">
              Разница
            </th>
          </tr>
        </thead>
        <tbody>
          <FlowComparison
            calculated={validation.calculatedTotalInflow}
            currency={validation.currency}
            ignored={validation.ignoredTotalInflow}
            label="Поступления"
            statement={validation.statementTotalInflow}
            tone="income"
            unexplained={validation.unexplainedInflowDifference}
          />
          <FlowComparison
            calculated={validation.calculatedTotalOutflow}
            currency={validation.currency}
            ignored={validation.ignoredTotalOutflow}
            label="Списания"
            statement={validation.statementTotalOutflow}
            tone="expense"
            unexplained={validation.unexplainedOutflowDifference}
          />
        </tbody>
      </table>

      <details className={styles.technicalReconciliationDetails}>
        <summary>Технические данные</summary>
        <div className={styles.technicalReconciliationBody}>
          <p className={styles.balanceChain}>
            <strong>Цепочка остатков:</strong>{" "}
            {balanceChainLabel(validation.balanceChain)}
          </p>
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
        </div>
      </details>
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
    <tr className={styles.flowComparison}>
      <th scope="row">
        <h3>{label}</h3>
      </th>
      <MoneyFact
        amount={calculated}
        currency={currency}
        label="По распознанным строкам"
        role="calculated"
        tone={tone}
      />
      <td aria-hidden="true" className={styles.flowOperator}>
        +
      </td>
      <MoneyFact
        amount={ignored}
        currency={currency}
        label="Исключённые строки"
        role="ignored"
      />
      <td
        aria-hidden="true"
        className={`${styles.flowOperator} ${styles.flowOperatorEquals}`}
      >
        =
      </td>
      <MoneyFact
        amount={statement}
        currency={currency}
        label="Итог в выписке"
        role="statement"
        tone={tone}
      />
      <MoneyFact
        amount={unexplained}
        currency={currency}
        label="Разница"
        role="difference"
        warning={unexplained !== null && !isZero(unexplained)}
      />
    </tr>
  );
}

function MoneyFact({
  amount,
  currency,
  label,
  role,
  tone = "neutral",
  warning = false,
}: {
  amount: string | null;
  currency: string | null;
  label: string;
  role: "calculated" | "difference" | "ignored" | "statement";
  tone?: "neutral" | "income" | "expense";
  warning?: boolean;
}) {
  const classNames = [
    styles.moneyFact,
    styles[`moneyFact${capitalize(role)}`],
    warning ? styles.moneyFactWarning : undefined,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <td className={classNames} data-label={label}>
      <span className={styles.moneyFactValue}>
        {amount === null ? (
          "—"
        ) : (
          <MoneyValue
            amount={formatStatementAmount(amount)}
            currency={currency ?? ""}
            tone={tone}
          />
        )}
      </span>
    </td>
  );
}

function capitalize(value: string): string {
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
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
  if (validation.reasonCode === "balance_chain_mismatch") {
    return {
      label: "Остаток после операции не сходится",
      description: "Ожидаемый остаток отличается от указанного в выписке.",
      tone: "warning",
    };
  }
  return {
    label: "Есть необъяснённая разница",
    description: "Суммы строк не совпадают с итогами выписки.",
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
