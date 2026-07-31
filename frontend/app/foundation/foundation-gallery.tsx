import { useRef, useState } from "react";

import { ActionStack } from "../ui/action-stack/action-stack";
import { AppliedFilterSummary } from "../ui/applied-filter-summary/applied-filter-summary";
import { Badge } from "../ui/badge/badge";
import { Button, ButtonLink } from "../ui/button/button";
import { IconButton } from "../ui/button/icon-button";
import { ExpansionPanel } from "../ui/expansion-panel/expansion-panel";
import { Field } from "../ui/field/field";
import { InlineNotice } from "../ui/inline-notice/inline-notice";
import { MoneyValue } from "../ui/money-value/money-value";
import { PageHeader } from "../ui/page-header/page-header";
import { RequestState } from "../ui/request-state/request-state";
import { ResponsiveRecordCollection } from "../ui/responsive-record-collection/responsive-record-collection";
import { StatusLabel } from "../ui/status-label/status-label";
import { Tag } from "../ui/tag/tag";
import { WorkbenchRow } from "../ui/workbench-row/workbench-row";
import { WorkbenchEmptyState } from "../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchPagination } from "../ui/workbench-pagination/workbench-pagination";
import styles from "./foundation-gallery.module.css";

type ThemeName = "catppuccin-mocha" | "catppuccin-latte" | "test";

const themes: ReadonlyArray<{ label: string; name: ThemeName }> = [
  { label: "Catppuccin Mocha", name: "catppuccin-mocha" },
  { label: "Catppuccin Latte", name: "catppuccin-latte" },
  { label: "Plain test theme", name: "test" },
];

export function FoundationGallery() {
  return (
    <main className={styles.page}>
      <PageHeader
        actions={
          <a className={styles.backLink} href="/app">
            Вернуться в приложение
          </a>
        }
        description="Одинаковая геометрия в трёх темах. Здесь проверяются только устойчивые shared responsibilities."
        eyebrow="Stage 02"
        title="React UI foundation"
      />

      <section className={styles.routeStateLinks}>
        <div>
          <p className={styles.themeLabel}>Full-page states</p>
          <h2>Состояния маршрутов</h2>
          <p className={styles.routeStateDescription}>
            Откройте состояние отдельно, чтобы проверить полноэкранную
            геометрию, семантический цвет и путь восстановления.
          </p>
        </div>
        <nav
          aria-label="Примеры состояний маршрутов"
          className={styles.controls}
        >
          <ButtonLink href="/app/foundation?route-state=loading">
            Загрузка
          </ButtonLink>
          <ButtonLink href="/app/foundation?route-state=unauthenticated">
            Нет сессии
          </ButtonLink>
          <ButtonLink href="/app/foundation?route-state=forbidden">
            Нет доступа
          </ButtonLink>
          <ButtonLink href="/app/foundation?route-state=notFound">
            Не найдено
          </ButtonLink>
          <ButtonLink href="/app/foundation?route-state=error">
            Ошибка
          </ButtonLink>
        </nav>
      </section>

      <div className={styles.themeGrid}>
        {themes.map((theme) => (
          <ThemePreview
            key={theme.name}
            label={theme.label}
            theme={theme.name}
          />
        ))}
      </div>
    </main>
  );
}

type ThemePreviewProps = {
  label: string;
  theme: ThemeName;
};

function ThemePreview({ label, theme }: ThemePreviewProps) {
  const [isPanelOpen, setIsPanelOpen] = useState(true);
  const editButtonRef = useRef<HTMLButtonElement>(null);
  const descriptionId = `${theme}-description-error`;
  const panelId = `${theme}-example-panel`;

  function closePanel() {
    setIsPanelOpen(false);
    requestAnimationFrame(() => editButtonRef.current?.focus());
  }

  return (
    <section className={styles.theme} data-theme={theme}>
      <header className={styles.themeHeader}>
        <div>
          <p className={styles.themeLabel}>Theme</p>
          <h2>{label}</h2>
        </div>
        <StatusLabel tone="success">token contract complete</StatusLabel>
      </header>

      <section className={styles.section}>
        <h3>Controls</h3>
        <div className={styles.controls}>
          <Button icon="plus" tone="primary">
            Создать операцию
          </Button>
          <Button icon="filter">Фильтры</Button>
          <Button tone="ghost">Отмена</Button>
          <Button tone="dangerSecondary">Отменить операцию</Button>
          <Button icon="delete" tone="danger">
            Удалить
          </Button>
          <Button disabled>Недоступно</Button>
          <Button isLoading>Сохраняем</Button>
          <IconButton aria-label="Редактировать пример" icon="edit" />
        </div>
      </section>

      <section className={styles.section}>
        <h3>Semantic color roles</h3>
        <div className={styles.roleGrid}>
          <span className={`${styles.roleChip} ${styles.rolePrimary}`}>
            Primary · Lavender
          </span>
          <span className={`${styles.roleChip} ${styles.roleBrand}`}>
            Brand · Mauve
          </span>
          <span className={`${styles.roleChip} ${styles.roleAutomation}`}>
            Automation · Pink
          </span>
          <span className={`${styles.roleChip} ${styles.roleInformation}`}>
            Information · Sky
          </span>
          <span className={`${styles.roleChip} ${styles.roleRecent}`}>
            Recent · Blue
          </span>
          <span className={`${styles.roleChip} ${styles.roleTransfer}`}>
            Transfer · Sapphire
          </span>
        </div>
      </section>

      <section className={styles.section}>
        <h3>Field and request states</h3>
        <Field
          error="Описание должно быть короче 500 символов."
          errorId={descriptionId}
          htmlFor={`${theme}-description`}
          label="Описание"
          required
        >
          <input
            aria-describedby={descriptionId}
            aria-invalid="true"
            defaultValue="Комиссия банка"
            id={`${theme}-description`}
          />
        </Field>
        <RequestState message="Обновляем данные…" />
      </section>

      <section className={styles.section}>
        <h3>Money and status</h3>
        <div className={styles.moneyGrid}>
          <MoneyValue amount="+125 000,00" currency="RUB" tone="income" />
          <MoneyValue amount="−4 890,50" currency="RUB" tone="expense" />
          <MoneyValue amount="25 000,00" currency="RUB" tone="transfer" />
        </div>
        <div className={styles.controls}>
          <StatusLabel tone="success">подтверждено</StatusLabel>
          <StatusLabel tone="automation" variant="soft">
            автоправило
          </StatusLabel>
          <StatusLabel tone="warning" variant="soft">
            требует проверки
          </StatusLabel>
          <Tag tone="transfer">перевод</Tag>
          <Tag tone="category" variant="soft">
            продукты
          </Tag>
          <span className={styles.countExample}>
            Требуют решения <Badge label="3 строки требуют решения">3</Badge>
          </span>
        </div>
      </section>

      <section className={styles.section}>
        <h3>Inline notices</h3>
        <InlineNotice title="Доступно только для чтения" tone="information">
          Изменения недоступны для вашей роли.
        </InlineNotice>
        <InlineNotice
          action={<Button icon="retry">Повторить</Button>}
          role="alert"
          title="Не удалось сохранить"
          tone="danger"
        >
          Проверьте соединение и повторите попытку.
        </InlineNotice>
      </section>

      <section className={styles.section}>
        <h3>Applied filters</h3>
        <AppliedFilterSummary
          filters={["Тип: расход", "Счёт: Основной", "Период: июль 2026"]}
          resetTo="/app/foundation"
        />
      </section>

      <section className={styles.section}>
        <h3>Workbench empty states</h3>
        <div className={styles.emptyStateGrid}>
          <WorkbenchEmptyState
            action={
              <Button icon="plus" tone="primary">
                Добавить первый счёт
              </Button>
            }
            icon="accounts"
            title="Пока нет счетов"
          >
            Добавьте карту, вклад, наличные или расчётный счёт.
          </WorkbenchEmptyState>
          <WorkbenchEmptyState
            action={<Button icon="filter">Сбросить фильтры</Button>}
            icon="search"
            kind="filtered"
            title="По этим фильтрам ничего нет"
          >
            Измените условия поиска или сбросьте фильтры.
          </WorkbenchEmptyState>
        </div>
      </section>

      <section className={`${styles.section} ${styles.flushSection}`}>
        <h3 className={styles.flushSectionTitle}>Workbench pagination</h3>
        <WorkbenchPagination
          ariaLabel={`Пример страниц, ${label}`}
          currentPage={2}
          getPageHref={(page) => `?foundation_page=${page}`}
          hasNext
          hasPrevious
          pageSize={{
            id: `${theme}-page-size`,
            onChange: () => undefined,
            options: [25, 50, 100],
            value: 25,
          }}
          summary="26–50 из 187"
          totalPages={8}
        />
      </section>

      <section className={`${styles.section} ${styles.flushSection}`}>
        <h3 className={styles.flushSectionTitle}>Responsive records</h3>
        <ResponsiveRecordCollection
          mobileList={
            <ol>
              <li>
                <article className={styles.recordExample}>
                  <strong>Основной счёт</strong>
                  <span>Карта · RUB</span>
                  <MoneyValue amount="125 000,00" currency="RUB" />
                </article>
              </li>
            </ol>
          }
          table={
            <table>
              <caption className="visually-hidden">
                Пример финансового реестра
              </caption>
              <thead>
                <tr>
                  <th scope="col">Счёт</th>
                  <th scope="col">Тип</th>
                  <th scope="col">Баланс</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Основной счёт</th>
                  <td>Карта</td>
                  <td>
                    <MoneyValue amount="125 000,00" currency="RUB" />
                  </td>
                </tr>
              </tbody>
            </table>
          }
        />
      </section>

      <section className={styles.section}>
        <h3>Workbench geometry</h3>
        <WorkbenchRow
          aside={
            <ActionStack
              danger={<Button tone="dangerSecondary">Отменить операцию</Button>}
              overflow={<Button tone="ghost">Открыть источник</Button>}
              primary={
                <Button
                  aria-controls={panelId}
                  aria-expanded={isPanelOpen}
                  onClick={() => setIsPanelOpen(true)}
                  ref={editButtonRef}
                >
                  Редактировать
                </Button>
              }
            />
          }
          date="2026-07-20"
          description="Аренда квартиры за июль"
          expansion={
            <ExpansionPanel
              id={panelId}
              isOpen={isPanelOpen}
              onClose={closePanel}
              title="Исправить операцию"
            >
              <p className={styles.panelCopy}>
                Feature form появится на следующем этапе. Панель уже проверяет
                composition и responsive geometry.
              </p>
              <div className={styles.panelActions}>
                <Button tone="primary">Сохранить</Button>
                <Button onClick={closePanel}>Отмена</Button>
              </div>
            </ExpansionPanel>
          }
          meta={
            <>
              <Tag tone="expense">расход</Tag>
              <span>Основной счёт</span>
            </>
          }
          signals={<span>Требует проверки</span>}
          state="working"
          value={
            <MoneyValue amount="−65 000,00" currency="RUB" tone="expense" />
          }
          workflowState="problem"
        />
        <WorkbenchRow
          date="2026-07-19"
          description="Операция по прямой ссылке"
          meta={<span>Навигационная цель</span>}
          state="target"
          value={
            <MoneyValue amount="+25 000,00" currency="RUB" tone="income" />
          }
        />
        <WorkbenchRow
          date="2026-07-18"
          description="Недавно обновлённая операция"
          meta={<span>Временная подсветка без сдвига строки</span>}
          state="recent"
          value={
            <MoneyValue amount="−4 890,50" currency="RUB" tone="expense" />
          }
        />
      </section>
    </section>
  );
}
