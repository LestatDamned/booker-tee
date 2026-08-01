import { useRef, useState, type FormEvent, type RefObject } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { ActionStack } from "../../ui/action-stack/action-stack";
import { Button, RouterButtonLink } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { StatusLabel } from "../../ui/status-label/status-label";
import { ToastViewport, useToastQueue } from "../../ui/toast/toast";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type {
  CreatePropertyDraft,
  PropertyDirectoryDto,
  PropertySummaryDto,
} from "./api/properties-api";
import { createProperty } from "./api/properties-api";
import { PropertyCreatePanel } from "./property-create-panel";
import {
  type PropertyFieldErrors,
  validatePropertyDraft,
} from "./property-form";
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
  const nameRef = useRef<HTMLInputElement>(null);
  const shortNameRef = useRef<HTMLInputElement>(null);
  const addressRef = useRef<HTMLTextAreaElement>(null);
  const createTriggerRef = useRef<HTMLButtonElement>(null);
  const pendingRef = useRef(false);
  const [properties, setProperties] = useState(directory.items);
  const [draft, setDraft] = useState<CreatePropertyDraft>(emptyPropertyDraft);
  const [fieldErrors, setFieldErrors] = useState<PropertyFieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [confirmCreateClose, setConfirmCreateClose] = useState(false);
  const { dismissToast, showToast, toast } = useToastQueue();
  const query = propertyListQuery(location.search);
  const activeCount = properties.filter(
    (property) => property.status === "active",
  ).length;
  const archivedCount = properties.length - activeCount;
  const visibleProperties = properties.filter(
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

  function changeDraft<FieldName extends keyof CreatePropertyDraft>(
    field: FieldName,
    value: CreatePropertyDraft[FieldName],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current) return;
    const nextErrors = validatePropertyDraft(draft);
    setFieldErrors(nextErrors);
    setSubmitError(null);
    const invalidField = firstInvalidField(nextErrors);
    if (invalidField) {
      focusPropertyField(invalidField, {
        addressRef,
        nameRef,
        shortNameRef,
      });
      return;
    }

    pendingRef.current = true;
    setPending(true);
    const result = await createProperty({
      csrfToken: session.csrfToken,
      draft,
    });
    pendingRef.current = false;
    setPending(false);
    if (result.status === "success") {
      setProperties((current) =>
        insertCommittedProperty(current, result.property),
      );
      setDraft(emptyPropertyDraft);
      setFieldErrors({});
      showToast({ message: `Объект «${result.property.name}» создан.` });
      setCreateOpen(false);
      void navigate({ pathname: location.pathname, search: "", hash: "" });
      window.setTimeout(() => createTriggerRef.current?.focus(), 0);
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/properties");
      return;
    }
    if (result.status === "forbidden") {
      setSubmitError(result.message);
      return;
    }
    const serverErrors = propertyFieldErrors(result.fieldErrors);
    setFieldErrors(serverErrors);
    setSubmitError(result.message);
    const serverInvalidField = firstInvalidField(serverErrors);
    if (serverInvalidField) {
      focusPropertyField(serverInvalidField, {
        addressRef,
        nameRef,
        shortNameRef,
      });
    }
  }

  function requestCreateClose() {
    if (propertyDraftIsDirty(draft)) {
      setConfirmCreateClose(true);
      return;
    }
    discardCreateDraft();
  }

  function discardCreateDraft() {
    setDraft(emptyPropertyDraft);
    setFieldErrors({});
    setSubmitError(null);
    setConfirmCreateClose(false);
    setCreateOpen(false);
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
              {directory.capabilities.canCreate ? (
                <Button
                  ref={createTriggerRef}
                  aria-haspopup="dialog"
                  icon="plus"
                  onClick={() => setCreateOpen(true)}
                  tone="primary"
                >
                  Новый объект
                </Button>
              ) : null}
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

          {properties.length === 0 ? (
            <WorkbenchEmptyState
              action={
                directory.capabilities.canCreate ? (
                  <Button
                    icon="plus"
                    onClick={() => setCreateOpen(true)}
                    tone="primary"
                  >
                    Добавить первый объект
                  </Button>
                ) : undefined
              }
              icon="properties"
              title="Пока нет объектов"
            >
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

      <ToastViewport onDismiss={dismissToast} toast={toast} />

      {createOpen ? (
        <PropertyCreatePanel
          addressRef={addressRef}
          confirmClose={confirmCreateClose}
          draft={draft}
          fieldErrors={fieldErrors}
          nameRef={nameRef}
          onCancelConfirm={() => setConfirmCreateClose(false)}
          onChange={changeDraft}
          onClose={requestCreateClose}
          onConfirmClose={discardCreateDraft}
          onSubmit={submitCreate}
          pending={pending}
          shortNameRef={shortNameRef}
          submitError={submitError}
        />
      ) : null}
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

const emptyPropertyDraft: CreatePropertyDraft = {
  name: "",
  shortName: "",
  address: "",
};

function propertyDraftIsDirty(draft: CreatePropertyDraft): boolean {
  return Boolean(draft.name || draft.shortName || draft.address);
}

function propertyFieldErrors(
  fieldErrors: Record<string, string[]>,
): PropertyFieldErrors {
  const errors: PropertyFieldErrors = {};
  for (const field of ["name", "shortName", "address"] as const) {
    const message = fieldErrors[field]?.[0];
    if (message) errors[field] = message;
  }
  return errors;
}

function firstInvalidField(
  errors: PropertyFieldErrors,
): keyof CreatePropertyDraft | null {
  for (const field of ["name", "shortName", "address"] as const) {
    if (errors[field]) return field;
  }
  return null;
}

function propertyFieldRefs({
  addressRef,
  nameRef,
  shortNameRef,
}: {
  addressRef: RefObject<HTMLTextAreaElement | null>;
  nameRef: RefObject<HTMLInputElement | null>;
  shortNameRef: RefObject<HTMLInputElement | null>;
}): Record<keyof CreatePropertyDraft, RefObject<HTMLElement | null>> {
  return { address: addressRef, name: nameRef, shortName: shortNameRef };
}

function focusPropertyField(
  field: keyof CreatePropertyDraft,
  refs: Parameters<typeof propertyFieldRefs>[0],
) {
  window.setTimeout(() => propertyFieldRefs(refs)[field].current?.focus(), 0);
}

function insertCommittedProperty(
  properties: PropertySummaryDto[],
  property: PropertySummaryDto,
): PropertySummaryDto[] {
  const withoutCommitted = properties.filter((item) => item.id !== property.id);
  const firstArchived = withoutCommitted.findIndex(
    (item) => item.status === "archived",
  );
  if (firstArchived === -1) return [...withoutCommitted, property];
  return [
    ...withoutCommitted.slice(0, firstArchived),
    property,
    ...withoutCommitted.slice(firstArchived),
  ];
}
