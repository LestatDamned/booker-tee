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
import { WorkbenchRow } from "../ui/workbench-row/workbench-row";
import styles from "./foundation-gallery.module.css";

type ThemeName = "catppuccin-mocha" | "test";

const themes: ReadonlyArray<{ label: string; name: ThemeName }> = [
  { label: "Catppuccin Mocha", name: "catppuccin-mocha" },
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
        description="Одинаковая геометрия в двух темах. Здесь проверяются только устойчивые shared responsibilities."
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
        <Badge tone="success">token contract complete</Badge>
      </header>

      <section className={styles.section}>
        <h3>Controls</h3>
        <div className={styles.controls}>
          <Button tone="primary">Создать операцию</Button>
          <Button>Фильтры</Button>
          <Button tone="ghost">Отмена</Button>
          <Button tone="danger">Удалить</Button>
          <Button disabled>Недоступно</Button>
          <Button isLoading>Сохраняем</Button>
          <IconButton aria-label="Редактировать пример" icon="edit" />
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
          <Badge>подтверждено</Badge>
          <Badge tone="warning">требует проверки</Badge>
          <Badge tone="transfer">перевод</Badge>
        </div>
      </section>

      <section className={styles.section}>
        <h3>Workbench geometry</h3>
        <WorkbenchRow
          aside={
            <ActionStack
              danger={<Button tone="danger">Отменить операцию</Button>}
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
              <Badge tone="expense">расход</Badge>
              <span>Основной счёт</span>
            </>
          }
          state="working"
          value={
            <MoneyValue amount="−65 000,00" currency="RUB" tone="expense" />
          }
        />
      </section>
    </section>
  );
}
