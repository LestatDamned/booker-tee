import { type FormEvent, useMemo, useRef, useState } from "react";

import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../../ui/field/field";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../../ui/field/form-error-summary";
import { FormActions, FormGrid } from "../../ui/field/form-layout";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { WorkbenchPanel } from "../../ui/workbench-panel/workbench-panel";
import {
  createTransactionRule,
  type TransactionRuleCreateRequest,
  type TransactionRuleDirectoryDto,
  type TransactionRuleSummaryDto,
} from "./api/transaction-rules-api";
import styles from "./transaction-rules-page.module.css";

type Draft = {
  applicationMode: "suggest" | "auto_apply";
  amountMax: string;
  amountMin: string;
  categoryId: string;
  direction: "any" | "inflow" | "outflow";
  matchType: "contains" | "exact";
  name: string;
  operationType: "" | "income" | "expense" | "transfer" | "adjustment";
  pattern: string;
  propertyId: string;
};

const emptyDraft: Draft = {
  applicationMode: "suggest",
  amountMax: "",
  amountMin: "",
  categoryId: "",
  direction: "any",
  matchType: "contains",
  name: "",
  operationType: "",
  pattern: "",
  propertyId: "",
};

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
  const [draft, setDraft] = useState(emptyDraft);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const patternRef = useRef<HTMLInputElement>(null);
  const activeCategories = references.categories.filter(
    (item) => item.isActive,
  );
  const activeProperties = references.properties.filter(
    (item) => item.isActive,
  );
  const dirty = Object.entries(draft).some(
    ([field, value]) => value !== emptyDraft[field as keyof Draft],
  );
  const summaryErrors = useMemo(() => formSummaryErrors(errors), [errors]);

  function change<Field extends keyof Draft>(
    field: Field,
    value: Draft[Field],
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
    const clientErrors = validateDraft(draft);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0) {
      focusFirstError(clientErrors, patternRef);
      return;
    }
    setPending(true);
    setSubmitError(null);
    const result = await createTransactionRule(toRequest(draft), {
      csrfToken,
      idempotencyKey: idempotencyKey.current,
    });
    setPending(false);
    if (result.status === "success") {
      onCreated(result.value.item);
      return;
    }
    if (result.status === "validation_error") {
      const serverErrors = Object.fromEntries(
        Object.entries(result.fieldErrors).map(([field, messages]) => [
          field,
          messages[0] ?? "Некорректное значение.",
        ]),
      );
      setErrors(serverErrors);
      setSubmitError(result.message);
      focusFirstError(serverErrors, patternRef);
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
          <FormGrid columns="two">
            <Field
              error={errors.pattern}
              htmlFor="rule-create-pattern"
              hint="Текст из описания банковской операции."
              label="Условие"
              required
            >
              <input
                aria-invalid={Boolean(errors.pattern)}
                autoFocus
                disabled={pending}
                id="rule-create-pattern"
                maxLength={255}
                onChange={(event) => change("pattern", event.target.value)}
                placeholder="OZON"
                ref={patternRef}
                value={draft.pattern}
              />
            </Field>
            <Field htmlFor="rule-create-match" label="Сопоставление" required>
              <select
                disabled={pending}
                id="rule-create-match"
                onChange={(event) =>
                  change("matchType", event.target.value as Draft["matchType"])
                }
                value={draft.matchType}
              >
                <option value="contains">Описание содержит</option>
                <option value="exact">Описание совпадает</option>
              </select>
            </Field>
            <Field
              error={errors.name}
              htmlFor="rule-create-name"
              hint="Необязательно — иначе название будет собрано автоматически."
              label="Название"
            >
              <input
                disabled={pending}
                id="rule-create-name"
                maxLength={255}
                onChange={(event) => change("name", event.target.value)}
                placeholder="Покупки на маркетплейсе"
                value={draft.name}
              />
            </Field>
            <Field htmlFor="rule-create-direction" label="Направление">
              <select
                disabled={pending}
                id="rule-create-direction"
                onChange={(event) =>
                  change("direction", event.target.value as Draft["direction"])
                }
                value={draft.direction}
              >
                <option value="any">Любое</option>
                <option value="outflow">Списание</option>
                <option value="inflow">Поступление</option>
              </select>
            </Field>
            <Field
              error={errors.amountMin}
              htmlFor="rule-create-min"
              label="Сумма от"
            >
              <input
                disabled={pending}
                id="rule-create-min"
                inputMode="decimal"
                onChange={(event) => change("amountMin", event.target.value)}
                placeholder="0.00"
                value={draft.amountMin}
              />
            </Field>
            <Field
              error={errors.amountMax}
              htmlFor="rule-create-max"
              label="Сумма до"
            >
              <input
                disabled={pending}
                id="rule-create-max"
                inputMode="decimal"
                onChange={(event) => change("amountMax", event.target.value)}
                placeholder="5000.00"
                value={draft.amountMax}
              />
            </Field>
            <Field htmlFor="rule-create-operation" label="Тип операции">
              <select
                disabled={pending}
                id="rule-create-operation"
                onChange={(event) =>
                  change(
                    "operationType",
                    event.target.value as Draft["operationType"],
                  )
                }
                value={draft.operationType}
              >
                <option value="">Не задан</option>
                <option value="expense">Расход</option>
                <option value="income">Доход</option>
                <option value="transfer">Перевод</option>
                <option value="adjustment">Корректировка</option>
              </select>
            </Field>
            <Field
              error={errors.categoryId}
              htmlFor="rule-create-category"
              label="Категория"
            >
              <select
                disabled={pending}
                id="rule-create-category"
                onChange={(event) => change("categoryId", event.target.value)}
                value={draft.categoryId}
              >
                <option value="">Без категории</option>
                {activeCategories.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              error={errors.propertyId}
              htmlFor="rule-create-property"
              label="Объект"
            >
              <select
                disabled={pending}
                id="rule-create-property"
                onChange={(event) => change("propertyId", event.target.value)}
                value={draft.propertyId}
              >
                <option value="">Без объекта</option>
                {activeProperties.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              htmlFor="rule-create-mode"
              hint="Auto-prefill заполняет предложение, но не подтверждает операцию."
              label="Режим"
            >
              <select
                disabled={pending}
                id="rule-create-mode"
                onChange={(event) =>
                  change(
                    "applicationMode",
                    event.target.value as Draft["applicationMode"],
                  )
                }
                value={draft.applicationMode}
              >
                <option value="suggest">Предложить</option>
                <option value="auto_apply">Предзаполнить review</option>
              </select>
            </Field>
          </FormGrid>
          <InlineNotice title="Предпросмотр" tone="information">
            {preview(draft, activeCategories, activeProperties)}
          </InlineNotice>
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

function validateDraft(draft: Draft): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!draft.pattern.trim()) errors.pattern = "Введите текст условия.";
  if (draft.name.length > 255) errors.name = "Не более 255 символов.";
  for (const field of ["amountMin", "amountMax"] as const) {
    if (draft[field] && !/^\d+(?:[.,]\d{1,2})?$/.test(draft[field])) {
      errors[field] =
        "Введите неотрицательную сумму, до двух знаков после запятой.";
    }
  }
  const min = decimalValue(draft.amountMin);
  const max = decimalValue(draft.amountMax);
  if (min !== null && max !== null && min > max) {
    errors.amountMax = "Максимум не может быть меньше минимума.";
  }
  return errors;
}

function toRequest(draft: Draft): TransactionRuleCreateRequest {
  const decimal = (value: string) => value.trim().replace(",", ".") || null;
  return {
    name: draft.name.trim() || null,
    pattern: draft.pattern,
    matchType: draft.matchType,
    direction: draft.direction,
    amountMin: decimal(draft.amountMin),
    amountMax: decimal(draft.amountMax),
    operationType: draft.operationType || null,
    categoryId: draft.categoryId || null,
    propertyId: draft.propertyId || null,
    applicationMode: draft.applicationMode,
  };
}

function decimalValue(value: string): number | null {
  if (!value) return null;
  return Number(value.replace(",", "."));
}

function focusFirstError(
  errors: Record<string, string>,
  patternRef: { current: HTMLInputElement | null },
) {
  const first = Object.keys(errors)[0];
  if (!first) return;
  if (first === "pattern") patternRef.current?.focus();
  else document.getElementById(`rule-create-${fieldId(first)}`)?.focus();
}

function fieldId(field: string): string {
  return (
    {
      amountMin: "min",
      amountMax: "max",
      categoryId: "category",
      propertyId: "property",
    }[field] ?? field
  );
}

function formSummaryErrors(
  errors: Record<string, string>,
): FormErrorSummaryItem[] {
  const labels: Record<string, string> = {
    pattern: "Условие",
    name: "Название",
    amountMin: "Сумма от",
    amountMax: "Сумма до",
    categoryId: "Категория",
    propertyId: "Объект",
  };
  return Object.entries(errors)
    .filter(([, message]) => Boolean(message))
    .map(([field, message]) => ({
      fieldId: `rule-create-${fieldId(field)}`,
      label: labels[field] ?? field,
      message,
    }));
}

function preview(
  draft: Draft,
  categories: TransactionRuleDirectoryDto["references"]["categories"],
  properties: TransactionRuleDirectoryDto["references"]["properties"],
): string {
  const pattern = draft.pattern.trim() || "…";
  const category = categories.find(
    (item) => item.id === draft.categoryId,
  )?.name;
  const propertyName = properties.find(
    (item) => item.id === draft.propertyId,
  )?.name;
  const outcome =
    [
      category && `категория «${category}»`,
      propertyName && `объект «${propertyName}»`,
    ]
      .filter(Boolean)
      .join(", ") || "без категории и объекта";
  return `Если описание ${draft.matchType === "exact" ? "совпадает с" : "содержит"} «${pattern}», подготовить ${outcome}. Подтверждение останется в Import Review.`;
}
