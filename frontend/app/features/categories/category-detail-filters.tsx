import { useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import { Button, RouterButtonLink } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { FormActions } from "../../ui/field/form-layout";
import { WorkbenchFilterRegion } from "../../ui/workbench-content/workbench-filter-region";
import type { CategoryDetailDto } from "./api/category-detail-api";
import { categoryDetailResetTarget, queryUrl } from "./category-detail-query";
import styles from "./category-detail-page.module.css";

export function CategoryDetailFilters({
  detail,
  onClose,
  reportsReturnPath,
}: {
  detail: CategoryDetailDto;
  onClose: () => void;
  reportsReturnPath: string | null;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(() => ({
    currency: detail.appliedFilters.currency,
    dateFrom: detail.appliedFilters.dateFrom ?? "",
    dateTo: detail.appliedFilters.dateTo ?? "",
    operationType: detail.appliedFilters.operationType ?? "",
  }));

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const search = new URLSearchParams();
    setOrDelete(search, "date_from", draft.dateFrom);
    setOrDelete(search, "date_to", draft.dateTo);
    setOrDelete(search, "currency", draft.currency);
    setOrDelete(search, "type", draft.operationType);
    setOrDelete(
      search,
      "search",
      new URLSearchParams(location.search).get("search") ?? "",
    );
    setOrDelete(
      search,
      "operations_page_size",
      new URLSearchParams(location.search).get("operations_page_size") ?? "",
    );
    setOrDelete(search, "return_to", reportsReturnPath ?? "");
    onClose();
    void navigate(queryUrl(location.pathname, search));
  }

  return (
    <WorkbenchFilterRegion id="category-detail-filter-region">
      <form className={styles.filterForm} onSubmit={apply}>
        <div className={styles.filterGrid}>
          <Field htmlFor="category-date-from" label="Дата от">
            <input
              id="category-date-from"
              onChange={(event) =>
                setDraft({ ...draft, dateFrom: event.currentTarget.value })
              }
              type="date"
              value={draft.dateFrom}
            />
          </Field>
          <Field htmlFor="category-date-to" label="Дата до">
            <input
              id="category-date-to"
              onChange={(event) =>
                setDraft({ ...draft, dateTo: event.currentTarget.value })
              }
              type="date"
              value={draft.dateTo}
            />
          </Field>
          <Field htmlFor="category-currency" label="Валюта">
            <select
              id="category-currency"
              onChange={(event) =>
                setDraft({ ...draft, currency: event.currentTarget.value })
              }
              value={draft.currency}
            >
              {detail.availableCurrencies.map((currency) => (
                <option key={currency} value={currency}>
                  {currency}
                </option>
              ))}
            </select>
          </Field>
          <Field htmlFor="category-operation-type" label="Тип операции">
            <select
              id="category-operation-type"
              onChange={(event) =>
                setDraft({
                  ...draft,
                  operationType: event.currentTarget.value,
                })
              }
              value={draft.operationType}
            >
              <option value="">Доходы и расходы</option>
              <option value="income">Доходы</option>
              <option value="expense">Расходы</option>
            </select>
          </Field>
        </div>
        <FormActions layout="split">
          <RouterButtonLink
            onClick={onClose}
            to={categoryDetailResetTarget(location.pathname, reportsReturnPath)}
          >
            Сбросить
          </RouterButtonLink>
          <Button icon="filterApply" tone="primary" type="submit">
            Применить
          </Button>
        </FormActions>
      </form>
    </WorkbenchFilterRegion>
  );
}

function setOrDelete(search: URLSearchParams, key: string, value: string) {
  if (value) search.set(key, value);
  else search.delete(key);
}
