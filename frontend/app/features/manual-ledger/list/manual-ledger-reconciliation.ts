import type { ManualOperationDto } from "../api/manual-ledger-api";

export type ManualLedgerLocalChanges = {
  updated: Record<string, ManualOperationDto>;
  deleted: Record<string, true>;
};

export function emptyManualLedgerLocalChanges(): ManualLedgerLocalChanges {
  return { updated: {}, deleted: {} };
}

export function recordManualOperationUpdate(
  current: ManualLedgerLocalChanges,
  operation: ManualOperationDto,
): ManualLedgerLocalChanges {
  return {
    ...current,
    updated: { ...current.updated, [operation.id]: operation },
  };
}

export function recordManualOperationDeletion(
  current: ManualLedgerLocalChanges,
  operationId: string,
): ManualLedgerLocalChanges {
  return {
    ...current,
    deleted: { ...current.deleted, [operationId]: true },
  };
}

export function reconcileManualLedgerLocalChanges(
  current: ManualLedgerLocalChanges,
  serverOperations: ManualOperationDto[],
): ManualLedgerLocalChanges {
  const serverById = new Map(
    serverOperations.map((operation) => [operation.id, operation]),
  );
  const updated = Object.fromEntries(
    Object.entries(current.updated).filter(([operationId, localOperation]) => {
      const serverOperation = serverById.get(operationId);
      return serverOperation !== undefined
        ? localOperation.version > serverOperation.version
        : false;
    }),
  );
  const deleted = Object.fromEntries(
    Object.entries(current.deleted).filter(([operationId]) =>
      serverById.has(operationId),
    ),
  );

  if (
    Object.keys(updated).length === Object.keys(current.updated).length &&
    Object.keys(deleted).length === Object.keys(current.deleted).length
  ) {
    return current;
  }
  return { updated, deleted };
}

export function visibleManualOperations(
  serverOperations: ManualOperationDto[],
  localChanges: ManualLedgerLocalChanges,
): ManualOperationDto[] {
  return serverOperations
    .filter((operation) => !localChanges.deleted[operation.id])
    .map((operation) => {
      const updated = localChanges.updated[operation.id];
      return updated && updated.version > operation.version
        ? updated
        : operation;
    });
}
