import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { StatementReconciliation } from "./statement-reconciliation";
import { importReviewPayload } from "./test-support";

describe("statement balances", () => {
  it.each([
    "match",
    "explained",
    "mismatch",
    "unavailable",
    "needs_review",
  ] as const)(
    "keeps the %s outcome visible and opens only unexplained differences",
    async (balanceStatus) => {
      const user = userEvent.setup();
      const validation = importReviewPayload().validation!;
      validation.balanceStatus = balanceStatus;
      validation.balanceDifference = "30000.00";
      const { rerender } = render(
        <StatementReconciliation validation={validation} />,
      );
      const summary = screen.getByText("Остатки").closest("summary")!;
      const details = summary.closest("details")!;
      expect(summary).toBeVisible();
      expect(details.open).toBe(balanceStatus === "mismatch");
      expect(within(summary).getByText(/30\s000,00/)).toBeVisible();
      await user.click(summary);
      expect(details.open).toBe(balanceStatus !== "mismatch");
      rerender(<StatementReconciliation validation={{ ...validation }} />);
      expect(details.open).toBe(balanceStatus !== "mismatch");
    },
  );

  it("shows source and calculated values and reopens when a mismatch arrives", () => {
    const validation = importReviewPayload().validation!;
    validation.openingBalance = "120000.00";
    validation.closingBalance = "123491.49";
    validation.calculatedClosingBalance = "153491.49";
    validation.balanceDifference = "30000.00";
    validation.balanceStatus = "explained";
    const { rerender } = render(
      <StatementReconciliation validation={validation} />,
    );
    rerender(
      <StatementReconciliation
        validation={{ ...validation, balanceStatus: "mismatch" }}
      />,
    );
    const table = screen.getByRole("table", { name: "Сравнение остатков" });
    expect(within(table).getByText("В выписке")).toBeVisible();
    expect(within(table).getByText("По импортируемым строкам")).toBeVisible();
    expect(within(table).getByText(/123\s491,49/)).toBeVisible();
    expect(within(table).getByText(/153\s491,49/)).toBeVisible();
  });

  it("hides absent balances and never invents a starting balance", async () => {
    const validation = importReviewPayload().validation!;
    validation.openingBalance = null;
    validation.closingBalance = null;
    const { rerender } = render(
      <StatementReconciliation validation={validation} />,
    );
    expect(screen.queryByText("Остатки")).not.toBeInTheDocument();
    rerender(
      <StatementReconciliation
        validation={{
          ...validation,
          closingBalance: "0.00",
          calculatedClosingBalance: null,
          balanceDifference: null,
          balanceStatus: "unavailable",
        }}
      />,
    );
    await userEvent.setup().click(screen.getByText("Остатки"));
    expect(screen.queryByText("На начало")).not.toBeInTheDocument();
    expect(screen.getByText("На конец")).toBeVisible();
    expect(screen.getByText("Недостаточно данных для сверки")).toBeVisible();
  });
});
