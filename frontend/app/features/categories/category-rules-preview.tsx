import { Link } from "react-router";

import { RouterButtonLink } from "../../ui/button/button";
import { StatusLabel } from "../../ui/status-label/status-label";
import type { CategoryDetailDto } from "./api/category-detail-api";
import styles from "./category-detail-page.module.css";

export function CategoryRulesPreview({
  detail,
}: {
  detail: CategoryDetailDto;
}) {
  return (
    <section aria-labelledby="category-rules-title" className={styles.rules}>
      <header>
        <div>
          <p>{detail.rules.activeCount} активных</p>
          <h2 id="category-rules-title">Связанные правила</h2>
        </div>
        {detail.rules.total ? (
          <RouterButtonLink to="/rules" tone="secondary">
            Все правила
          </RouterButtonLink>
        ) : null}
      </header>
      {detail.rules.items.length ? (
        <ul>
          {detail.rules.items.map((rule) => (
            <li key={rule.id}>
              <div>
                <Link to={`/rules#rule-${rule.id}`}>{rule.name}</Link>
                <code>{rule.pattern}</code>
              </div>
              <StatusLabel tone={rule.isActive ? "success" : "neutral"}>
                {rule.isActive ? "Активно" : "Выключено"}
              </StatusLabel>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.rulesEmpty}>Для этой категории правил пока нет.</p>
      )}
    </section>
  );
}
