import type { ManualOperationDto } from "../api/manual-ledger-api";

type VersionedOperation = { id: string; version: number };

export type ManualLedgerLocalChanges<
  T extends VersionedOperation = ManualOperationDto,
> = {
  updated: Record<string, T>;
  deleted: Record<string, true>;
};

export function emptyManualLedgerLocalChanges<
  T extends VersionedOperation = ManualOperationDto,
>(): ManualLedgerLocalChanges<T> {
  return { updated: {}, deleted: {} };
}

export function recordManualOperationUpdate<T extends VersionedOperation>(
  current: ManualLedgerLocalChanges<T>,
  operation: T,
): ManualLedgerLocalChanges<T> {
  return {
    ...current,
    updated: { ...current.updated, [operation.id]: operation },
  };
}

export function recordManualOperationDeletion<T extends VersionedOperation>(
  current: ManualLedgerLocalChanges<T>,
  operationId: string,
): ManualLedgerLocalChanges<T> {
  return {
    ...current,
    deleted: { ...current.deleted, [operationId]: true },
  };
}

export function reconcileManualLedgerLocalChanges<T extends VersionedOperation>(
  current: ManualLedgerLocalChanges<T>,
  serverOperations: T[],
): ManualLedgerLocalChanges<T> {
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

export function visibleManualOperations<T extends VersionedOperation>(
  serverOperations: T[],
  localChanges: ManualLedgerLocalChanges<T>,
): T[] {
  return serverOperations
    .filter((operation) => !localChanges.deleted[operation.id])
    .map((operation) => {
      const updated = localChanges.updated[operation.id];
      return updated && updated.version > operation.version
        ? updated
        : operation;
    });
}
