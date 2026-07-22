import styles from "./money-value.module.css";

export type MoneyTone =
  "neutral" | "income" | "expense" | "transfer" | "profit" | "adjustment";

type MoneyValueProps = {
  amount: string;
  currency: string;
  size?: "default" | "prominent";
  tone?: MoneyTone;
};

export function MoneyValue({
  amount,
  currency,
  size = "default",
  tone = "neutral",
}: MoneyValueProps) {
  return (
    <span
      aria-label={`${amount} ${currency}`}
      className={`${styles.value} ${styles[tone]} ${styles[size]}`}
    >
      <span className={styles.amount}>{amount}</span>
      <span className={styles.currency}>{currency}</span>
    </span>
  );
}
