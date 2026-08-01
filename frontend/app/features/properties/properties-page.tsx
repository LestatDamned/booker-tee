import type { FormEvent } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { ActionStack } from "../../ui/action-stack/action-stack";
import { RouterButtonLink } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { StatusLabel } from "../../ui/status-label/status-label";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type {
  PropertyDirectoryDto,
  PropertySummaryDto,
} from "./api/properties-api";
import {
  propertyListQuery,
  propertyListUrl,
  propertyMatchesSearch,
} from "./property-list-query";
import styles from "./properties-page.module.css";

export function PropertiesPage({
  directory,
  session,
}: {
  directory: PropertyDirectoryDto;
  session: SessionDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const query = propertyListQuery(location.search);
  const activeCount = directory.items.filter(
    (property) => property.status === "active",
  ).length;
  const archivedCount = directory.items.length - activeCount;
  const visibleProperties = directory.items.filter(
    (property) =>
      property.status === query.view &&
      propertyMatchesSearch(property, query.search),
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("search");
    void navigate(
      propertyListUrl(query.view, typeof value === "string" ? value : ""),
    );
  }

  return (
    <AppShell session={session}>
      <PageFrame>
        <WorkbenchSurface className={styles.workbench}>
          <WorkbenchHeader>
            <PageHeader
              actions={
                <RouterButtonLink icon="reports" to="/reports">
                  Отчёты
                </RouterButtonLink>
              }
              description="Аналитические привязки для раздельного учёта квартир, аренды, проектов и других целей."
              eyebrow={propertyCountLabel(visibleProperties.length)}
              title="Объекты"
            />
          </WorkbenchHeader>

          <WorkbenchToolbar>
            <div className={styles.listTools}>
              <WorkbenchSearch
                ariaLabel="Поиск объектов"
                className={styles.searchPlacement}
                inputId="property-search"
                inputLabel="Поиск по названию, короткому названию или адресу"
                inputProps={{ defaultValue: query.search }}
                key={query.search}
                onSubmit={submitSearch}
                placeholder="Название, короткое имя или адрес"
              />
              <SelectionTabs
                as="nav"
                aria-label="Состояние объектов"
                className={styles.propertyTabs}
              >
                <SelectionTabLink
                  count={activeCount}
                  selected={query.view === "active"}
                  to={propertyListUrl("active", query.search)}
                >
                  Активные
                </SelectionTabLink>
                <SelectionTabLink
                  count={archivedCount}
                  selected={query.view === "archived"}
                  to={propertyListUrl("archived", query.search)}
                >
                  Архив
                </SelectionTabLink>
              </SelectionTabs>
            </div>
          </WorkbenchToolbar>

          {!directory.capabilities.canCreate ? (
            <InlineNotice
              className={styles.readonlyNotice}
              title="Объекты доступны только для просмотра"
              tone="information"
            >
              Создавать и изменять объекты может владелец, администратор или
              редактор.
            </InlineNotice>
          ) : null}

          {directory.items.length === 0 ? (
            <WorkbenchEmptyState icon="properties" title="Пока нет объектов">
              Объекты помогают отделять операции квартиры, аренды, проекта или
              другой финансовой цели.
            </WorkbenchEmptyState>
          ) : visibleProperties.length > 0 ? (
            <ResponsiveRecordCollection
              mobileList={<PropertyMobileList properties={visibleProperties} />}
              table={<PropertyTable properties={visibleProperties} />}
            />
          ) : (
            <WorkbenchEmptyState
              action={
                query.search ? (
                  <RouterButtonLink
                    icon="search"
                    to={propertyListUrl(query.view, "")}
                  >
                    Очистить поиск
                  </RouterButtonLink>
                ) : undefined
              }
              icon="search"
              kind="filtered"
              title={
                query.search
                  ? "По этому запросу объектов нет"
                  : query.view === "archived"
                    ? "Архив пока пуст"
                    : "Активных объектов нет"
              }
            >
              {query.search
                ? "Измените запрос или очистите поиск."
                : "Объекты появятся здесь после изменения их состояния."}
            </WorkbenchEmptyState>
          )}
        </WorkbenchSurface>
      </PageFrame>
    </AppShell>
  );
}

function PropertyTable({ properties }: { properties: PropertySummaryDto[] }) {
  return (
    <table className={styles.table}>
      <caption className="visually-hidden">Объекты текущего workspace</caption>
      <thead>
        <tr>
          <th scope="col">Объект</th>
          <th scope="col">Адрес</th>
          <th scope="col">Состояние</th>
          <th scope="col">
            <span className="visually-hidden">Действие</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {properties.map((property) => (
          <tr data-property-record key={property.id}>
            <th scope="row">
              <strong data-record-identity>{property.name}</strong>
              {property.shortName ? (
                <span className={styles.shortName}>{property.shortName}</span>
              ) : null}
            </th>
            <td className={styles.addressCell}>
              {property.address ?? <span aria-label="Адрес не указан">—</span>}
            </td>
            <td>
              <PropertyStatus property={property} />
            </td>
            <td className={styles.actionCell}>
              <PropertyActions property={property} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function PropertyMobileList({
  properties,
}: {
  properties: PropertySummaryDto[];
}) {
  return (
    <ol aria-label="Объекты текущего workspace">
      {properties.map((property) => (
        <li key={property.id}>
          <article data-property-record data-responsive-record>
            <div className={styles.mobileHeading}>
              <div>
                <strong data-record-identity>{property.name}</strong>
                {property.shortName ? (
                  <span className={styles.shortName}>
                    Коротко: {property.shortName}
                  </span>
                ) : null}
              </div>
              <PropertyStatus property={property} />
            </div>
            <p className={styles.mobileAddress}>
              {property.address ?? "Адрес не указан"}
            </p>
            <div className={styles.mobileFooter}>
              <PropertyActions property={property} />
            </div>
          </article>
        </li>
      ))}
    </ol>
  );
}

function PropertyStatus({ property }: { property: PropertySummaryDto }) {
  return property.status === "active" ? (
    <StatusLabel tone="success">Активен</StatusLabel>
  ) : (
    <StatusLabel tone="neutral">Архив</StatusLabel>
  );
}

function PropertyActions({ property }: { property: PropertySummaryDto }) {
  return (
    <ActionStack
      orientation="row"
      primary={
        <RouterButtonLink
          aria-label={`Открыть отчёт по объекту «${property.name}»`}
          icon="reports"
          to={`/reports?property_id=${property.id}`}
        >
          Отчёт
        </RouterButtonLink>
      }
    />
  );
}

function propertyCountLabel(count: number): string {
  return `${count} ${pluralize(count, "объект", "объекта", "объектов")}`;
}

function pluralize(
  count: number,
  one: string,
  few: string,
  many: string,
): string {
  const tens = count % 100;
  const units = count % 10;
  if (tens >= 11 && tens <= 14) return many;
  if (units === 1) return one;
  if (units >= 2 && units <= 4) return few;
  return many;
}
