import { RouterButtonLink } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import type { ReportOverviewDto } from "./api/reports-api";
import { operationHref } from "../operations/operation-navigation";

type Operation = ReportOverviewDto["uncategorized"]["items"][number];

export function ReportUncategorizedNotice({
  overview,
}: {
  overview: ReportOverviewDto;
}) {
  const page = overview.uncategorized;
  if (page.total === 0) return null;
  const operation = page.items.find((item) => correctionHref(item) !== null);
  const href = operation ? correctionHref(operation) : null;

  return (
    <InlineNotice
      action={
        href ? (
          <RouterButtonLink to={href} icon="edit" tone="secondary">
            Разобрать
          </RouterButtonLink>
        ) : undefined
      }
      title={`${page.total} ${operationCountLabel(page.total)} без категории`}
      tone="warning"
    >
      Они уже влияют на финансовый результат. Добавьте категории, чтобы отчёт
      был точнее.
    </InlineNotice>
  );
}

export function reportUncategorizedCorrectionHref(
  overview: ReportOverviewDto,
): string | null {
  const operation = overview.uncategorized.items.find(
    (item) => correctionHref(item) !== null,
  );
  return operation ? correctionHref(operation) : null;
}

function correctionHref(operation: Operation): string | null {
  if (!operation.capabilities.canCorrect) return null;
  return operationHref(operation.operationId);
}

function operationCountLabel(value: number): string {
  const modulo100 = value % 100;
  const modulo10 = value % 10;
  if (modulo100 >= 11 && modulo100 <= 14) return "операций";
  if (modulo10 === 1) return "операция";
  if (modulo10 >= 2 && modulo10 <= 4) return "операции";
  return "операций";
}
