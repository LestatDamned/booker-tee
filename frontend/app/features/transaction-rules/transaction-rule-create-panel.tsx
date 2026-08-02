import { type FormEvent, useMemo, useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { FormErrorSummary } from "../../ui/field/form-error-summary";
import { FormActions } from "../../ui/field/form-layout";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import {
  createTransactionRule,
  type TransactionRuleDirectoryDto,
  type TransactionRuleSummaryDto,
} from "./api/transaction-rules-api";
import {
  emptyTransactionRuleDraft,
  focusFirstTransactionRuleError,
  normalizeTransactionRuleFieldErrors,
  TransactionRuleFormFields,
  transactionRuleCreateRequest,
  transactionRuleFormSummary,
  type TransactionRuleDraft,
  validateTransactionRuleDraft,
} from "./transaction-rule-form";
import styles from "./transaction-rules-page.module.css";

const idPrefix = "rule-create";

export function TransactionRuleCreatePanel({
  csrfToken,
  onClose,
  onCreated,
  references,
}: {
  csrfToken: string;
  onClose: () => void;
  onCreated: (item: TransactionRuleSummaryDto) => void;
  references: TransactionRuleDirectoryDto["references"];
}) {
  const [draft, setDraft] = useState(emptyTransactionRuleDraft);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const dirty = Object.entries(draft).some(
    ([field, value]) =>
      value !== emptyTransactionRuleDraft[field as keyof TransactionRuleDraft],
  );
  const summaryErrors = useMemo(
    () => transactionRuleFormSummary(errors, idPrefix),
    [errors],
  );

  function change<Field extends keyof TransactionRuleDraft>(
    field: Field,
    value: TransactionRuleDraft[Field],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: "" }));
    setSubmitError(null);
  }
  function requestClose() {
    if (dirty) setConfirmClose(true);
    else onClose();
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clientErrors = validateTransactionRuleDraft(draft);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length) {
      focusFirstTransactionRuleError(clientErrors, idPrefix);
      return;
    }
    setPending(true);
    setSubmitError(null);
    const result = await createTransactionRule(
      transactionRuleCreateRequest(draft),
      { csrfToken, idempotencyKey: idempotencyKey.current },
    );
    setPending(false);
    if (result.status === "success") {
      onCreated(result.value.item);
      return;
    }
    if (result.status === "validation_error") {
      const serverErrors = normalizeTransactionRuleFieldErrors(
        result.fieldErrors,
      );
      setErrors(serverErrors);
      setSubmitError(result.message);
      focusFirstTransactionRuleError(serverErrors, idPrefix);
      return;
    }
    setSubmitError(result.message);
  }

  return (
    <>
      <WorkbenchPanel
        description="Правило только подготавливает предложение для Import Review. Проведение операции всё равно требует проверки пользователя."
        disabled={pending}
        onClose={requestClose}
        title="Новое правило"
      >
        <form className={styles.ruleForm} noValidate onSubmit={submit}>
          {submitError || summaryErrors.length ? (
            <FormErrorSummary
              errors={summaryErrors}
              message={submitError ?? "Проверьте поля правила и повторите."}
            />
          ) : null}
          <TransactionRuleFormFields
            autoFocus
            draft={draft}
            errors={errors}
            idPrefix={idPrefix}
            onChange={change}
            pending={pending}
            references={{
              categories: references.categories.filter((item) => item.isActive),
              properties: references.properties.filter((item) => item.isActive),
            }}
          />
          <FormActions layout="split" sticky>
            <Button disabled={pending} onClick={requestClose}>
              Отмена
            </Button>
            <Button
              icon="plus"
              isLoading={pending}
              tone="primary"
              type="submit"
            >
              {pending ? "Создаём…" : "Создать правило"}
            </Button>
          </FormActions>
        </form>
      </WorkbenchPanel>
      {confirmClose ? (
        <ConfirmationDialog
          cancelLabel="Продолжить создание"
          confirmLabel="Закрыть без сохранения"
          description="Несохранённые данные нового правила будут потеряны."
          onCancel={() => setConfirmClose(false)}
          onConfirm={onClose}
          title="Закрыть создание правила?"
        />
      ) : null}
    </>
  );
}
