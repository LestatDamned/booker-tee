import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { directory, ruleId, session } from "./test-support";
import { TransactionRulesPage } from "./transaction-rules-page";

describe("TransactionRulesPage", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders complete rule meaning twice for desktop and mobile without mutation controls", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { name: "Правила операций" }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Все 3" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getAllByText("OZON → Маркетплейсы")).toHaveLength(2);
    expect(screen.getAllByText("Описание содержит «OZON»")).toHaveLength(2);
    expect(screen.getAllByText("Сумма 100.00–500.00")).toHaveLength(2);
    expect(screen.getAllByText("Категория: Маркетплейсы")).toHaveLength(2);
    expect(screen.getAllByText("Объект: Старая квартира · архив")).toHaveLength(
      2,
    );
    expect(screen.getAllByText("Влияет на финансовый результат")).toHaveLength(
      2,
    );
    expect(
      screen.queryByRole("button", {
        name: /изменить|выключить|удалить/i,
      }),
    ).not.toBeInTheDocument();
  });

  it("opens the category filter and navigates with URL-owned state", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Фильтры" }));
    const category = screen.getByLabelText("Категория результата");
    expect(
      within(category).getByRole("option", {
        name: "Архивная категория · архив",
      }),
    ).toBeVisible();
    await user.selectOptions(category, directory.references.categories[0]!.id);
    await user.click(screen.getByRole("button", { name: "Применить" }));

    expect(screen.getByTestId("location")).toHaveTextContent(
      `?category_id=${directory.references.categories[0]!.id}`,
    );
  });

  it("marks a deep-linked rule and reports a missing target", () => {
    const { unmount } = renderPage(`/rules#rule-${ruleId}`);
    expect(document.querySelectorAll('[data-targeted="true"]')).toHaveLength(2);
    unmount();

    renderPage("/rules#rule-11111111-1111-4111-8111-111111111111");
    expect(
      screen.getByText("Правило не найдено в текущей выборке"),
    ).toBeVisible();
  });

  it("shows explicit viewer read-only copy and no controls", () => {
    renderPage("/rules", {
      ...directory,
      capabilities: {
        canCreate: false,
        canSeedDefaults: false,
        readonlyReasonCode: "financial_write_forbidden",
      },
      items: directory.items.map((item) => ({
        ...item,
        capabilities: {
          ...item.capabilities,
          canUpdate: false,
          canDisable: false,
        },
      })),
    });

    expect(
      screen.getByText(/Просматривать смысл правил можно с вашей ролью/),
    ).toBeVisible();
    expect(screen.queryByText("Редактировать")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Новое правило" }),
    ).not.toBeInTheDocument();
  });

  it("creates a rule from the right-side dialog and preserves review semantics", async () => {
    const user = userEvent.setup();
    const created = {
      ...directory.items[0]!,
      id: "fc2d7025-7789-4312-9191-d9731d4be611",
      name: "Такси",
      condition: { ...directory.items[0]!.condition, pattern: "YANDEX GO" },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ item: created, replayed: false }), {
            headers: { "Content-Type": "application/json" },
            status: 201,
          }),
        ),
      ),
    );
    renderPage();

    await user.click(screen.getByRole("button", { name: "Новое правило" }));
    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.getByText(/не подтверждает операцию/i)).toBeVisible();
    await user.type(screen.getByLabelText(/^Условие/), "YANDEX GO");
    await user.selectOptions(screen.getByLabelText("Тип операции"), "expense");
    await user.click(screen.getByRole("button", { name: "Создать правило" }));

    expect(await screen.findByText("Правило «Такси» создано.")).toBeVisible();
    expect(screen.getAllByText("Такси")).toHaveLength(2);
    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        `#rule-${created.id}`,
      ),
    );
  });

  it("confirms discarding a dirty create draft", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Новое правило" }));
    await user.type(screen.getByLabelText(/^Условие/), "OZON");
    await user.click(screen.getByRole("button", { name: "Отмена" }));
    expect(
      screen.getByRole("heading", { name: "Закрыть создание правила?" }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Продолжить создание" }),
    );
    expect(screen.getByDisplayValue("OZON")).toBeVisible();
  });

  it("seeds only after confirmation and reports truthful counts", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              createdRules: 2,
              existingRules: 51,
              createdCategories: 1,
            }),
            { headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );
    renderPage();
    await user.click(screen.getByRole("button", { name: "Базовые правила" }));
    expect(
      screen.getByText(/Существующие правила, режимы и состояния не изменятся/),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Добавить недостающие" }),
    );
    expect(
      await screen.findByText(/создано 2, уже было 51, новых категорий 1/),
    ).toBeVisible();
  });
});

function renderPage(initialEntry = "/rules", snapshot = directory) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <TransactionRulesPage directory={snapshot} session={session} />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.search}
      {location.hash}
    </output>
  );
}
