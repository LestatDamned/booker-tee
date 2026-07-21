import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { FormActions } from "../../ui/field/form-layout";
import type { ManualLedgerDto } from "./manual-ledger-api";
import styles from "./manual-ledger.module.css";

type FilterOptions = ManualLedgerDto["filterOptions"];

export type ManualLedgerFilterDraft = {
  accountId: string;
  categoryId: string;
  dateFrom: string;
  dateTo: string;
  operationType: string;
  propertyId: string;
  search: string;
  status: string;
};

const operationTypes = [
  { value: "income", label: "доход" },
  { value: "expense", label: "расход" },
  { value: "transfer", label: "перевод" },
  { value: "adjustment", label: "корректировка" },
];
const statuses = [
  { value: "draft", label: "черновик" },
  { value: "needs_review", label: "нужна проверка" },
  { value: "confirmed", label: "подтверждено" },
  { value: "ignored", label: "отменено" },
  { value: "duplicate", label: "дубликат" },
];
const filterNames = [
  "date_from",
  "date_to",
  "type",
  "status",
  "account_id",
  "category_id",
  "property_id",
  "search",
] as const;

type ManualLedgerFiltersProps = {
  navigationPending?: boolean;
  onClose: () => void;
  options: FilterOptions;
  perPage: number;
};

export function ManualLedgerFilters({
  navigationPending = false,
  onClose,
  options,
  perPage,
}: ManualLedgerFiltersProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(() =>
    manualLedgerFilterDraft(location.search, options),
  );
  const [advancedOpen, setAdvancedOpen] = useState(() =>
    classificationFiltersAreActive(draft),
  );

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onClose();
    void navigate({
      pathname: location.pathname,
      search: manualLedgerFilterSearch(draft, perPage),
    });
  }

  return (
    <form
      className={styles.filterForm}
      id="manual-ledger-filter-panel"
      onSubmit={applyFilters}
    >
      <div className={styles.filterGrid}>
        <div>
          <FilterSelect
            id="manual-filter-status"
            label="Статус"
            name="status"
            onChange={(status) => setDraft({ ...draft, status })}
            options={statuses}
            value={draft.status}
          />
        </div>
        <div>
          <Field htmlFor="manual-filter-date-from" label="Дата от">
            <input
              id="manual-filter-date-from"
              name="dateFrom"
              onChange={(event) =>
                setDraft({
                  ...draft,
                  dateFrom: event.currentTarget.value,
                })
              }
              type="date"
              value={draft.dateFrom}
            />
          </Field>
        </div>
        <div>
          <Field htmlFor="manual-filter-date-to" label="Дата до">
            <input
              id="manual-filter-date-to"
              name="dateTo"
              onChange={(event) =>
                setDraft({ ...draft, dateTo: event.currentTarget.value })
              }
              type="date"
              value={draft.dateTo}
            />
          </Field>
        </div>
      </div>

      <details
        className={styles.advancedFilters}
        onToggle={(event) => setAdvancedOpen(event.currentTarget.open)}
        open={advancedOpen}
      >
        <summary>Ещё фильтры</summary>
        <div className={styles.filterGrid}>
          <FilterSelect
            id="manual-filter-type"
            label="Тип"
            name="operationType"
            onChange={(operationType) => setDraft({ ...draft, operationType })}
            options={operationTypes}
            value={draft.operationType}
          />
          <FilterSelect
            id="manual-filter-account"
            label="Счёт"
            name="accountId"
            onChange={(accountId) => setDraft({ ...draft, accountId })}
            options={options.accounts.map((account) => ({
              value: account.id,
              label: `${account.name} · ${account.currency}`,
            }))}
            value={draft.accountId}
          />
          <FilterSelect
            id="manual-filter-category"
            label="Категория"
            name="categoryId"
            onChange={(categoryId) => setDraft({ ...draft, categoryId })}
            options={options.categories.map(referenceOption)}
            value={draft.categoryId}
          />
          <FilterSelect
            id="manual-filter-property"
            label="Объект"
            name="propertyId"
            onChange={(propertyId) => setDraft({ ...draft, propertyId })}
            options={options.properties.map(referenceOption)}
            value={draft.propertyId}
          />
        </div>
      </details>

      <FormActions>
        <Button isLoading={navigationPending} tone="primary" type="submit">
          Применить
        </Button>
        <Link
          className={styles.resetLink}
          onClick={onClose}
          to={location.pathname}
        >
          Сбросить
        </Link>
      </FormActions>
    </form>
  );
}

type FilterSelectProps = {
  id: string;
  label: string;
  name: string;
  onChange: (value: string) => void;
  options: { label: string; value: string }[];
  value: string;
};

function FilterSelect({
  id,
  label,
  name,
  onChange,
  options,
  value,
}: FilterSelectProps) {
  return (
    <Field htmlFor={id} label={label}>
      <select
        id={id}
        name={name}
        onChange={(event) => onChange(event.currentTarget.value)}
        value={value}
      >
        <option value="">Все</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

export function manualLedgerFilterDraft(
  currentSearch: string,
  options: FilterOptions,
): ManualLedgerFilterDraft {
  const search = new URLSearchParams(currentSearch);
  return {
    accountId: validOption(search.get("account_id"), options.accounts),
    categoryId: validOption(search.get("category_id"), options.categories),
    dateFrom: validDate(search.get("date_from")),
    dateTo: validDate(search.get("date_to")),
    operationType: validOption(search.get("type"), operationTypes),
    propertyId: validOption(search.get("property_id"), options.properties),
    search: search.get("search") ?? "",
    status: validOption(search.get("status"), statuses),
  };
}

export function manualLedgerFilterSearch(
  draft: ManualLedgerFilterDraft,
  perPage: number,
): string {
  const search = new URLSearchParams();
  append(search, "date_from", draft.dateFrom);
  append(search, "date_to", draft.dateTo);
  append(search, "type", draft.operationType);
  append(search, "status", draft.status);
  append(search, "account_id", draft.accountId);
  append(search, "category_id", draft.categoryId);
  append(search, "property_id", draft.propertyId);
  append(search, "search", draft.search.trim().replace(/\s+/g, " "));
  search.set("page", "1");
  search.set("per_page", String(perPage));
  return `?${search.toString()}`;
}

export function manualLedgerFiltersAreActive(currentSearch: string): boolean {
  const search = new URLSearchParams(currentSearch);
  return filterNames.some((name) => {
    const value = search.get(name);
    if (name === "date_from" || name === "date_to") {
      return Boolean(validDate(value));
    }
    if (name === "type") {
      return Boolean(validOption(value, operationTypes));
    }
    if (name === "status") {
      return Boolean(validOption(value, statuses));
    }
    if (name.endsWith("_id")) {
      return Boolean(value && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value));
    }
    return Boolean(value?.trim());
  });
}

export function manualLedgerAppliedFilters(
  currentSearch: string,
  options: FilterOptions,
): string[] {
  const draft = manualLedgerFilterDraft(currentSearch, options);
  const filters: string[] = [];
  addAppliedFilter(filters, "От", draft.dateFrom);
  addAppliedFilter(filters, "До", draft.dateTo);
  addAppliedFilter(filters, "Статус", optionLabel(draft.status, statuses));
  addAppliedFilter(
    filters,
    "Тип",
    optionLabel(draft.operationType, operationTypes),
  );
  addAppliedFilter(
    filters,
    "Счёт",
    optionLabel(draft.accountId, options.accounts),
  );
  addAppliedFilter(
    filters,
    "Категория",
    optionLabel(draft.categoryId, options.categories),
  );
  addAppliedFilter(
    filters,
    "Объект",
    optionLabel(draft.propertyId, options.properties),
  );
  return filters;
}

function classificationFiltersAreActive(draft: ManualLedgerFilterDraft) {
  return Boolean(
    draft.operationType ||
    draft.accountId ||
    draft.categoryId ||
    draft.propertyId,
  );
}

function addAppliedFilter(filters: string[], label: string, value: string) {
  if (value) {
    filters.push(`${label}: ${value}`);
  }
}

function optionLabel(
  value: string,
  options: readonly (
    { id: string; name: string } | { value: string; label: string }
  )[],
): string {
  if (!value) {
    return "";
  }
  const option = options.find((candidate) => optionValue(candidate) === value);
  if (!option) {
    return "";
  }
  return "name" in option ? option.name : option.label;
}

function append(search: URLSearchParams, name: string, value: string) {
  if (value) {
    search.set(name, value);
  }
}

function validDate(value: string | null): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return "";
  }
  return Number.isNaN(Date.parse(`${value}T00:00:00Z`)) ? "" : value;
}

function validOption(
  value: string | null,
  options: readonly ({ id: string } | { value: string } | number)[],
): string {
  if (!value) {
    return "";
  }
  return options.some((option) => optionValue(option) === value) ? value : "";
}

function optionValue(
  option: { id: string } | { value: string } | number,
): string {
  if (typeof option === "number") {
    return String(option);
  }
  return "id" in option ? option.id : option.value;
}

function referenceOption(reference: { id: string; name: string }) {
  return { value: reference.id, label: reference.name };
}
