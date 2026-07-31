import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ActionStack } from "./action-stack/action-stack";
import { AppliedFilterSummary } from "./applied-filter-summary/applied-filter-summary";
import { BackLink } from "./back-link/back-link";
import { Badge } from "./badge/badge";
import { Button, RouterButtonLink } from "./button/button";
import { IconButton } from "./button/icon-button";
import { DocumentWorkbenchHeader } from "./document-workbench-header/document-workbench-header";
import { ExpansionPanel } from "./expansion-panel/expansion-panel";
import { Field } from "./field/field";
import { Fieldset } from "./field/fieldset";
import { FormErrorSummary } from "./field/form-error-summary";
import { FormActions } from "./field/form-layout";
import { InlineNotice } from "./inline-notice/inline-notice";
import { MoneyValue } from "./money-value/money-value";
import { PageFrame } from "./page-frame/page-frame";
import { RequestState } from "./request-state/request-state";
import { ResponsiveRecordCollection } from "./responsive-record-collection/responsive-record-collection";
import { RouteLoadingPage } from "./route-state-page/route-loading-page";
import { RouteStatePage } from "./route-state-page/route-state-page";
import {
  SelectionTabButton,
  SelectionTabLink,
  SelectionTabs,
} from "./selection-tabs/selection-tabs";
import { StatusLabel } from "./status-label/status-label";
import { Tag } from "./tag/tag";
import { WorkbenchRow } from "./workbench-row/workbench-row";
import { WorkbenchEmptyState } from "./workbench-empty-state/workbench-empty-state";
import { WorkbenchPagination } from "./workbench-pagination/workbench-pagination";
import { WorkbenchContent } from "./workbench-content/workbench-content";
import { WorkbenchFilterRegion } from "./workbench-content/workbench-filter-region";
import { WorkbenchStatus } from "./workbench-content/workbench-status";
import { WorkbenchHeader } from "./workbench-surface/workbench-header";
import { WorkbenchSurface } from "./workbench-surface/workbench-surface";
import { WorkbenchSearch } from "./workbench-toolbar/workbench-search";
import { WorkbenchToolbar } from "./workbench-toolbar/workbench-toolbar";

describe("foundation controls", () => {
  it("keeps semantic desktop and mobile record representations together", () => {
    render(
      <ResponsiveRecordCollection
        mobileList={
          <ol aria-label="Счета">
            <li>Основной счёт</li>
          </ol>
        }
        table={
          <table>
            <caption>Счета</caption>
            <tbody>
              <tr>
                <td>Основной счёт</td>
              </tr>
            </tbody>
          </table>
        }
      />,
    );

    expect(screen.getByRole("table", { name: "Счета" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Счета" })).toBeInTheDocument();
  });

  it("presents applied filters and one bordered reset action", () => {
    render(
      <MemoryRouter>
        <AppliedFilterSummary
          filters={["Тип: расход", "Счёт: Основной"]}
          resetTo="/operations"
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("list", { name: "Применённые фильтры" }),
    ).toHaveTextContent("Тип: расход");
    const reset = screen.getByRole("link", { name: "Сбросить все" });
    expect(reset).toHaveAttribute("href", "/operations");
    expect(reset).toHaveAttribute("data-tone", "secondary");
  });

  it("announces a full-page route loading state without an action", () => {
    render(
      <RouteLoadingPage eyebrow="Booker Tee" title="Загружаем workspace…" />,
    );

    const page = screen.getByRole("main");
    expect(page).toHaveAttribute("aria-busy", "true");
    expect(page).toHaveAccessibleName("Загружаем workspace…");
    expect(page.querySelector("a, button")).not.toBeInTheDocument();
  });

  it("distinguishes route failures from static access states", () => {
    const { rerender } = render(
      <RouteStatePage
        actionHref="/app/imports"
        actionLabel="К импортам"
        eyebrow="Документ импорта"
        kind="notFound"
        title="Документ не найден"
      >
        Документ удалён или относится к другому workspace.
      </RouteStatePage>,
    );

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("data-kind", "notFound");
    expect(screen.getByRole("link", { name: "К импортам" })).toHaveAttribute(
      "data-tone",
      "primary",
    );

    rerender(
      <RouteStatePage
        actionHref="/app/imports"
        actionLabel="Повторить"
        eyebrow="Ошибка загрузки"
        kind="error"
        title="Не удалось загрузить документы"
      >
        Backend недоступен.
      </RouteStatePage>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Backend недоступен.");
    expect(
      screen.getByRole("link", { name: "Повторить" }).querySelector("svg"),
    ).toHaveAttribute("aria-hidden", "true");
  });

  it("pairs inline notice tones with icons, semantics and recovery actions", () => {
    render(
      <InlineNotice
        action={<Button icon="retry">Повторить</Button>}
        role="alert"
        title="Не удалось сохранить"
        tone="danger"
      >
        Проверьте соединение и повторите попытку.
      </InlineNotice>,
    );

    const notice = screen.getByRole("alert");
    expect(notice).toHaveAttribute("data-tone", "danger");
    expect(notice.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(
      screen.getByRole("button", { name: "Повторить" }),
    ).toBeInTheDocument();
  });

  it("renders a consistent labeled back route with a decorative icon", () => {
    render(
      <MemoryRouter>
        <BackLink to="/imports">Все импорты</BackLink>
      </MemoryRouter>,
    );

    const link = screen.getByRole("link", { name: "Все импорты" });
    expect(link).toHaveAttribute("href", "/imports");
    expect(link.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("keeps client-side route actions visually consistent with buttons", () => {
    render(
      <MemoryRouter>
        <RouterButtonLink to="/imports">Сбросить</RouterButtonLink>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Сбросить" })).toHaveAttribute(
      "data-tone",
      "secondary",
    );
  });

  it("shares selected visuals while preserving link and button semantics", () => {
    render(
      <MemoryRouter>
        <SelectionTabs as="nav" aria-label="Состояние счетов">
          <SelectionTabLink count={2} selected to="/accounts">
            Активные
          </SelectionTabLink>
          <SelectionTabLink
            count={1}
            selected={false}
            to="/accounts?view=archived"
          >
            Архив
          </SelectionTabLink>
        </SelectionTabs>
        <SelectionTabs aria-label="Фильтр строк" role="group">
          <SelectionTabButton count={3} selected>
            Требуют решения
          </SelectionTabButton>
        </SelectionTabs>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("navigation", { name: "Состояние счетов" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Активные 2" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      screen.getByRole("button", { name: "Требуют решения 3" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("shares pagination semantics, links and page-size behavior", () => {
    const onPageSizeChange = vi.fn();

    const { container } = render(
      <MemoryRouter>
        <WorkbenchPagination
          ariaLabel="Страницы операций"
          currentPage={2}
          getPageHref={(page) => `?page=${page}`}
          hasNext
          hasPrevious
          pageSize={{
            id: "test-page-size",
            onChange: onPageSizeChange,
            options: [25, 50],
            value: 25,
          }}
          summary="26–50 из 187"
          totalPages={8}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("navigation", { name: "Страницы операций" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Страница 2")).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Страница 3" })).toHaveAttribute(
      "href",
      "/?page=3",
    );
    expect(screen.getByRole("link", { name: "Страница 8" })).toBeVisible();
    expect(screen.queryByLabelText("Страница 4")).not.toBeInTheDocument();
    expect(container.querySelectorAll("li[aria-hidden='true']")).toHaveLength(
      1,
    );

    fireEvent.change(screen.getByLabelText("На странице"), {
      target: { value: "50" },
    });
    expect(onPageSizeChange).toHaveBeenCalledWith(50);
  });

  it("makes a loading button unavailable and announces its state", () => {
    render(<Button isLoading>Сохранить</Button>);

    const button = screen.getByRole("button", { name: "Сохранить" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-busy", "true");
  });

  it("keeps reversible cancellation visually quieter than deletion", () => {
    render(
      <>
        <Button tone="dangerSecondary">Отменить операцию</Button>
        <Button tone="danger">Удалить окончательно</Button>
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Отменить операцию" }),
    ).toHaveAttribute("data-tone", "dangerSecondary");
    expect(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    ).toHaveAttribute("data-tone", "danger");
  });

  it("requires an accessible label for an icon-only action", () => {
    render(<IconButton aria-label="Редактировать" icon="edit" />);

    expect(
      screen.getByRole("button", { name: "Редактировать" }),
    ).toBeInTheDocument();
  });

  it("connects a field label and validation error to its native control", () => {
    render(
      <Field
        error="Обязательное поле"
        errorId="description-error"
        htmlFor="description"
        label="Описание"
      >
        <input
          aria-describedby="description-error"
          aria-invalid="true"
          id="description"
        />
      </Field>,
    );

    expect(screen.getByLabelText("Описание")).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByText("Обязательное поле")).toHaveAttribute(
      "id",
      "description-error",
    );
  });

  it("groups a short choice set and links summary errors to fields", () => {
    render(
      <>
        <FormErrorSummary
          errors={[
            {
              fieldId: "operation-expense",
              label: "Тип операции",
              message: "Выберите тип.",
            },
          ]}
          message="Проверьте данные."
        />
        <Fieldset legend="Тип операции" required>
          <label htmlFor="operation-expense">
            <input id="operation-expense" name="type" type="radio" />
            Расход
          </label>
        </Fieldset>
      </>,
    );

    expect(
      screen.getByRole("group", { name: "Тип операции" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Тип операции: Выберите тип." }),
    ).toHaveAttribute("href", "#operation-expense");
  });

  it("exposes a shared split sticky footer for panel forms", () => {
    render(
      <FormActions layout="split" sticky>
        <Button tone="secondary">Отмена</Button>
        <Button tone="primary">Сохранить</Button>
      </FormActions>,
    );

    const actions = screen.getByRole("button", {
      name: "Отмена",
    }).parentElement;
    expect(actions).toHaveAttribute("data-layout", "split");
    expect(actions).toHaveAttribute("data-sticky", "true");
  });
});

describe("financial presentation primitives", () => {
  it("renders a server-formatted amount without recalculating it", () => {
    render(<MoneyValue amount="−4 890,50" currency="RUB" tone="expense" />);

    expect(screen.getByText("−4 890,50")).toBeInTheDocument();
    expect(screen.getByText("RUB")).toBeInTheDocument();
  });

  it("renders status text independently of its visual tone", () => {
    render(<StatusLabel tone="warning">требует проверки</StatusLabel>);
    expect(screen.getByText("требует проверки")).toBeInTheDocument();
  });

  it("exposes automation as a project-wide semantic status role", () => {
    render(<StatusLabel tone="automation">автоправило</StatusLabel>);
    expect(screen.getByText("автоправило")).toHaveAttribute(
      "data-tone",
      "automation",
    );
  });

  it("keeps category tags and numeric badges as separate semantics", () => {
    render(
      <>
        <Tag tone="category">Продукты</Tag>
        <span>
          Требуют решения <Badge>3</Badge>
        </span>
      </>,
    );

    expect(screen.getByText("Продукты")).toHaveAttribute(
      "data-tone",
      "category",
    );
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});

describe("request and workbench composition", () => {
  it("composes the shared page and workbench geometry without another main landmark", () => {
    render(
      <PageFrame aria-label="Счета">
        <WorkbenchSurface aria-busy="true">
          <WorkbenchHeader>Заголовок</WorkbenchHeader>
        </WorkbenchSurface>
      </PageFrame>,
    );

    const frame = screen.getByRole("region", { name: "Счета" });
    expect(frame).toHaveAttribute("data-spacing", "top");
    expect(frame.querySelector("main")).not.toBeInTheDocument();
    expect(screen.getByText("Заголовок").parentElement).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("renders a document identity header from presentation-only content", () => {
    render(
      <DocumentWorkbenchHeader
        context="Альфа-Банк · RUB"
        eyebrow="Настройка импорта"
        filename="statement.xlsx"
        status={<StatusLabel tone="warning">Требует действия</StatusLabel>}
        title="Основной счёт"
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Основной счёт" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Альфа-Банк · RUB")).toBeVisible();
    expect(screen.getByText("statement.xlsx")).toHaveAttribute(
      "title",
      "statement.xlsx",
    );
    expect(screen.getByText("Состояние документа")).toBeVisible();
    expect(screen.getByText("Требует действия")).toBeVisible();
  });

  it("supports a frame without adding outer spacing", () => {
    render(
      <PageFrame aria-label="Импорт" spacing="none">
        Содержимое
      </PageFrame>,
    );

    expect(screen.getByRole("region", { name: "Импорт" })).toHaveAttribute(
      "data-spacing",
      "none",
    );
  });

  it("keeps workbench search labelled and disables both controls together", () => {
    render(
      <WorkbenchToolbar>
        <WorkbenchSearch
          ariaLabel="Поиск операций"
          disabled
          inputId="operation-search"
          inputLabel="Поиск по описанию"
          onSubmit={() => undefined}
          placeholder="Поиск по описанию"
        />
      </WorkbenchToolbar>,
    );

    expect(
      screen.getByRole("region", { name: "Инструменты списка" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("search", { name: "Поиск операций" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Поиск по описанию")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Найти" })).toBeDisabled();
  });

  it("composes filters, live status, and an explicit empty content region", () => {
    render(
      <>
        <WorkbenchFilterRegion data-testid="filter-region">
          Фильтры
        </WorkbenchFilterRegion>
        <WorkbenchStatus>Обновляем операции…</WorkbenchStatus>
        <WorkbenchContent aria-label="Список операций" isEmpty>
          Операций пока нет
        </WorkbenchContent>
      </>,
    );

    expect(screen.getByTestId("filter-region")).toHaveTextContent("Фильтры");
    expect(screen.getByText("Обновляем операции…")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    expect(
      screen.getByRole("region", { name: "Список операций" }),
    ).toHaveAttribute("data-empty", "true");
  });

  it("presents an empty result with a helpful action and semantic icon", () => {
    render(
      <WorkbenchEmptyState
        action={<Button icon="filter">Сбросить фильтры</Button>}
        icon="search"
        kind="filtered"
        title="По этим фильтрам операций нет"
      >
        Измените условия поиска.
      </WorkbenchEmptyState>,
    );

    const state = screen.getByRole("status");
    expect(state).toHaveAttribute("data-kind", "filtered");
    expect(state).toHaveTextContent("Измените условия поиска.");
    expect(state.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(
      screen.getByRole("button", { name: "Сбросить фильтры" }),
    ).toBeInTheDocument();
  });

  it("announces a local loading state without exposing an action", () => {
    render(<RequestState message="Обновляем данные…" />);

    const state = screen.getByRole("status");
    expect(state).toHaveAttribute("aria-busy", "true");
    expect(state).toHaveTextContent("Обновляем данные…");
    expect(state.querySelector("[aria-hidden='true']")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("closes an expansion through its accessible icon action", () => {
    const close = vi.fn();
    render(
      <ExpansionPanel
        id="edit-panel"
        isOpen
        onClose={close}
        title="Редактирование"
      >
        Форма
      </ExpansionPanel>,
    );

    expect(
      screen.getByRole("region", { name: "Редактирование" }),
    ).toHaveAttribute("data-workbench-row-expansion");
    fireEvent.click(screen.getByRole("button", { name: "Закрыть панель" }));
    expect(close).toHaveBeenCalledOnce();
  });

  it("composes row content and grouped dangerous actions", () => {
    render(
      <WorkbenchRow
        aside={
          <ActionStack
            danger={<Button tone="danger">Отменить операцию</Button>}
            primary={<Button>Редактировать</Button>}
          />
        }
        date="2026-07-20"
        description="Аренда за июль"
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Аренда за июль" }),
    ).toBeInTheDocument();
    expect(screen.getByText("20.07.2026")).toHaveAttribute(
      "datetime",
      "2026-07-20",
    );
    fireEvent.click(screen.getByText("Ещё действия"));
    expect(screen.getByLabelText("Опасные действия")).toBeInTheDocument();
  });

  it("keeps one action menu open and provides explicit escape routes", async () => {
    render(
      <>
        <ActionStack overflow={<Button>Первое действие</Button>} />
        <ActionStack overflow={<Button>Второе действие</Button>} />
      </>,
    );

    const triggers = screen.getAllByRole("button", {
      name: "Ещё действия",
    });
    const firstTrigger = triggers[0];
    const secondTrigger = triggers[1];
    if (!firstTrigger || !secondTrigger) {
      throw new Error("action menu triggers are required");
    }

    fireEvent.click(firstTrigger);
    expect(screen.getByText("Первое действие")).toBeInTheDocument();

    fireEvent.click(secondTrigger);
    expect(screen.queryByText("Первое действие")).not.toBeInTheDocument();
    expect(screen.getByText("Второе действие")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByText("Второе действие")).not.toBeInTheDocument();
    await waitFor(() => expect(secondTrigger).toHaveFocus());
  });

  it("moves keyboard focus into a portaled action menu", async () => {
    render(<ActionStack overflow={<Button>Открыть форму</Button>} />);

    const trigger = screen.getByRole("button", { name: "Ещё действия" });
    fireEvent.click(trigger, { detail: 0 });

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Открыть форму" }),
      ).toHaveFocus(),
    );
  });

  it.each([
    ["recent", "Недавно"],
    ["target", "Текущая строка"],
    ["working", "В работе"],
  ] as const)(
    "keeps the %s row state without adding a layout marker",
    (state, label) => {
      render(<WorkbenchRow description="Операция" state={state} />);

      expect(screen.getByRole("article")).toHaveAttribute("data-state", state);
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    },
  );
});
