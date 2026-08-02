import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { directory, ruleId, session } from "./test-support";
import { TransactionRulesPage } from "./transaction-rules-page";

describe("TransactionRulesPage", () => {
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
        name: /создать|изменить|выключить|удалить/i,
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
