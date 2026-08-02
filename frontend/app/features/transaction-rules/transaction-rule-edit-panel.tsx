import { type FormEvent, useMemo } from "react";

import { Button } from "../../ui/button/button";
import { ExpansionPanel } from "../../ui/expansion-panel/expansion-panel";
import { FormErrorSummary } from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type { TransactionRuleEditDto } from "./api/transaction-rules-api";
import {
  TransactionRuleFormFields,
  transactionRuleFormSummary,
  type TransactionRuleDraft,
} from "./transaction-rule-form";
import styles from "./transaction-rules-page.module.css";

export function TransactionRuleEditPanel({
  conflict,
  draft,
  errors,
  loadError,
  loading,
  onChange,
  onClose,
  onReload,
  onSubmit,
  pending,
  ruleId,
  source,
  variant,
}: {
  conflict: boolean;
  draft: TransactionRuleDraft | null;
  errors: Record<string, string>;
  loadError: string | null;
  loading: boolean;
  onChange: <Field extends keyof TransactionRuleDraft>(
    field: Field,
    value: TransactionRuleDraft[Field],
  ) => void;
  onClose: () => void;
  onReload: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  pending: boolean;
  ruleId: string;
  source: TransactionRuleEditDto | null;
  variant: "desktop" | "mobile";
}) {
  const idPrefix = `rule-edit-${variant}-${ruleId}`;
  const summary = useMemo(
    () => transactionRuleFormSummary(errors, idPrefix),
    [errors, idPrefix],
  );
  return (
    <ExpansionPanel
      id={`${idPrefix}-panel`}
      onClose={onClose}
      title="Изменить правило"
    >
      {loading ? (
        <p aria-live="polite">Загружаем актуальную версию правила…</p>
      ) : null}
      {loadError && !draft ? (
        <InlineNotice
          action={
            <Button icon="retry" onClick={onReload} type="button">
              Повторить
            </Button>
          }
          role="alert"
          title="Не удалось открыть редактор"
          tone="danger"
        >
          {loadError}
        </InlineNotice>
      ) : null}
      {draft && source ? (
        <form
          className={styles.editForm}
          data-transaction-rule-edit
          noValidate
          onSubmit={onSubmit}
        >
          {conflict ? (
            <InlineNotice
              action={
                <Button
                  disabled={pending}
                  icon="retry"
                  onClick={onReload}
                  tone="secondary"
                  type="button"
                >
                  Загрузить актуальную версию
                </Button>
              }
              role="alert"
              title="Правило уже изменилось"
              tone="danger"
            >
              Ваш черновик сохранён. Загрузка актуальной версии заменит его
              только после нажатия кнопки.
            </InlineNotice>
          ) : null}
          {!conflict && (loadError || summary.length) ? (
            <FormErrorSummary
              errors={summary}
              message={loadError ?? "Проверьте поля правила и повторите."}
              title="Не удалось сохранить изменения"
            />
          ) : null}
          <TransactionRuleFormFields
            draft={draft}
            errors={errors}
            idPrefix={idPrefix}
            onChange={onChange}
            pending={pending}
            references={source.references}
          />
          <FormActions layout="split">
            <Button
              disabled={pending}
              onClick={onClose}
              tone="secondary"
              type="button"
            >
              Отмена
            </Button>
            <Button
              disabled={pending}
              icon="check"
              isLoading={pending}
              tone="primary"
              type="submit"
            >
              {pending ? "Сохраняем…" : "Сохранить"}
            </Button>
          </FormActions>
        </form>
      ) : null}
    </ExpansionPanel>
  );
}
