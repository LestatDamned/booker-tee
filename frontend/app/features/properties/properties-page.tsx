import { useRef, useState, type FormEvent, type RefObject } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { Button, RouterButtonLink } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { ToastViewport, useToastQueue } from "../../ui/toast/toast";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type {
  CreatePropertyDraft,
  PropertyDirectoryDto,
} from "./api/properties-api";
import { createProperty } from "./api/properties-api";
import { PropertyCreatePanel } from "./property-create-panel";
import { PropertyEditPanel } from "./property-edit-panel";
import {
  firstInvalidPropertyField,
  propertyFieldErrors,
  type PropertyFieldErrors,
  validatePropertyDraft,
} from "./property-form";
import {
  propertyListQuery,
  propertyListUrl,
  propertyMatchesSearch,
} from "./property-list-query";
import { PropertyMobileList, PropertyTable } from "./property-records";
import styles from "./properties-page.module.css";
import { usePropertyCollection } from "./use-property-collection";
import { usePropertyEditor } from "./use-property-editor";
import { usePropertyLifecycle } from "./use-property-lifecycle";

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
  const [draft, setDraft] = useState<CreatePropertyDraft>(emptyPropertyDraft);
  const [fieldErrors, setFieldErrors] = useState<PropertyFieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [confirmCreateClose, setConfirmCreateClose] = useState(false);
  const { dismissToast, showToast, toast } = useToastQueue();
  const collection = usePropertyCollection(directory.items);
  const editor = usePropertyEditor({
    csrfToken: session.csrfToken,
    onCommitted: collection.replaceCommitted,
    onReloaded: collection.replaceAll,
    showToast,
  });
  const lifecycle = usePropertyLifecycle({
    csrfToken: session.csrfToken,
    onCommitted: collection.replaceCommitted,
    onReloaded: collection.replaceAll,
    showToast,
  });
  const { editState } = editor;
  const { properties } = collection;
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
    const invalidField = firstInvalidPropertyField(nextErrors);
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
      collection.commitCreated(result.property);
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
    const serverInvalidField = firstInvalidPropertyField(serverErrors);
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

  function renderEditor(propertyId: string, panelId: string) {
    if (!editState || editState.snapshot.id !== propertyId) return null;
    return (
      <PropertyEditPanel
        conflict={editState.conflict}
        draft={editState.draft}
        fieldErrors={editState.fieldErrors}
        onChange={editor.changeDraft}
        onClose={editor.requestClose}
        onReload={() => void editor.reloadSnapshot()}
        onSubmit={editor.submit}
        panelId={panelId}
        pending={editState.pending}
        propertyId={propertyId}
        submitError={editState.submitError}
      />
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

          {lifecycle.failure ? (
            <InlineNotice
              action={
                <Button
                  disabled={lifecycle.pendingId !== null}
                  icon="retry"
                  isLoading={lifecycle.pendingId !== null}
                  onClick={() =>
                    lifecycle.failure?.conflict
                      ? void lifecycle.refreshAndRetry()
                      : lifecycle.retry()
                  }
                  tone="secondary"
                >
                  {lifecycle.failure.conflict
                    ? "Обновить и повторить"
                    : "Повторить"}
                </Button>
              }
              className={styles.readonlyNotice}
              role="alert"
              title="Не удалось изменить состояние объекта"
              tone="danger"
            >
              {lifecycle.failure.message}
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
              mobileList={
                <PropertyMobileList
                  editingId={editState?.snapshot.id ?? null}
                  lifecyclePendingId={lifecycle.pendingId}
                  onArchive={lifecycle.requestArchive}
                  onEdit={editor.requestEdit}
                  onRestore={lifecycle.restore}
                  properties={visibleProperties}
                  renderEditor={(property, panelId) =>
                    renderEditor(property.id, panelId)
                  }
                />
              }
              table={
                <PropertyTable
                  editingId={editState?.snapshot.id ?? null}
                  lifecyclePendingId={lifecycle.pendingId}
                  onArchive={lifecycle.requestArchive}
                  onEdit={editor.requestEdit}
                  onRestore={lifecycle.restore}
                  properties={visibleProperties}
                  renderEditor={(property, panelId) =>
                    renderEditor(property.id, panelId)
                  }
                />
              }
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

      {editor.confirmation ? (
        <ConfirmationDialog
          cancelLabel="Продолжить редактирование"
          confirmLabel="Отменить изменения"
          description="Несохранённые изменения объекта будут потеряны."
          onCancel={editor.cancelDiscard}
          onConfirm={editor.confirmDiscard}
          title={
            editor.confirmation === "switch"
              ? "Перейти к другому объекту?"
              : "Закрыть редактирование?"
          }
        />
      ) : null}

      {lifecycle.archiveCandidate ? (
        <ConfirmationDialog
          confirmLabel="Перенести в архив"
          description={`История, связанные операции и отчёты объекта «${lifecycle.archiveCandidate.name}» сохранятся. Объект исчезнет из выбора для новых операций, но действующие правила останутся включены и могут продолжить предлагать его.`}
          onCancel={lifecycle.cancelArchive}
          onConfirm={lifecycle.confirmArchive}
          pending={lifecycle.pendingId === lifecycle.archiveCandidate.id}
          title="Перенести объект в архив?"
        />
      ) : null}
    </AppShell>
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
