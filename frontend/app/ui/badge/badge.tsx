import styles from "./badge.module.css";

type BadgeProps = {
  children: number | string;
  label?: string;
};

export function Badge({ children, label }: BadgeProps) {
  return (
    <span {...(label ? { "aria-label": label } : {})} className={styles.badge}>
      {children}
    </span>
  );
}
