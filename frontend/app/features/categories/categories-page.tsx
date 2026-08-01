import { type FormEvent, useMemo } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { RouterButtonLink } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ResponsiveRecordCollection } from "../../ui/responsive-record-collection/responsive-record-collection";
import {
  SelectionTabLink,
  SelectionTabs,
} from "../../ui/selection-tabs/selection-tabs";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchSearch } from "../../ui/workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "../../ui/workbench-toolbar/workbench-toolbar";
import type { CategoryDirectoryDto } from "./api/categories-api";
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
  const query = categoryListQuery(location.search);
  const kindLabels = useMemo(
    () =>
      new Map(
        directory.kindOptions.map((option) => [option.value, option.label]),
      ),
    [directory.kindOptions],
  );
  const viewCounts = {
    active: directory.items.filter(
      (category) => !category.isSystem && category.isActive,
    ).length,
    archived: directory.items.filter(
      (category) => !category.isSystem && !category.isActive,
    ).length,
    system: directory.items.filter((category) => category.isSystem).length,
  };
  const categoriesInView = directory.items.filter((category) =>
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
    </AppShell>
  );
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
