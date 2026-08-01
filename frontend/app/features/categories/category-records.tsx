import { StatusLabel } from "../../ui/status-label/status-label";
import { Tag, type TagTone } from "../../ui/tag/tag";
import type { CategoryKind, CategorySummaryDto } from "./api/categories-api";
import styles from "./categories-page.module.css";

type CategoryRecordsProps = {
  categories: CategorySummaryDto[];
  kindLabels: ReadonlyMap<CategoryKind, string>;
};

export function CategoryTable({
  categories,
  kindLabels,
}: CategoryRecordsProps) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">
        Категории текущего workspace
      </caption>
      <thead>
        <tr>
          <th scope="col">Категория</th>
          <th scope="col">Тип и состояние</th>
          <th scope="col">Использование</th>
          <th scope="col">Заметка</th>
        </tr>
      </thead>
      <tbody>
        {categories.map((category) => (
          <tr data-category-record key={category.id}>
            <th scope="row">
              <CategoryIdentity category={category} />
            </th>
            <td>
              <div className={styles.classification}>
                <CategoryKindTag category={category} kindLabels={kindLabels} />
                <CategoryStatus category={category} />
              </div>
            </td>
            <td>
              <CategoryUsage category={category} />
            </td>
            <td className={styles.notesCell}>
              {category.notes ?? <span aria-label="Заметка не указана">—</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CategoryMobileList({
  categories,
  kindLabels,
}: CategoryRecordsProps) {
  return (
    <ol aria-label="Категории текущего workspace">
      {categories.map((category) => (
        <li key={category.id}>
          <article data-category-record data-responsive-record>
            <div className={styles.mobileHeading}>
              <CategoryIdentity category={category} />
              <CategoryStatus category={category} />
            </div>
            <div className={styles.mobileMeta}>
              <CategoryKindTag category={category} kindLabels={kindLabels} />
              <CategoryUsage category={category} />
            </div>
            {category.notes ? (
              <p className={styles.mobileNotes}>{category.notes}</p>
            ) : null}
          </article>
        </li>
      ))}
    </ol>
  );
}

function CategoryIdentity({ category }: { category: CategorySummaryDto }) {
  return (
    <a
      aria-label={`Открыть категорию «${category.name}»`}
      className={styles.identityLink}
      data-record-identity
      href={`/categories/${category.id}`}
    >
      {category.name}
    </a>
  );
}

function CategoryKindTag({
  category,
  kindLabels,
}: {
  category: CategorySummaryDto;
  kindLabels: ReadonlyMap<CategoryKind, string>;
}) {
  return (
    <Tag tone={kindTone(category.kind)} variant="soft">
      {kindLabels.get(category.kind) ?? category.kind}
    </Tag>
  );
}

function CategoryStatus({ category }: { category: CategorySummaryDto }) {
  if (category.isSystem) {
    return <StatusLabel tone="information">Системная</StatusLabel>;
  }
  return category.isActive ? (
    <StatusLabel tone="success">Активна</StatusLabel>
  ) : (
    <StatusLabel tone="neutral">Архив</StatusLabel>
  );
}

function CategoryUsage({ category }: { category: CategorySummaryDto }) {
  return (
    <span className={styles.usage}>
      <span>
        {countLabel(
          category.operationCount,
          "операция",
          "операции",
          "операций",
        )}
      </span>
      <span>
        {countLabel(category.ruleCount, "правило", "правила", "правил")}
      </span>
      {category.activeRuleCount > 0 ? (
        <small>{category.activeRuleCount} активных</small>
      ) : null}
    </span>
  );
}

function kindTone(kind: CategoryKind): TagTone {
  return kind === "mixed" ? "category" : kind;
}

function countLabel(count: number, one: string, few: string, many: string) {
  const lastTwo = count % 100;
  const last = count % 10;
  const word =
    lastTwo >= 11 && lastTwo <= 14
      ? many
      : last === 1
        ? one
        : last >= 2 && last <= 4
          ? few
          : many;
  return `${count} ${word}`;
}
