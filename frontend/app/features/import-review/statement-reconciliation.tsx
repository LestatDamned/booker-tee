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
      <section className={styles.validation}>
        <p className={styles.sectionEyebrow}>Сверка выписки</p>
        <h2>Проверка ещё не рассчитана</h2>
        <p>Для документа пока нет завершённой попытки парсинга.</p>
      </section>
    );
  }

  const copy = validationCopy(validation.reasonCode);
  const statusLabel = reconciliationStatusLabel(validation.status);
  return (
    <section
      aria-labelledby="import-review-validation-title"
      className={styles.validation}
      data-status={validation.status}
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
            <span aria-hidden="true">{statusSymbol(validation.status)}</span>
            {statusLabel}
          </span>
          <h2 id="import-review-validation-title">{copy.title}</h2>
        </div>
      </div>

      <details className={styles.reconciliationDetails}>
        <summary>Подробнее о сверке</summary>
        <div className={styles.reconciliationDetailsBody}>
          <p>{copy.description}</p>
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
              label="Ошибки данных"
              value={validation.needsReviewCount}
            />
          </dl>
          <div className={styles.flowComparisons}>
            <FlowComparison
              calculated={validation.calculatedTotalInflow}
              currency={validation.currency}
              ignored={validation.ignoredTotalInflow}
              label="Как сошлись поступления"
              statement={validation.statementTotalInflow}
              tone="income"
              unexplained={validation.unexplainedInflowDifference}
            />
            <FlowComparison
              calculated={validation.calculatedTotalOutflow}
              currency={validation.currency}
              ignored={validation.ignoredTotalOutflow}
              label="Как сошлись списания"
              statement={validation.statementTotalOutflow}
              tone="expense"
              unexplained={validation.unexplainedOutflowDifference}
            />
          </div>
          <p className={styles.balanceChain}>
            <strong>Цепочка остатков:</strong>{" "}
            {balanceChainLabel(validation.balanceChain)}
          </p>
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
        size="prominent"
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
          label="По строкам"
          tone={tone}
        />
        <MoneyFact amount={ignored} currency={currency} label="Исключено" />
        <MoneyFact
          amount={statement}
          currency={currency}
          label="В выписке"
          tone={tone}
        />
        <MoneyFact
          amount={unexplained}
          currency={currency}
          label="Не объяснено"
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

function reconciliationStatusLabel(
  status: PresentValidation["status"],
): string {
  if (status === "valid") return "Сошлось";
  if (status === "mismatch") return "Есть расхождение";
  if (status === "needs_review") return "Нужна проверка";
  return "Недостаточно данных";
}

function statusSymbol(status: PresentValidation["status"]): string {
  if (status === "valid") return "✓";
  if (status === "mismatch" || status === "needs_review") return "!";
  return "–";
}

function validationCopy(reason: PresentValidation["reasonCode"]): {
  title: string;
  description: string;
} {
  return {
    totals_match: {
      title: "Итоги выписки сошлись",
      description: "Суммы строк и контрольные итоги согласованы.",
    },
    rows_need_review: {
      title: "Не все данные распознаны",
      description: "Проверьте отмеченные строки, затем вернитесь к сверке.",
    },
    balance_chain_mismatch: {
      title: "Нарушена цепочка остатков",
      description:
        "Один или несколько остатков не следуют из соседних операций.",
    },
    control_totals_unavailable: {
      title: "Контрольные итоги недоступны",
      description:
        "Парсер не извлёк итоги выписки, но строки можно проверить вручную.",
    },
    control_totals_mismatch: {
      title: "Итоги не совпадают с выпиской",
      description:
        "Между найденными строками и итогами выписки остаётся разница.",
    },
    ignored_rows_explain_mismatch: {
      title: "Разница объяснена исключёнными строками",
      description:
        "Итоги совпадают после учёта строк, исключённых из проведения.",
    },
  }[reason];
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
