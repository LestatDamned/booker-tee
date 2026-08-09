import { describe, expect, it } from "vitest";

import { DebtCreateDrafts, DebtMoney } from "./debt-model";

describe("debt form model", () => {
  it("builds every supported create command without signed money", () => {
    const base = {
      ...DebtCreateDrafts.empty("RUB"),
      accountId: "11111111-1111-4111-8111-111111111111",
      amount: "100,50",
      creditLimit: "200000.00",
      maturityDate: "2027-01-01",
      name: "Долг",
      openingBalance: "75.00",
      openingDebt: "1000.00",
      originalPrincipal: "100.00",
    };

    expect(
      DebtCreateDrafts.build({ ...base, action: "give_loan" }),
    ).toMatchObject({
      action: "give_loan",
      amount: "100.50",
      fundingAccountId: base.accountId,
    });
    expect(
      DebtCreateDrafts.build({
        ...base,
        action: "take_loan",
        kind: "mortgage",
      }),
    ).toMatchObject({
      action: "take_loan",
      kind: "mortgage",
      receivingAccountId: base.accountId,
    });
    expect(
      DebtCreateDrafts.build({ ...base, action: "open_credit_card" }),
    ).toMatchObject({
      action: "open_credit_card",
      creditLimit: "200000.00",
      openingDebt: "1000.00",
    });
    expect(
      DebtCreateDrafts.build({
        ...base,
        action: "add_existing",
        kind: "loan_payable",
      }),
    ).toMatchObject({
      action: "add_existing",
      openingBalance: "75.00",
      originalPrincipal: "100.00",
    });
  });

  it("compares decimal money exactly and rejects an excessive card debt", () => {
    expect(DebtMoney.toMinor("9007199254740993.01")).toBe(900719925474099301n);
    const draft = {
      ...DebtCreateDrafts.empty("RUB"),
      action: "open_credit_card" as const,
      creditLimit: "100.00",
      name: "Кредитка",
      openingDebt: "100.01",
    };

    expect(DebtCreateDrafts.validate(draft).openingDebt).toBe(
      "Текущий долг не может превышать лимит.",
    );
  });
});
