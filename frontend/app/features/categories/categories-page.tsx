import {
  type FormEvent,
  type RefObject,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { Button, RouterButtonLink } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { ToastViewport, useToastQueue } from "../../ui/toast/toast";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type {
  CategoryDirectoryDto,
  CreateCategoryDraft,
} from "./api/categories-api";
import { createCategory } from "./api/categories-api";
import { CategoryCreatePanel } from "./category-create-panel";
import {
  categoryFieldErrors,
  firstInvalidCategoryField,
  type CategoryFieldErrors,
  validateCategoryDraft,
} from "./category-form";
import { CategoryMobileList, CategoryTable } from "./category-records";
import {
  categoryListQuery,
  categoryListUrl,
  categoryMatchesSearch,
  categoryMatchesView,
} from "./category-list-query";
import styles from "./categories-page.module.css";

export function CategoriesPage({
  directory,
  session,
}: {
  directory: CategoryDirectoryDto;
  session: SessionDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const nameRef = useRef<HTMLInputElement>(null);
  const kindRef = useRef<HTMLSelectElement>(null);
  const notesRef = useRef<HTMLTextAreaElement>(null);
  const createTriggerRef = useRef<HTMLButtonElement>(null);
  const pendingRef = useRef(false);
  const [categories, setCategories] = useState(directory.items);
  const [draft, setDraft] = useState<CreateCategoryDraft>(emptyCategoryDraft);
  const [fieldErrors, setFieldErrors] = useState<CategoryFieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [confirmCreateClose, setConfirmCreateClose] = useState(false);
  const { dismissToast, showToast, toast } = useToastQueue();
  const query = categoryListQuery(location.search);
  const kindLabels = useMemo(
    () =>
      new Map(
        directory.kindOptions.map((option) => [option.value, option.label]),
      ),
    [directory.kindOptions],
  );
  const viewCounts = {
    active: categories.filter(
      (category) => !category.isSystem && category.isActive,
    ).length,
    archived: categories.filter(
      (category) => !category.isSystem && !category.isActive,
    ).length,
    system: categories.filter((category) => category.isSystem).length,
  };
  const categoriesInView = categories.filter((category) =>
    categoryMatchesView(category, query.view),
  );
  const visibleCategories = categoriesInView.filter((category) =>
    categoryMatchesSearch(category, query.search, kindLabels),
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = new FormData(event.currentTarget).get("search");
    void navigate(
      categoryListUrl(query.view, typeof value === "string" ? value : ""),
    );
  }

  function changeDraft<FieldName extends keyof CreateCategoryDraft>(
    field: FieldName,
    value: CreateCategoryDraft[FieldName],
  ) {
    setDraft((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pendingRef.current) return;
    const nextErrors = validateCategoryDraft(draft);
    setFieldErrors(nextErrors);
    setSubmitError(null);
    const invalidField = firstInvalidCategoryField(nextErrors);
    if (invalidField) {
      focusCategoryField(invalidField, { kindRef, nameRef, notesRef });
      return;
    }

    pendingRef.current = true;
    setPending(true);
    const result = await createCategory({
      csrfToken: session.csrfToken,
      draft,
    });
    pendingRef.current = false;
    setPending(false);
    if (result.status === "success") {
      setCategories((current) => [
        result.category,
        ...current.filter((category) => category.id !== result.category.id),
      ]);
      setDraft(emptyCategoryDraft);
      setFieldErrors({});
      showToast({ message: `Категория «${result.category.name}» создана.` });
      setCreateOpen(false);
      void navigate({ pathname: location.pathname, search: "", hash: "" });
      window.setTimeout(() => createTriggerRef.current?.focus(), 0);
      return;
    }
    if (result.status === "unauthenticated") {
      window.location.assign("/login?next=/app/categories");
      return;
    }
    if (result.status === "forbidden") {
      setSubmitError(result.message);
      return;
    }
    const serverErrors = categoryFieldErrors(result.fieldErrors);
    setFieldErrors(serverErrors);
    setSubmitError(result.message);
    const serverInvalidField = firstInvalidCategoryField(serverErrors);
    if (serverInvalidField) {
      focusCategoryField(serverInvalidField, { kindRef, nameRef, notesRef });
    }
  }

  function requestCreateClose() {
    if (categoryDraftIsDirty(draft)) {
      setConfirmCreateClose(true);
      return;
    }
    discardCreateDraft();
  }

  function discardCreateDraft() {
    setDraft(emptyCategoryDraft);
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
              description="Причины поступлений и списаний для операций, автокатегоризации и финансовых отчётов."
              eyebrow={categoryCountLabel(visibleCategories.length)}
              title="Категории"
            />
          </WorkbenchHeader>

          <WorkbenchToolbar>
            <div className={styles.listTools}>
              <WorkbenchSearch
                ariaLabel="Поиск категорий"
                inputId="category-search"
                inputLabel="Поиск по названию, типу или заметке"
                inputProps={{ defaultValue: query.search }}
                key={query.search}
                onSubmit={submitSearch}
                placeholder="Название, тип или заметка"
              />
              <SelectionTabs
                as="nav"
                aria-label="Состояние категорий"
                className={styles.categoryTabs}
              >
                <SelectionTabLink
                  count={viewCounts.active}
                  selected={query.view === "active"}
                  to={categoryListUrl("active", query.search)}
                >
                  Активные
                </SelectionTabLink>
                <SelectionTabLink
                  count={viewCounts.archived}
                  selected={query.view === "archived"}
                  to={categoryListUrl("archived", query.search)}
                >
                  Архив
                </SelectionTabLink>
                <SelectionTabLink
                  count={viewCounts.system}
                  selected={query.view === "system"}
                  to={categoryListUrl("system", query.search)}
                >
                  Системные
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
                  Новая категория
                </Button>
              ) : null}
            </div>
          </WorkbenchToolbar>

          {!directory.capabilities.canCreate ? (
            <InlineNotice
              className={styles.readonlyNotice}
              title="Категории доступны только для просмотра"
              tone="information"
            >
              Создавать и изменять категории может владелец, администратор или
              редактор.
            </InlineNotice>
          ) : null}

          <WorkbenchContent
            aria-label="Список категорий"
            isEmpty={visibleCategories.length === 0}
          >
            {visibleCategories.length > 0 ? (
              <ResponsiveRecordCollection
                mobileList={
                  <CategoryMobileList
                    categories={visibleCategories}
                    kindLabels={kindLabels}
                  />
                }
                table={
                  <CategoryTable
                    categories={visibleCategories}
                    kindLabels={kindLabels}
                  />
                }
              />
            ) : (
              <WorkbenchEmptyState
                action={
                  query.search ? (
                    <RouterButtonLink
                      to={categoryListUrl(query.view, "")}
                      tone="secondary"
                    >
                      Очистить поиск
                    </RouterButtonLink>
                  ) : undefined
                }
                icon="categories"
                kind="filtered"
                title={emptyTitle(query.search, query.view)}
              >
                {query.search
                  ? "Попробуйте другое название, тип или текст заметки."
                  : "В этом разделе пока нет категорий."}
              </WorkbenchEmptyState>
            )}
          </WorkbenchContent>
        </WorkbenchSurface>
      </PageFrame>

      <ToastViewport onDismiss={dismissToast} toast={toast} />

      {createOpen ? (
        <CategoryCreatePanel
          confirmClose={confirmCreateClose}
          draft={draft}
          fieldErrors={fieldErrors}
          kindOptions={directory.kindOptions}
          kindRef={kindRef}
          nameRef={nameRef}
          notesRef={notesRef}
          onCancelConfirm={() => setConfirmCreateClose(false)}
          onChange={changeDraft}
          onClose={requestCreateClose}
          onConfirmClose={discardCreateDraft}
          onSubmit={submitCreate}
          pending={pending}
          submitError={submitError}
        />
      ) : null}
    </AppShell>
  );
}

const emptyCategoryDraft: CreateCategoryDraft = {
  name: "",
  kind: "mixed",
  notes: "",
};

function categoryDraftIsDirty(draft: CreateCategoryDraft): boolean {
  return Boolean(draft.name || draft.notes || draft.kind !== "mixed");
}

function categoryFieldRefs({
  kindRef,
  nameRef,
  notesRef,
}: {
  kindRef: RefObject<HTMLSelectElement | null>;
  nameRef: RefObject<HTMLInputElement | null>;
  notesRef: RefObject<HTMLTextAreaElement | null>;
}): Record<keyof CreateCategoryDraft, RefObject<HTMLElement | null>> {
  return { kind: kindRef, name: nameRef, notes: notesRef };
}

function focusCategoryField(
  field: keyof CreateCategoryDraft,
  refs: Parameters<typeof categoryFieldRefs>[0],
) {
  window.setTimeout(() => categoryFieldRefs(refs)[field].current?.focus(), 0);
}

function categoryCountLabel(count: number) {
  return `${count} ${count === 1 ? "категория" : count >= 2 && count <= 4 ? "категории" : "категорий"}`;
}

function emptyTitle(search: string, view: "active" | "archived" | "system") {
  if (search) return "По этому запросу категорий нет";
  if (view === "archived") return "Архив пуст";
  if (view === "system") return "Системных категорий нет";
  return "Активных категорий нет";
}
