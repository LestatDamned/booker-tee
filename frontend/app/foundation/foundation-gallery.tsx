import { useRef, useState } from "react";

import { ActionStack } from "../ui/action-stack/action-stack";
import { Badge } from "../ui/badge/badge";
import { Button } from "../ui/button/button";
import { IconButton } from "../ui/button/icon-button";
import { ExpansionPanel } from "../ui/expansion-panel/expansion-panel";
import { Field } from "../ui/field/field";
import { MoneyValue } from "../ui/money-value/money-value";
import { PageHeader } from "../ui/page-header/page-header";
import { RequestState } from "../ui/request-state/request-state";
import { StatusLabel } from "../ui/status-label/status-label";
import { Tag } from "../ui/tag/tag";
import { WorkbenchRow } from "../ui/workbench-row/workbench-row";
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
        <RequestState message="Обновляем данные…" status="loading" />
        <RequestState
          message="Проверьте соединение и повторите запрос."
          onRetry={() => undefined}
          status="error"
          title="Не удалось загрузить операции"
        />
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
