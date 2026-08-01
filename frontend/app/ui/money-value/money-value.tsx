import styles from "./money-value.module.css";

export type MoneyTone =
  | "neutral"
  | "income"
  | "expense"
  | "transfer"
  | "profit"
  | "adjustment"
  | "balancePositive";

type MoneyValueProps = {
  amount: string;
  currency: string;
  currencyVisibility?: "visible" | "accessible";
  size?: "compact" | "default" | "prominent";
  tone?: MoneyTone;
};

export function MoneyValue({
  amount,
  currency,
  currencyVisibility = "visible",
  size = "default",
  tone = "neutral",
}: MoneyValueProps) {
  return (
    <span
      aria-label={`${amount} ${currency}`}
      className={`${styles.value} ${styles[tone]} ${styles[size]}`}
    >
      <span className={styles.amount}>{amount}</span>
      <span
        className={
          currencyVisibility === "accessible"
            ? "visually-hidden"
            : styles.currency
        }
      >
        {currency}
      </span>
    </span>
  );
}
