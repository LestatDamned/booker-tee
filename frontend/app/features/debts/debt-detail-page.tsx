import { useState } from "react";
import { useLocation, useNavigate } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatIsoDate } from "../../shared/date/format-date";
import { formatMoneyAmount } from "../../shared/money/format-money";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import { AppShell } from "../../shell/app-shell";
import { ActionStack } from "../../ui/action-stack/action-stack";
import { BackLink } from "../../ui/back-link/back-link";
import { Button } from "../../ui/button/button";
import { ConfirmationDialog } from "../../ui/confirmation-dialog/confirmation-dialog";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { MoneyValue } from "../../ui/money-value/money-value";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { ReadOnlyFinancialRow } from "../../ui/read-only-financial-row/read-only-financial-row";
import { StatusLabel } from "../../ui/status-label/status-label";
import { Tag } from "../../ui/tag/tag";
import { ToastViewport, useToastQueue } from "../../ui/toast/toast";
import { WorkbenchContent } from "../../ui/workbench-content/workbench-content";
import { WorkbenchEmptyState } from "../../ui/workbench-empty-state/workbench-empty-state";
import { WorkbenchHeader } from "../../ui/workbench-surface/workbench-header";
import { WorkbenchSurface } from "../../ui/workbench-surface/workbench-surface";
import { WorkbenchPagination } from "../../ui/workbench-pagination/workbench-pagination";
import type { AccountSummaryDto } from "../accounts/api/accounts-api";
import type { CategorySummaryDto } from "../categories/api/categories-api";
import {
  changeDebtLifecycle,
  deleteDebt,
  undoDebtPayment,
  type DebtDetailDto,
} from "./api/debts-api";
import {
  debtDirectionLabel,
  debtKindLabels,
  debtStatusLabels,
} from "./debt-model";
import { DebtEditPanel } from "./debt-edit-panel";
import { DebtPaymentPanel } from "./debt-payment-panel";
import styles from "./debts.module.css";

type Payment = DebtDetailDto["payments"]["items"][number];

export function DebtDetailPage({
  accounts,
  categories,
  detail: initialDetail,
  navigationPending = false,
  session,
}: {
  accounts: AccountSummaryDto[];
  categories: CategorySummaryDto[];
  detail: DebtDetailDto;
  navigationPending?: boolean;
  session: SessionDto;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [localDetail, setLocalDetail] = useState<{
    source: DebtDetailDto;
    value: DebtDetailDto;
  } | null>(null);
  const detail =
    localDetail?.source === initialDetail ? localDetail.value : initialDetail;
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [undoCandidate, setUndoCandidate] = useState<Payment | null>(null);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const { dismissToast, showToast, toast } = useToastQueue();
  const debt = detail.debt;

  function commit(next: DebtDetailDto, message: string) {
    setLocalDetail({ source: initialDetail, value: next });
    setFailure(null);
    showToast({ message });
  }

  async function lifecycle(action: "archive" | "restore") {
    if (pending) return;
    setPending(true);
    setFailure(null);
    const result = await changeDebtLifecycle(debt, action, session.csrfToken);
    setPending(false);
    setArchiveOpen(false);
    if (result.status === "success") {
      commit(
        result.detail,
        action === "archive" ? "Долг перенесён в архив." : "Долг восстановлен.",
      );
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setFailure(result.message);
  }

  async function confirmUndo() {
    if (!undoCandidate || pending) return;
    setPending(true);
    setFailure(null);
    const result = await undoDebtPayment(undoCandidate, session.csrfToken);
    setPending(false);
    setUndoCandidate(null);
    if (result.status === "success") {
      commit(
        result.detail,
        "Платёж отменён, связанные операции исключены из учёта.",
      );
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setFailure(result.message);
  }

  async function confirmDelete() {
    if (pending) return;
    setPending(true);
    setFailure(null);
    const result = await deleteDebt(debt, session.csrfToken);
    setPending(false);
    setDeleteOpen(false);
    if (result.status === "success") {
      void navigate("/debts", { replace: true });
      return;
    }
    if (redirectIfUnauthenticated(result)) return;
    setFailure(result.message);
  }

  const paymentBlockedMessage = paymentBlockedReason(
    debt.capabilities.paymentBlockedReason,
  );

  return (
    <AppShell session={session}>
      <PageFrame mobileTop="compact" spacing="block">
        <WorkbenchSurface
          aria-busy={navigationPending}
          className={styles.workbench}
        >
          <WorkbenchHeader>
            <BackLink to="/debts">Все долги</BackLink>
            <PageHeader
              actions={
                <ActionStack
                  dismissOnAction
                  orientation="row"
                  primary={
                    debt.capabilities.canRecordPayment ? (
                      <Button
                        onClick={() => setPaymentOpen(true)}
                        tone="primary"
                      >
                        Записать платёж
                      </Button>
                    ) : undefined
                  }
                  secondary={
                    debt.capabilities.canRestore ? (
                      <Button
                        disabled={pending}
                        icon="undo"
                        isLoading={pending}
                        onClick={() => void lifecycle("restore")}
                        tone="secondary"
                      >
                        Восстановить
                      </Button>
                    ) : debt.capabilities.canArchive ? (
                      <Button
                        disabled={pending}
                        onClick={() => setArchiveOpen(true)}
                        tone="secondary"
                      >
                        В архив
                      </Button>
                    ) : undefined
                  }
                  overflow={
                    debt.capabilities.canUpdate ? (
                      <Button onClick={() => setEditOpen(true)} tone="ghost">
                        Изменить
                      </Button>
                    ) : undefined
                  }
                  danger={
                    debt.capabilities.canDelete ? (
                      <Button onClick={() => setDeleteOpen(true)} tone="danger">
                        Удалить
                      </Button>
                    ) : debt.capabilities.deleteBlockedReason ===
                      "financial_history" ? (
                      <Button
                        onClick={() =>
                          setFailure(
                            "Долг уже имеет платежи, импорт или последующие операции. Его нужно погасить и перенести в архив.",
                          )
                        }
                        tone="danger"
                      >
                        Удалить
                      </Button>
                    ) : undefined
                  }
                />
              }
              description={detail.notes ?? debtDirectionLabel(debt.kind)}
              eyebrow={debtKindLabels[debt.kind]}
              title={debt.name}
            />
            <div className={styles.identityMeta}>
              <Tag
                tone={debt.kind === "loan_receivable" ? "income" : "expense"}
                variant="soft"
              >
                {debtDirectionLabel(debt.kind)}
              </Tag>
              <StatusLabel
                tone={
                  debt.status === "active"
                    ? "information"
                    : debt.status === "archived"
                      ? "neutral"
                      : "success"
                }
              >
                {debtStatusLabels[debt.status]}
              </StatusLabel>
            </div>
            <DebtFacts detail={detail} />
          </WorkbenchHeader>

          {paymentBlockedMessage ? (
            <InlineNotice
              className={styles.notice}
              title="Новый платёж сейчас недоступен"
              tone="information"
            >
              {paymentBlockedMessage}
            </InlineNotice>
          ) : null}
          {failure ? (
            <InlineNotice
              action={
                <Button
                  icon="retry"
                  onClick={() =>
                    void navigate(location.pathname + location.search, {
                      replace: true,
                    })
                  }
                  tone="secondary"
                >
                  Обновить страницу
                </Button>
              }
              className={styles.notice}
              role="alert"
              title="Действие не выполнено"
              tone="danger"
            >
              {failure}
            </InlineNotice>
          ) : null}

          <section
            aria-labelledby="debt-payment-history-title"
            className={styles.history}
          >
            <div className={styles.sectionHeader}>
              <div>
                <h2 id="debt-payment-history-title">История платежей</h2>
                <p>{paymentCountLabel(detail.payments.total)}</p>
              </div>
            </div>
            <WorkbenchContent
              aria-label="История платежей"
              isEmpty={detail.payments.items.length === 0}
            >
              {detail.payments.items.length ? (
                <div className={styles.historyRows}>
                  {detail.payments.items.map((payment) => (
                    <ReadOnlyFinancialRow
                      context={
                        payment.reversedAt ? "Платёж отменён" : "Платёж учтён"
                      }
                      date={formatIsoDate(
                        (payment.principal ?? payment.interest)
                          ?.operationDate ?? payment.createdAt.slice(0, 10),
                      )}
                      dateTime={
                        (payment.principal ?? payment.interest)?.operationDate
                      }
                      description={
                        (payment.principal ?? payment.interest)?.description ??
                        "Платёж по долгу"
                      }
                      details={
                        <PaymentParts
                          payment={payment}
                          currency={debt.currency}
                        />
                      }
                      id={`payment-${payment.paymentId}`}
                      key={payment.paymentId}
                      status={
                        payment.reversedAt ? (
                          <StatusLabel tone="neutral">Отменён</StatusLabel>
                        ) : payment.canUndo ? (
                          <Button
                            disabled={pending}
                            icon="undo"
                            onClick={() => setUndoCandidate(payment)}
                            tone="ghost"
                          >
                            Отменить
                          </Button>
                        ) : undefined
                      }
                    />
                  ))}
                </div>
              ) : (
                <WorkbenchEmptyState
                  icon="operations"
                  title="Платежей пока нет"
                >
                  Запишите первый платёж, разделив основной долг и проценты.
                </WorkbenchEmptyState>
              )}
            </WorkbenchContent>
            {detail.payments.total > 0 ? (
              <WorkbenchPagination
                ariaLabel="Страницы истории платежей"
                currentPage={detail.payments.page}
                getPageHref={(page) =>
                  debtPaymentPageUrl(
                    debt.accountId,
                    page,
                    detail.payments.pageSize,
                  )
                }
                hasNext={detail.payments.hasNext}
                hasPrevious={detail.payments.hasPrevious}
                summary={`${detail.payments.items.length} из ${detail.payments.total}`}
                totalPages={detail.payments.totalPages}
              />
            ) : null}
          </section>
        </WorkbenchSurface>
      </PageFrame>
      <ToastViewport onDismiss={dismissToast} toast={toast} />

      {paymentOpen ? (
        <DebtPaymentPanel
          accounts={accounts}
          categories={categories}
          detail={detail}
          onClose={() => setPaymentOpen(false)}
          onCommitted={(next) => {
            setPaymentOpen(false);
            commit(next, "Платёж записан.");
          }}
          session={session}
        />
      ) : null}
      {editOpen ? (
        <DebtEditPanel
          csrfToken={session.csrfToken}
          detail={detail}
          onClose={() => setEditOpen(false)}
          onUpdated={(next) => {
            setEditOpen(false);
            commit(next, "Долг изменён.");
          }}
        />
      ) : null}
      {archiveOpen ? (
        <ConfirmationDialog
          confirmLabel="Перенести в архив"
          description={`Долг «${debt.name}» останется в истории, но новые платежи будут недоступны.`}
          onCancel={() => setArchiveOpen(false)}
          onConfirm={() => void lifecycle("archive")}
          pending={pending}
          title="Перенести долг в архив?"
        />
      ) : null}
      {undoCandidate ? (
        <ConfirmationDialog
          confirmLabel="Отменить платёж"
          description="Основной долг и проценты будут исключены из финансового учёта вместе. История отмены сохранится."
          onCancel={() => setUndoCandidate(null)}
          onConfirm={() => void confirmUndo()}
          pending={pending}
          title="Отменить этот платёж?"
        />
      ) : null}
      {deleteOpen ? (
        <ConfirmationDialog
          confirmLabel="Удалить долг"
          description={`«${debt.name}» будет удалён безвозвратно. Если при создании займа был записан transfer, он тоже будет удалён и баланс второго счёта восстановится.`}
          onCancel={() => setDeleteOpen(false)}
          onConfirm={() => void confirmDelete()}
          pending={pending}
          title="Удалить неиспользованный долг?"
        />
      ) : null}
    </AppShell>
  );
}

function DebtFacts({ detail }: { detail: DebtDetailDto }) {
  const debt = detail.debt;
  return (
    <dl className={styles.facts}>
      <Fact label="Остаток основного долга">
        <MoneyValue
          amount={formatMoneyAmount(debt.outstanding, null)}
          currency={debt.currency}
          size="prominent"
          tone={debt.kind === "loan_receivable" ? "income" : "expense"}
        />
      </Fact>
      {debt.originalPrincipal ? (
        <Fact label="Первоначальная сумма">
          <MoneyValue
            amount={formatMoneyAmount(debt.originalPrincipal, null)}
            currency={debt.currency}
          />
        </Fact>
      ) : null}
      <Fact label="Проведено principal">
        <MoneyValue
          amount={formatMoneyAmount(detail.paymentTotals.principal, null)}
          currency={debt.currency}
          tone="transfer"
        />
      </Fact>
      <Fact
        label={
          debt.kind === "loan_receivable"
            ? "Получено процентов"
            : "Уплачено процентов"
        }
      >
        <MoneyValue
          amount={formatMoneyAmount(detail.paymentTotals.interest, null)}
          currency={debt.currency}
          tone={debt.kind === "loan_receivable" ? "income" : "expense"}
        />
      </Fact>
      {debt.creditLimit ? (
        <Fact label="Кредитный лимит">
          <MoneyValue
            amount={formatMoneyAmount(debt.creditLimit, null)}
            currency={debt.currency}
          />
        </Fact>
      ) : null}
      {debt.availableCredit ? (
        <Fact label="Доступно по лимиту">
          <MoneyValue
            amount={formatMoneyAmount(debt.availableCredit, null)}
            currency={debt.currency}
          />
        </Fact>
      ) : null}
      {debt.openedOn ? (
        <Fact label="Дата открытия">{formatIsoDate(debt.openedOn)}</Fact>
      ) : null}
      {debt.maturityDate ? (
        <Fact label="Конечный срок">{formatIsoDate(debt.maturityDate)}</Fact>
      ) : null}
    </dl>
  );
}

function Fact({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function PaymentParts({
  payment,
  currency,
}: {
  payment: Payment;
  currency: string;
}) {
  return (
    <div className={styles.paymentParts}>
      {payment.principal ? (
        <span>
          Основной долг{" "}
          <MoneyValue
            amount={formatMoneyAmount(payment.principal.amount, null)}
            currency={currency}
            tone="transfer"
          />
        </span>
      ) : null}
      {payment.interest ? (
        <span>
          Проценты{" "}
          <MoneyValue
            amount={formatMoneyAmount(payment.interest.amount, null)}
            currency={currency}
            tone={
              payment.interest.operationType === "income" ? "income" : "expense"
            }
          />
        </span>
      ) : null}
      {payment.notes ? <span>{payment.notes}</span> : null}
    </div>
  );
}

function paymentBlockedReason(
  reason: DebtDetailDto["debt"]["capabilities"]["paymentBlockedReason"],
): string | null {
  if (reason === "debt_archived") return "Сначала восстановите долг из архива.";
  if (reason === "debt_settled") return "Основной долг уже равен нулю.";
  if (reason === "no_payment_account")
    return "Добавьте активный денежный счёт в той же валюте.";
  if (reason === "financial_write_forbidden")
    return "У вас есть доступ только для просмотра.";
  return null;
}

function debtPaymentPageUrl(
  debtId: string,
  page: number,
  pageSize: number,
): string {
  const params = new URLSearchParams();
  if (page > 1) params.set("page", String(page));
  if (pageSize !== 20) params.set("page_size", String(pageSize));
  const query = params.toString();
  return query ? `/debts/${debtId}?${query}` : `/debts/${debtId}`;
}

function paymentCountLabel(count: number): string {
  return `${count} ${count === 1 ? "платёж" : count >= 2 && count <= 4 ? "платежа" : "платежей"}`;
}
