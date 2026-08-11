import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import { Button, RouterButtonLink } from "../../../ui/button/button";
import { Field } from "../../../ui/field/field";
import { FormActions } from "../../../ui/field/form-layout";
import type { components } from "../../../api/generated/schema";
import styles from "../manual-ledger.module.css";
import {
  manualLedgerClassificationFiltersAreActive,
  manualLedgerFilterDraft,
  manualLedgerFilterSearch,
  manualOperationStatusFilters,
  manualOperationTypeFilters,
  operationSourceFilters,
} from "./manual-ledger-filter-query";

type OperationsFilterOptions =
  components["schemas"]["OperationsFilterOptionsApiResponse"];
type FilterOptions = Omit<OperationsFilterOptions, "sources"> & {
  sources?: OperationsFilterOptions["sources"];
};

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
    manualLedgerClassificationFiltersAreActive(draft),
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
            emptyLabel="Подтверждённые"
            label="Статус"
            name="status"
            onChange={(status) => setDraft({ ...draft, status })}
            options={manualOperationStatusFilters}
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
            options={manualOperationTypeFilters}
            value={draft.operationType}
          />
          {options.sources ? (
            <FilterSelect
              id="manual-filter-source"
              label="Источник"
              name="source"
              onChange={(source) => setDraft({ ...draft, source })}
              options={operationSourceFilters.filter((option) =>
                options.sources?.includes(option.value),
              )}
              value={draft.source}
            />
          ) : null}
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

      <FormActions layout="split">
        <RouterButtonLink onClick={onClose} to={location.pathname}>
          Сбросить
        </RouterButtonLink>
        <Button
          icon="filterApply"
          isLoading={navigationPending}
          tone="primary"
          type="submit"
        >
          Применить
        </Button>
      </FormActions>
    </form>
  );
}

type FilterSelectProps = {
  emptyLabel?: string;
  id: string;
  label: string;
  name: string;
  onChange: (value: string) => void;
  options: { label: string; value: string }[];
  value: string;
};

function FilterSelect({
  emptyLabel = "Все",
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
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

function referenceOption(reference: { id: string; name: string }) {
  return { value: reference.id, label: reference.name };
}
