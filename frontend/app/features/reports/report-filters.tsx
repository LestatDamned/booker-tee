import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import { Button, RouterButtonLink } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { FormActions } from "../../ui/field/form-layout";
import type { ReportOverviewDto } from "./api/reports-api";
import {
  reportFilterDraft,
  reportFilterSearch,
  type ReportFilterDraft,
} from "./report-filter-query";
import styles from "./reports-page.module.css";

export function ReportFilters({
  navigationPending,
  onClose,
  overview,
}: {
  navigationPending: boolean;
  onClose: () => void;
  overview: ReportOverviewDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(() => reportFilterDraft(overview));

  function change<Field extends keyof ReportFilterDraft>(
    field: Field,
    value: ReportFilterDraft[Field],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onClose();
    void navigate({
      pathname: location.pathname,
      search: reportFilterSearch(draft, location.search),
    });
  }

  return (
    <form className={styles.filterForm} onSubmit={apply}>
      <div className={styles.filterGrid}>
        <Field htmlFor="report-date-from" label="Период от">
          <input
            id="report-date-from"
            onChange={(event) => change("dateFrom", event.currentTarget.value)}
            type="date"
            value={draft.dateFrom}
          />
        </Field>
        <Field htmlFor="report-date-to" label="Период до">
          <input
            id="report-date-to"
            onChange={(event) => change("dateTo", event.currentTarget.value)}
            type="date"
            value={draft.dateTo}
          />
        </Field>
        <Field htmlFor="report-currency" label="Валюта отчёта">
          <select
            id="report-currency"
            onChange={(event) => change("currency", event.currentTarget.value)}
            value={draft.currency}
          >
            {overview.filterOptions.currencies.map((currency) => (
              <option key={currency} value={currency}>
                {currency}
              </option>
            ))}
          </select>
        </Field>
        <Field htmlFor="report-account" label="Счёт">
          <select
            id="report-account"
            onChange={(event) => change("accountId", event.currentTarget.value)}
            value={draft.accountId}
          >
            <option value="">Все счета</option>
            {overview.filterOptions.accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name} · {account.currency}
                {account.isActive ? "" : " · архив"}
              </option>
            ))}
          </select>
        </Field>
        <Field htmlFor="report-category" label="Категория">
          <select
            id="report-category"
            onChange={(event) =>
              change("categoryId", event.currentTarget.value)
            }
            value={draft.categoryId}
          >
            <option value="">Все категории</option>
            {overview.filterOptions.categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
                {category.isActive ? "" : " · архив"}
              </option>
            ))}
          </select>
        </Field>
        <Field htmlFor="report-property" label="Объект">
          <select
            id="report-property"
            onChange={(event) =>
              change("propertyId", event.currentTarget.value)
            }
            value={draft.propertyId}
          >
            <option value="">Все объекты</option>
            {overview.filterOptions.properties.map((property) => (
              <option key={property.id} value={property.id}>
                {property.name}
                {property.isActive ? "" : " · архив"}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <FormActions layout="split">
        <RouterButtonLink onClick={onClose} to={location.pathname}>
          Сбросить все
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
