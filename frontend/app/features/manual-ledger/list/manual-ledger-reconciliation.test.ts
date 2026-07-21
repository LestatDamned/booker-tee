import { describe, expect, it } from "vitest";

import type { ManualOperationDto } from "../api/manual-ledger-api";
import {
  emptyManualLedgerLocalChanges,
  reconcileManualLedgerLocalChanges,
  recordManualOperationDeletion,
  recordManualOperationUpdate,
  visibleManualOperations,
} from "./manual-ledger-reconciliation";

describe("manual ledger local reconciliation", () => {
  it("shows a mutation response until the server returns that version", () => {
    const serverOperation = operation({ version: 1, description: "Before" });
    const savedOperation = operation({ version: 2, description: "After" });
    const localChanges = recordManualOperationUpdate(
      emptyManualLedgerLocalChanges(),
      savedOperation,
    );

    expect(
      visibleManualOperations([serverOperation], localChanges)[0]?.description,
    ).toBe("After");
    expect(
      reconcileManualLedgerLocalChanges(localChanges, [savedOperation]).updated,
    ).toEqual({});
  });

  it("forgets a local deletion after the server removes the operation", () => {
    const serverOperation = operation({});
    const localChanges = recordManualOperationDeletion(
      emptyManualLedgerLocalChanges(),
      serverOperation.id,
    );

    expect(visibleManualOperations([serverOperation], localChanges)).toEqual(
      [],
    );
    expect(reconcileManualLedgerLocalChanges(localChanges, []).deleted).toEqual(
      {},
    );
  });
});

function operation(overrides: Partial<ManualOperationDto>): ManualOperationDto {
  return {
    id: "61f1e242-9b4a-43e8-b9f8-4fb0627f771a",
    version: 1,
    operationType: "expense",
    operationDate: "2026-07-20",
    description: "Operation",
    status: "confirmed",
    money: { amount: "10.00", currency: "RUB" },
    account: null,
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
    ...overrides,
  };
}
