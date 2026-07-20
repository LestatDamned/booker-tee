import styles from "./money-value.module.css";

export type MoneyTone =
  "neutral" | "income" | "expense" | "transfer" | "profit" | "adjustment";

type MoneyValueProps = {
  amount: string;
  currency: string;
  tone?: MoneyTone;
};

export function MoneyValue({
  amount,
  currency,
  tone = "neutral",
}: MoneyValueProps) {
  return (
    <span
      aria-label={`${amount} ${currency}`}
      className={`${styles.value} ${styles[tone]}`}
    >
      <span className={styles.amount}>{amount}</span>
      <span className={styles.currency}>{currency}</span>
    </span>
  );
}
