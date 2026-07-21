import { describe, expect, it } from "vitest";

import type { components } from "../../api/generated/schema";
import {
  manualOperationsTotalLabel,
  toManualOperationRowModel,
} from "./manual-ledger-model";

type ManualOperationDto = components["schemas"]["ManualOperationResponse"];

describe("toManualOperationRowModel", () => {
  it("maps backend description directly into the primary row content", () => {
    const row = toManualOperationRowModel(operation());

    expect(row.description).toBe("Аренда за июль");
    expect(row.date).toBe("2026-07-20");
    expect(row.version).toBe(3);
    expect(row.canCancel).toBe(true);
    expect(row.canDelete).toBe(false);
    expect(row.canRestore).toBe(false);
    expect(row.money).toEqual({
      amount: "−65 000,00",
      currency: "RUB",
      tone: "expense",
    });
  });

  it("uses explicit transfer semantics instead of inferring from amount", () => {
    const dto = operation();
    dto.money = {
      amount: "65000.00",
      currency: "RUB",
      operationType: "transfer",
      entryDirection: "transfer",
    };
    dto.account = null;
    dto.sourceAccount = { id: crypto.randomUUID(), name: "Карта" };
    dto.destinationAccount = { id: crypto.randomUUID(), name: "Накопительный" };

    const row = toManualOperationRowModel(dto);

    expect(row.money?.tone).toBe("transfer");
    expect(row.money?.amount).toBe("65 000,00");
    expect(row.transferRouteLabel).toBe("Карта → Накопительный");
    expect(row.accountLabel).toBeNull();
    expect(row.categoryLabel).toBeNull();
  });

  it("uses readable Russian totals", () => {
    expect(manualOperationsTotalLabel(1)).toBe("1 ручная операция");
    expect(manualOperationsTotalLabel(22)).toBe("22 ручные операции");
    expect(manualOperationsTotalLabel(11)).toBe("11 ручных операций");
  });
});

function operation(): ManualOperationDto {
  return {
    id: crypto.randomUUID(),
    version: 3,
    operationDate: "2026-07-20",
    description: "Аренда за июль",
    status: "confirmed",
    money: {
      amount: "65000.00",
      currency: "RUB",
      operationType: "expense",
      entryDirection: "outflow",
    },
    account: { id: crypto.randomUUID(), name: "Основной счёт" },
    sourceAccount: null,
    destinationAccount: null,
    category: null,
    property: null,
    capabilities: {
      canEdit: true,
      canCancel: true,
      canRestore: false,
      canDelete: false,
      readonlyReason: null,
    },
  };
}
