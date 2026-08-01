import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CategoryDetailPage } from "./category-detail-page";
import { detail, session } from "./test-support";

describe("CategoryDetailPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders currency-safe summary, bounded operations and rules preview", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Продукты" })).toBeVisible();
    expect(screen.getByLabelText(/100.*000,00 RUB/)).toBeVisible();
    expect(screen.getAllByLabelText(/35.*000,00 RUB/)[0]).toBeVisible();
    expect(screen.getByLabelText(/65.*000,00 RUB/)).toBeVisible();
    expect(screen.getByText("Супермаркет")).toBeVisible();
    expect(screen.getByText("Не влияет на прибыль")).toBeVisible();
    expect(screen.getByText("1–20 из 22")).toBeVisible();
    expect(screen.getByRole("link", { name: "Страница 2" })).toHaveAttribute(
      "href",
      expect.stringContaining("operations_page=2"),
    );
    expect(
      screen.getByRole("heading", { name: "Связанные правила" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Супермаркеты" })).toHaveAttribute(
      "href",
      `/rules#rule-${detail.rules.items[0]!.id}`,
    );
  });

  it("treats the workspace currency default as context, not an active filter", () => {
    renderPage("/categories/id", {
      ...detail,
      appliedFilters: {
        ...detail.appliedFilters,
        dateFrom: null,
        dateTo: null,
      },
    });

    expect(screen.queryByText("Активные фильтры")).not.toBeInTheDocument();
  });

  it("preserves a safe Reports back path and rejects an external one", () => {
    const { unmount } = renderPage(
      "/categories/id?currency=RUB&return_to=%2Fapp%2Freports%3Fcurrency%3DRUB",
    );
    expect(
      screen.getByRole("link", { name: "Вернуться в отчёт" }),
    ).toHaveAttribute("href", "/app/reports?currency=RUB");
    expect(screen.getByText("Валюта: RUB")).toBeVisible();
    unmount();

    renderPage(
      "/categories/id?return_to=https%3A%2F%2Fevil.test%2Fapp%2Freports",
    );
    expect(screen.getByRole("link", { name: "Все категории" })).toHaveAttribute(
      "href",
      "/categories",
    );
  });

  it("applies detail filters and retains report context", async () => {
    const user = userEvent.setup();
    renderPage("/categories/id?return_to=%2Fapp%2Freports%3Fcurrency%3DRUB");

    await user.click(screen.getByRole("button", { name: /Показать фильтры/ }));
    await user.clear(screen.getByLabelText("Дата от"));
    await user.type(screen.getByLabelText("Дата от"), "2026-08-01");
    await user.selectOptions(screen.getByLabelText("Валюта"), "USD");
    await user.selectOptions(screen.getByLabelText("Тип операции"), "expense");
    await user.click(screen.getByRole("button", { name: "Применить" }));

    expect(screen.getByTestId("location")).toHaveTextContent(
      "date_from=2026-08-01",
    );
    expect(screen.getByTestId("location")).toHaveTextContent("currency=USD");
    expect(screen.getByTestId("location")).toHaveTextContent("type=expense");
    expect(screen.getByTestId("location")).toHaveTextContent(
      "return_to=%2Fapp%2Freports%3Fcurrency%3DRUB",
    );
    expect(screen.getByTestId("location")).not.toHaveTextContent(
      "operations_page=",
    );
  });

  it("searches operations without dropping filters or report context", async () => {
    const user = userEvent.setup();
    renderPage(
      "/categories/id?currency=RUB&type=expense&operations_page=2&return_to=%2Fapp%2Freports",
    );

    await user.type(
      screen.getByRole("searchbox", {
        name: "Поиск по описанию операции",
      }),
      "  market  ",
    );
    await user.click(screen.getByRole("button", { name: "Найти" }));

    const location = screen.getByTestId("location");
    expect(location).toHaveTextContent("search=market");
    expect(location).toHaveTextContent("currency=RUB");
    expect(location).toHaveTextContent("type=expense");
    expect(location).toHaveTextContent("return_to=%2Fapp%2Freports");
    expect(location).not.toHaveTextContent("operations_page=");
  });

  it("changes page size and resets operation pagination", async () => {
    const user = userEvent.setup();
    renderPage("/categories/id?currency=RUB&operations_page=2");

    await user.selectOptions(screen.getByLabelText("На странице"), "50");

    const location = screen.getByTestId("location");
    expect(location).toHaveTextContent("currency=RUB");
    expect(location).toHaveTextContent("operations_page_size=50");
    expect(location).not.toHaveTextContent("operations_page=2");
  });

  it("edits a custom category and replaces the authoritative detail", async () => {
    const user = userEvent.setup();
    const committed = {
      ...detail,
      category: {
        ...detail.category,
        name: "Еда и покупки",
        notes: "Покупки и возвраты",
        updatedAt: "2026-08-01T09:00:00Z",
      },
    };
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(committed)));
    vi.stubGlobal("fetch", fetchMock);
    renderPage("/categories/id?currency=RUB&search=market");

    await user.click(screen.getByRole("button", { name: "Изменить" }));
    expect(
      screen.getByRole("dialog", { name: "Изменить категорию" }),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Закрыть" })).toBeVisible();
    const name = await screen.findByLabelText(/^Название/);
    await user.clear(name);
    await user.type(name, "Еда и покупки");
    const notes = await screen.findByLabelText("Заметка");
    await user.clear(notes);
    await user.type(notes, "Покупки и возвраты");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(
      await screen.findByRole("heading", { name: "Еда и покупки" }),
    ).toBeVisible();
    expect(
      screen.getByText("Категория «Еда и покупки» изменена."),
    ).toBeVisible();
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/categories/${detail.category.id}?currency=RUB&search=market`,
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("confirms linked kind impact before saving", async () => {
    const user = userEvent.setup();
    const committed = {
      ...detail,
      category: { ...detail.category, kind: "mixed" as const },
    };
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse(committed)));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    await user.click(screen.getByRole("button", { name: "Изменить" }));
    await user.selectOptions(await screen.findByLabelText(/^Тип/), "mixed");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(
      screen.getByRole("heading", {
        name: "Изменить тип связанной категории?",
      }),
    ).toBeVisible();
    expect(screen.getByText("12 операций сохранятся")).toBeVisible();
    expect(screen.getByText("3 правила останутся связанными")).toBeVisible();
    expect(fetchMock).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Изменить тип" }));
    expect(await screen.findByText("Смешанная")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("preserves the draft while reloading after an update conflict", async () => {
    const user = userEvent.setup();
    const fresh = {
      ...detail,
      category: {
        ...detail.category,
        notes: "Изменено в другом окне",
        updatedAt: "2026-08-01T09:15:00Z",
      },
    };
    const committed = {
      ...fresh,
      category: { ...fresh.category, name: "Мой draft" },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(apiErrorResponse(409, "category_update_conflict"))
      .mockResolvedValueOnce(jsonResponse(fresh))
      .mockResolvedValueOnce(jsonResponse(committed));
    vi.stubGlobal("fetch", fetchMock);
    renderPage();

    await user.click(screen.getByRole("button", { name: "Изменить" }));
    const name = await screen.findByLabelText(/^Название/);
    await user.clear(name);
    await user.type(name, "Мой draft");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(
      await screen.findByText("Категория уже была изменена"),
    ).toBeVisible();

    await user.click(
      screen.getByRole("button", { name: "Загрузить актуальную версию" }),
    );
    expect(await screen.findByDisplayValue("Мой draft")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(
      await screen.findByRole("heading", { name: "Мой draft" }),
    ).toBeVisible();
    const retryBody = JSON.parse(
      (fetchMock.mock.calls[2]?.[1] as RequestInit).body as string,
    ) as { expectedUpdatedAt: string };
    expect(retryBody.expectedUpdatedAt).toBe("2026-08-01T09:15:00Z");
  });

  it("hides mutation affordances for system categories and viewers", () => {
    const { unmount } = renderPage("/categories/id", {
      ...detail,
      category: directorySystemCategory(),
    });
    expect(
      screen.queryByRole("button", { name: "Изменить" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Системная · только чтение")).toBeVisible();
    unmount();

    renderPage("/categories/id", {
      ...detail,
      category: {
        ...detail.category,
        capabilities: { ...detail.category.capabilities, canUpdate: false },
      },
    });
    expect(
      screen.queryByRole("button", { name: "Изменить" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Только чтение")).toBeVisible();
  });

  it("focuses invalid fields and protects a dirty edit draft", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Изменить" }));
    const name = await screen.findByLabelText(/^Название/);
    await user.clear(name);
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(screen.getByText("Введите название категории.")).toBeVisible();
    expect(name).toHaveFocus();

    await user.type(name, "Мой draft");
    await user.click(screen.getByRole("button", { name: "Закрыть" }));
    expect(
      screen.getByRole("heading", { name: "Закрыть редактирование?" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Продолжить редактирование" }),
    );
    expect(screen.getByDisplayValue("Мой draft")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Закрыть" }));
    await user.click(
      screen.getByRole("button", { name: "Отменить изменения" }),
    );
    expect(
      screen.queryByRole("heading", { name: "Изменить категорию" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Изменить" })).toHaveFocus();
  });
});

function renderPage(initialEntry = "/categories/id", categoryDetail = detail) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <CategoryDetailPage detail={categoryDetail} session={session} />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.pathname}
      {location.search}
    </output>
  );
}

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

function apiErrorResponse(status: number, code: string): Response {
  return new Response(
    JSON.stringify({ error: { code, message: "Категория уже изменена." } }),
    { headers: { "Content-Type": "application/json" }, status },
  );
}

function directorySystemCategory() {
  return {
    ...detail.category,
    isSystem: true,
    systemKey: "uncategorized",
    capabilities: {
      ...detail.category.capabilities,
      canUpdate: false,
    },
  };
}
