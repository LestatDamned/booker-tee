import { Field } from "../../ui/field/field";
import type { FormErrorSummaryItem } from "../../ui/field/form-error-summary";
import { FormGrid } from "../../ui/field/form-layout";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type {
  TransactionRuleCreateRequest,
  TransactionRuleDirectoryDto,
  TransactionRuleSummaryDto,
  TransactionRuleUpdateRequest,
} from "./api/transaction-rules-api";

export type TransactionRuleDraft = {
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

export const emptyTransactionRuleDraft: TransactionRuleDraft = {
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

export function transactionRuleDraftFromItem(
  item: TransactionRuleSummaryDto,
): TransactionRuleDraft {
  return {
    applicationMode: item.outcome.applicationMode,
    amountMax: item.condition.amountMax ?? "",
    amountMin: item.condition.amountMin ?? "",
    categoryId: item.outcome.category?.id ?? "",
    direction: item.condition.direction,
    matchType: item.condition.matchType,
    name: item.name,
    operationType: item.outcome.operationType ?? "",
    pattern: item.condition.pattern,
    propertyId: item.outcome.property?.id ?? "",
  };
}

export function TransactionRuleFormFields({
  autoFocus = false,
  draft,
  errors,
  idPrefix,
  onChange,
  pending,
  references,
}: {
  autoFocus?: boolean;
  draft: TransactionRuleDraft;
  errors: Record<string, string>;
  idPrefix: string;
  onChange: <Field extends keyof TransactionRuleDraft>(
    field: Field,
    value: TransactionRuleDraft[Field],
  ) => void;
  pending: boolean;
  references: TransactionRuleDirectoryDto["references"];
}) {
  const categories = references.categories;
  const properties = references.properties;
  return (
    <>
      <FormGrid columns="two">
        <Field
          error={errors.pattern}
          htmlFor={`${idPrefix}-pattern`}
          hint="Текст из описания банковской операции."
          label="Условие"
          required
        >
          <input
            aria-invalid={Boolean(errors.pattern)}
            autoFocus={autoFocus}
            disabled={pending}
            id={`${idPrefix}-pattern`}
            maxLength={255}
            onChange={(event) => onChange("pattern", event.target.value)}
            placeholder="OZON"
            value={draft.pattern}
          />
        </Field>
        <Field htmlFor={`${idPrefix}-match`} label="Сопоставление" required>
          <select
            disabled={pending}
            id={`${idPrefix}-match`}
            onChange={(event) =>
              onChange(
                "matchType",
                event.target.value as TransactionRuleDraft["matchType"],
              )
            }
            value={draft.matchType}
          >
            <option value="contains">Описание содержит</option>
            <option value="exact">Описание совпадает</option>
          </select>
        </Field>
        <Field
          error={errors.name}
          htmlFor={`${idPrefix}-name`}
          hint="Необязательно — иначе название будет собрано автоматически."
          label="Название"
        >
          <input
            disabled={pending}
            id={`${idPrefix}-name`}
            maxLength={255}
            onChange={(event) => onChange("name", event.target.value)}
            placeholder="Покупки на маркетплейсе"
            value={draft.name}
          />
        </Field>
        <Field htmlFor={`${idPrefix}-direction`} label="Направление">
          <select
            disabled={pending}
            id={`${idPrefix}-direction`}
            onChange={(event) =>
              onChange(
                "direction",
                event.target.value as TransactionRuleDraft["direction"],
              )
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
          htmlFor={`${idPrefix}-min`}
          label="Сумма от"
        >
          <input
            disabled={pending}
            id={`${idPrefix}-min`}
            inputMode="decimal"
            onChange={(event) => onChange("amountMin", event.target.value)}
            placeholder="0.00"
            value={draft.amountMin}
          />
        </Field>
        <Field
          error={errors.amountMax}
          htmlFor={`${idPrefix}-max`}
          label="Сумма до"
        >
          <input
            disabled={pending}
            id={`${idPrefix}-max`}
            inputMode="decimal"
            onChange={(event) => onChange("amountMax", event.target.value)}
            placeholder="5000.00"
            value={draft.amountMax}
          />
        </Field>
        <Field htmlFor={`${idPrefix}-operation`} label="Тип операции">
          <select
            disabled={pending}
            id={`${idPrefix}-operation`}
            onChange={(event) =>
              onChange(
                "operationType",
                event.target.value as TransactionRuleDraft["operationType"],
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
          htmlFor={`${idPrefix}-category`}
          label="Категория"
        >
          <select
            disabled={pending}
            id={`${idPrefix}-category`}
            onChange={(event) => onChange("categoryId", event.target.value)}
            value={draft.categoryId}
          >
            <option value="">Без категории</option>
            {categories.map((item) => (
              <option
                disabled={!item.isActive && item.id !== draft.categoryId}
                key={item.id}
                value={item.id}
              >
                {item.name}
                {item.isActive ? "" : " · архив"}
              </option>
            ))}
          </select>
        </Field>
        <Field
          error={errors.propertyId}
          htmlFor={`${idPrefix}-property`}
          label="Объект"
        >
          <select
            disabled={pending}
            id={`${idPrefix}-property`}
            onChange={(event) => onChange("propertyId", event.target.value)}
            value={draft.propertyId}
          >
            <option value="">Без объекта</option>
            {properties.map((item) => (
              <option
                disabled={!item.isActive && item.id !== draft.propertyId}
                key={item.id}
                value={item.id}
              >
                {item.name}
                {item.isActive ? "" : " · архив"}
              </option>
            ))}
          </select>
        </Field>
        <Field
          htmlFor={`${idPrefix}-mode`}
          hint="Предзаполнение готовит предложение, но не подтверждает операцию."
          label="Режим"
        >
          <select
            disabled={pending}
            id={`${idPrefix}-mode`}
            onChange={(event) =>
              onChange(
                "applicationMode",
                event.target.value as TransactionRuleDraft["applicationMode"],
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
        {transactionRulePreview(draft, categories, properties)}
      </InlineNotice>
    </>
  );
}

export function validateTransactionRuleDraft(
  draft: TransactionRuleDraft,
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!draft.pattern.trim()) errors.pattern = "Введите текст условия.";
  if (draft.name.length > 255) errors.name = "Не более 255 символов.";
  for (const field of ["amountMin", "amountMax"] as const)
    if (draft[field] && !/^\d+(?:[.,]\d{1,2})?$/.test(draft[field]))
      errors[field] =
        "Введите неотрицательную сумму, до двух знаков после запятой.";
  const min = decimalValue(draft.amountMin);
  const max = decimalValue(draft.amountMax);
  if (min !== null && max !== null && min > max)
    errors.amountMax = "Максимум не может быть меньше минимума.";
  return errors;
}

export function transactionRuleCreateRequest(
  draft: TransactionRuleDraft,
): TransactionRuleCreateRequest {
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

export function transactionRuleUpdateRequest(
  draft: TransactionRuleDraft,
  expectedUpdatedAt: string,
): TransactionRuleUpdateRequest {
  return { ...transactionRuleCreateRequest(draft), expectedUpdatedAt };
}

export function transactionRuleFormSummary(
  errors: Record<string, string>,
  idPrefix: string,
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
      fieldId: `${idPrefix}-${fieldId(field)}`,
      label: labels[field] ?? field,
      message,
    }));
}

export function focusFirstTransactionRuleError(
  errors: Record<string, string>,
  idPrefix: string,
) {
  const first = Object.keys(errors)[0];
  if (first) document.getElementById(`${idPrefix}-${fieldId(first)}`)?.focus();
}

export function normalizeTransactionRuleFieldErrors(
  errors: Record<string, string[]>,
): Record<string, string> {
  const aliases: Record<string, string> = {
    category_id: "categoryId",
    property_id: "propertyId",
    amount_min: "amountMin",
    amount_max: "amountMax",
    operation_type: "operationType",
  };
  return Object.fromEntries(
    Object.entries(errors).map(([field, messages]) => [
      aliases[field] ?? field,
      messages[0] ?? "Некорректное значение.",
    ]),
  );
}

function decimalValue(value: string): number | null {
  return value ? Number(value.replace(",", ".")) : null;
}
function fieldId(field: string): string {
  return (
    (
      {
        amountMin: "min",
        amountMax: "max",
        categoryId: "category",
        propertyId: "property",
      } as Record<string, string>
    )[field] ?? field
  );
}
function transactionRulePreview(
  draft: TransactionRuleDraft,
  categories: TransactionRuleDirectoryDto["references"]["categories"],
  properties: TransactionRuleDirectoryDto["references"]["properties"],
): string {
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
  return `Если описание ${draft.matchType === "exact" ? "совпадает с" : "содержит"} «${draft.pattern.trim() || "…"}», подготовить ${outcome}. Подтверждение останется в Import Review.`;
}
