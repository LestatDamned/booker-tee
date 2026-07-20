import { Badge } from "../../ui/badge/badge";
import { MoneyValue } from "../../ui/money-value/money-value";
import { WorkbenchRow } from "../../ui/workbench-row/workbench-row";
import type { ManualOperationRowModel } from "./manual-ledger-model";

type ManualOperationRowProps = {
  isTargeted: boolean;
  operation: ManualOperationRowModel;
};

export function ManualOperationRow({
  isTargeted,
  operation,
}: ManualOperationRowProps) {
  return (
    <WorkbenchRow
      date={operation.date}
      description={operation.description}
      id={operation.anchorId}
      meta={
        <>
          <Badge tone={operation.operationTone}>
            {operation.operationLabel}
          </Badge>
          <Badge tone={operation.statusTone}>{operation.statusLabel}</Badge>
          {operation.meta.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </>
      }
      state={isTargeted ? "target" : "default"}
      value={
        operation.money ? (
          <MoneyValue
            amount={operation.money.amount}
            currency={operation.money.currency}
            tone={operation.money.tone}
          />
        ) : undefined
      }
    />
  );
}
