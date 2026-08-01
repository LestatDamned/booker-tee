import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MoneyValue } from "../money-value/money-value";
import { StatusLabel } from "../status-label/status-label";
import { ReadOnlyFinancialRow } from "./read-only-financial-row";

describe("ReadOnlyFinancialRow", () => {
  it("renders a compact financial fact without interactive row behavior", () => {
    const { container } = render(
      <ReadOnlyFinancialRow
        context="стр. 2 · строка 14"
        date="20.07.2026"
        dateTime="2026-07-20"
        description="Комиссия банка"
        details={<span>Основной счёт</span>}
        issues={<p role="alert">Сумма не распознана</p>}
        status={<StatusLabel tone="danger">Ошибка</StatusLabel>}
        tone="problem"
        value={<MoneyValue amount="−450,00" currency="RUB" tone="expense" />}
      />,
    );

    expect(screen.getByText("Комиссия банка")).toBeVisible();
    expect(screen.getByText("стр. 2 · строка 14")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Сумма не распознана");
    expect(container.querySelector("article")).not.toHaveAttribute("tabindex");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
