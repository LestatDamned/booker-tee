import type { To } from "react-router";

import { RouterButtonLink } from "../button/button";
import { Tag } from "../tag/tag";
import styles from "./applied-filter-summary.module.css";

type AppliedFilterSummaryProps = {
  filters: readonly string[];
  resetTo: To;
};

export function AppliedFilterSummary({
  filters,
  resetTo,
}: AppliedFilterSummaryProps) {
  if (filters.length === 0) return null;

  return (
    <section className={styles.summary}>
      <div className={styles.filters}>
        <p>Активные фильтры</p>
        <ul aria-label="Применённые фильтры">
          {filters.map((filter) => (
            <li key={filter}>
              <Tag variant="soft">{filter}</Tag>
            </li>
          ))}
        </ul>
      </div>
      <RouterButtonLink icon="undo" to={resetTo}>
        Сбросить все
      </RouterButtonLink>
    </section>
  );
}
