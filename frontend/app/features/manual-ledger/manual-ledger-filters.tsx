import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import type { ManualLedgerDto } from "./manual-ledger-api";
import styles from "./manual-ledger.module.css";

type FilterOptions = ManualLedgerDto["filterOptions"];

export type ManualLedgerFilterDraft = {
  accountId: string;
  categoryId: string;
  dateFrom: string;
  dateTo: string;
  operationType: string;
  perPage: string;
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
  options: FilterOptions;
  paginationPerPage: number;
};

export function ManualLedgerFilters({
  options,
  paginationPerPage,
}: ManualLedgerFiltersProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const active = manualLedgerFiltersAreActive(location.search);
  const [isOpen, setIsOpen] = useState(active);
  const [draft, setDraft] = useState(() =>
    manualLedgerFilterDraft(location.search, options, paginationPerPage),
  );

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void navigate({
      pathname: location.pathname,
      search: manualLedgerFilterSearch(draft),
    });
  }

  return (
    <section className={styles.filters}>
      <div className={styles.filterHeader}>
        <div>
          <h2>Фильтры</h2>
          <p>
            {active
              ? "Фильтры применены к списку."
              : "Показываем все операции."}
          </p>
        </div>
        <Button
          aria-controls="manual-ledger-filter-panel"
          aria-expanded={isOpen}
          onClick={() => setIsOpen((current) => !current)}
        >
          {isOpen ? "Скрыть" : "Показать"}
        </Button>
      </div>

      {isOpen ? (
        <form id="manual-ledger-filter-panel" onSubmit={applyFilters}>
          <div className={styles.filterGrid}>
            <Field htmlFor="manual-filter-search" label="Описание">
              <input
                id="manual-filter-search"
                onChange={(event) =>
                  setDraft({ ...draft, search: event.currentTarget.value })
                }
                type="search"
                value={draft.search}
              />
            </Field>
            <Field htmlFor="manual-filter-date-from" label="Дата от">
              <input
                id="manual-filter-date-from"
                onChange={(event) =>
                  setDraft({ ...draft, dateFrom: event.currentTarget.value })
                }
                type="date"
                value={draft.dateFrom}
              />
            </Field>
            <Field htmlFor="manual-filter-date-to" label="Дата до">
              <input
                id="manual-filter-date-to"
                onChange={(event) =>
                  setDraft({ ...draft, dateTo: event.currentTarget.value })
                }
                type="date"
                value={draft.dateTo}
              />
            </Field>
            <FilterSelect
              id="manual-filter-type"
              label="Тип"
              onChange={(operationType) =>
                setDraft({ ...draft, operationType })
              }
              options={operationTypes}
              value={draft.operationType}
            />
            <FilterSelect
              id="manual-filter-status"
              label="Статус"
              onChange={(status) => setDraft({ ...draft, status })}
              options={statuses}
              value={draft.status}
            />
            <FilterSelect
              id="manual-filter-account"
              label="Счёт"
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
              onChange={(categoryId) => setDraft({ ...draft, categoryId })}
              options={options.categories.map(referenceOption)}
              value={draft.categoryId}
            />
            <FilterSelect
              id="manual-filter-property"
              label="Объект"
              onChange={(propertyId) => setDraft({ ...draft, propertyId })}
              options={options.properties.map(referenceOption)}
              value={draft.propertyId}
            />
            <FilterSelect
              id="manual-filter-per-page"
              label="На странице"
              onChange={(perPage) => setDraft({ ...draft, perPage })}
              options={options.perPage.map((value) => ({
                value: String(value),
                label: String(value),
              }))}
              value={draft.perPage}
            />
          </div>
          <div className={styles.filterActions}>
            <Button tone="primary" type="submit">
              Применить
            </Button>
            <Link className={styles.resetLink} to="/ledger/manual">
              Сбросить
            </Link>
          </div>
        </form>
      ) : null}
    </section>
  );
}

type FilterSelectProps = {
  id: string;
  label: string;
  onChange: (value: string) => void;
  options: { label: string; value: string }[];
  value: string;
};

function FilterSelect({
  id,
  label,
  onChange,
  options,
  value,
}: FilterSelectProps) {
  return (
    <Field htmlFor={id} label={label}>
      <select
        id={id}
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
  paginationPerPage: number,
): ManualLedgerFilterDraft {
  const search = new URLSearchParams(currentSearch);
  return {
    accountId: validOption(search.get("account_id"), options.accounts),
    categoryId: validOption(search.get("category_id"), options.categories),
    dateFrom: validDate(search.get("date_from")),
    dateTo: validDate(search.get("date_to")),
    operationType: validOption(search.get("type"), operationTypes),
    perPage:
      validOption(search.get("per_page"), options.perPage) ||
      String(paginationPerPage),
    propertyId: validOption(search.get("property_id"), options.properties),
    search: search.get("search") ?? "",
    status: validOption(search.get("status"), statuses),
  };
}

export function manualLedgerFilterSearch(
  draft: ManualLedgerFilterDraft,
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
  search.set("per_page", draft.perPage);
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
