import { Link } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatIsoDate } from "../../shared/date/format-date";
import {
  decimalSign,
  formatMoneyAmount,
} from "../../shared/money/format-money";
import { AppShell } from "../../shell/app-shell";
import { RouterButtonLink } from "../../ui/button/button";
import { Icon } from "../../ui/icon/icon";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { MoneyValue, type MoneyTone } from "../../ui/money-value/money-value";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import {
  StatusLabel,
  type StatusTone,
} from "../../ui/status-label/status-label";
import type {
  DashboardDocumentDto,
  DashboardOverviewDto,
} from "./api/dashboard-api";
import styles from "./dashboard-page.module.css";

const documentStatuses: Record<
  DashboardDocumentDto["status"],
  { label: string; tone: StatusTone }
> = {
  uploaded: { label: "Загружен", tone: "information" },
  pending_parse: { label: "Ожидает разбора", tone: "warning" },
  parsing: { label: "Разбирается", tone: "information" },
  parsed: { label: "Готов к проверке", tone: "warning" },
  requires_review: { label: "Требует решения", tone: "warning" },
  failed_to_parse: { label: "Ошибка разбора", tone: "danger" },
  imported: { label: "Проведён", tone: "success" },
  ignored: { label: "Игнорируется", tone: "neutral" },
};

export function DashboardPage({
  dashboard,
  session,
}: {
  dashboard: DashboardOverviewDto;
  session: SessionDto;
}) {
  return (
    <AppShell session={session}>
      <PageFrame>
        <div className={styles.page}>
          <PageHeader
            actions={
              <PrimaryAction action={dashboard.capabilities.primaryAction} />
            }
            description="Проверенные данные, текущий результат и следующий шаг без лишней аналитики."
            eyebrow={formatPeriod(dashboard.period.start, dashboard.period.end)}
            title="Обзор"
            titleId="dashboard-title"
          />

          <AttentionSection attention={dashboard.attention} />

          {!dashboard.onboarding.isComplete ? (
            <OnboardingSection dashboard={dashboard} />
          ) : null}

          <MoneySummary summary={dashboard.summary} />

          <div className={styles.columns}>
            <AccountsSection dashboard={dashboard} />
            <RecentDocumentsSection documents={dashboard.recentDocuments} />
          </div>
        </div>
      </PageFrame>
    </AppShell>
  );
}

function PrimaryAction({
  action,
}: {
  action: DashboardOverviewDto["capabilities"]["primaryAction"];
}) {
  if (action === "upload") {
    return (
      <RouterButtonLink icon="imports" to="/imports/upload" tone="primary">
        Загрузить выписку
      </RouterButtonLink>
    );
  }
  if (action === "manual_operation") {
    return (
      <RouterButtonLink icon="plus" to="/ledger/manual" tone="primary">
        Добавить операцию
      </RouterButtonLink>
    );
  }
  return (
    <RouterButtonLink icon="reports" to="/reports" tone="primary">
      Открыть отчёт
    </RouterButtonLink>
  );
}

function AttentionSection({
  attention,
}: {
  attention: DashboardOverviewDto["attention"];
}) {
  if (attention.total === 0) {
    return (
      <InlineNotice title="Нет данных, требующих решения" tone="success">
        Импорты не содержат открытых ошибок или очередей проверки.
      </InlineNotice>
    );
  }
  return (
    <section aria-labelledby="attention-title" className={styles.attentionCard}>
      <SectionHeading
        action={
          <RouterButtonLink icon="imports" to="/imports?state=attention">
            Вся очередь
          </RouterButtonLink>
        }
        eyebrow={`${attention.total} требуют действия`}
        title="Требует внимания"
        titleId="attention-title"
      />
      <ul className={styles.documentList}>
        {attention.items.map((document) => (
          <DocumentRow document={document} key={document.id} />
        ))}
      </ul>
    </section>
  );
}

function MoneySummary({
  summary,
}: {
  summary: DashboardOverviewDto["summary"];
}) {
  const resultSign = decimalSign(summary.profit);
  return (
    <section aria-labelledby="month-result-title">
      <div className={styles.sectionTitleLine}>
        <div>
          <p className={styles.eyebrow}>Только подтверждённые операции</p>
          <h2 id="month-result-title">Результат месяца</h2>
        </div>
        <Link className={styles.textLink} to="/reports">
          Подробный отчёт
        </Link>
      </div>
      <div className={styles.moneyGrid}>
        <MoneyMetric
          amount={formatMoneyAmount(summary.income, "income")}
          currency={summary.currency}
          label="Доходы"
          tone="income"
        />
        <MoneyMetric
          amount={formatMoneyAmount(summary.expense, "expense")}
          currency={summary.currency}
          label="Расходы"
          tone="expense"
        />
        <MoneyMetric
          amount={formatMoneyAmount(
            summary.profit,
            resultSign === 1 ? "income" : resultSign === -1 ? "expense" : null,
          )}
          currency={summary.currency}
          label="Результат"
          tone={resultSign === -1 ? "expense" : "profit"}
        />
      </div>
      <p className={styles.transferNote}>
        Внутренние переводы не входят в доходы, расходы и результат.
      </p>
    </section>
  );
}

function MoneyMetric({
  amount,
  currency,
  label,
  tone,
}: {
  amount: string;
  currency: string;
  label: string;
  tone: MoneyTone;
}) {
  return (
    <article className={styles.moneyMetric}>
      <span>{label}</span>
      <MoneyValue
        amount={amount}
        currency={currency}
        size="prominent"
        tone={tone}
      />
    </article>
  );
}

function AccountsSection({ dashboard }: { dashboard: DashboardOverviewDto }) {
  return (
    <section aria-labelledby="accounts-title" className={styles.surfaceCard}>
      <SectionHeading
        action={
          <RouterButtonLink icon="accounts" to="/accounts">
            Все счета
          </RouterButtonLink>
        }
        eyebrow={`${dashboard.activeAccountCount} активных`}
        title="Счета и остатки"
        titleId="accounts-title"
      />
      {dashboard.accounts.length === 0 ? (
        <EmptySection
          actionHref="/accounts"
          actionLabel="Добавить счёт"
          icon="accounts"
          text="Добавьте место хранения денег, чтобы увидеть подтверждённый остаток."
        />
      ) : (
        <ul className={styles.accountList}>
          {dashboard.accounts.map((account) => {
            const sign = decimalSign(account.balance);
            return (
              <li key={account.id}>
                <Link
                  className={styles.accountRow}
                  to={`/accounts/${account.id}`}
                >
                  <span className={styles.rowIdentity}>{account.name}</span>
                  <MoneyValue
                    amount={formatMoneyAmount(account.balance, null)}
                    currency={account.currency}
                    size="compact"
                    tone={
                      sign === 1
                        ? "balancePositive"
                        : sign === -1
                          ? "expense"
                          : "neutral"
                    }
                  />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

function RecentDocumentsSection({
  documents,
}: {
  documents: DashboardDocumentDto[];
}) {
  return (
    <section
      aria-labelledby="recent-documents-title"
      className={styles.surfaceCard}
    >
      <SectionHeading
        action={
          <RouterButtonLink icon="imports" to="/imports">
            Все импорты
          </RouterButtonLink>
        }
        eyebrow="Происхождение данных"
        title="Последние документы"
        titleId="recent-documents-title"
      />
      {documents.length === 0 ? (
        <EmptySection
          actionHref="/imports/upload"
          actionLabel="Загрузить выписку"
          icon="imports"
          text="После загрузки здесь появится статус обработки документа."
        />
      ) : (
        <ul className={styles.documentList}>
          {documents.map((document) => (
            <DocumentRow document={document} key={document.id} />
          ))}
        </ul>
      )}
    </section>
  );
}

function DocumentRow({ document }: { document: DashboardDocumentDto }) {
  const status = documentStatuses[document.status];
  return (
    <li>
      <Link className={styles.documentRow} to={documentHref(document)}>
        <span className={styles.documentIdentity}>
          <strong title={document.filename}>{document.filename}</strong>
          <small>
            {document.account?.name ?? "Счёт не указан"} ·{" "}
            {formatUploadDate(document.createdAt)}
          </small>
        </span>
        <span className={styles.documentState}>
          <StatusLabel tone={status.tone} variant="soft">
            {status.label}
          </StatusLabel>
          {document.reviewableRowCount > 0 ? (
            <small>{document.reviewableRowCount} строк ждут</small>
          ) : null}
        </span>
        <Icon className={styles.rowArrow} name="forward" size={18} />
      </Link>
    </li>
  );
}

function OnboardingSection({ dashboard }: { dashboard: DashboardOverviewDto }) {
  const { onboarding } = dashboard;
  const steps = [
    { done: true, href: "/workspaces", label: "Рабочее пространство" },
    { done: onboarding.hasAccounts, href: "/accounts", label: "Добавьте счёт" },
    {
      done: onboarding.hasDocuments,
      href: "/imports/upload",
      label: "Загрузите выписку",
    },
    {
      done: onboarding.hasDocuments && dashboard.attention.total === 0,
      href:
        dashboard.attention.items[0] === undefined
          ? "/imports"
          : documentHref(dashboard.attention.items[0]),
      label: "Проверьте строки",
    },
    {
      done: onboarding.hasConfirmedActivity,
      href: "/reports",
      label: "Откройте отчёт",
    },
  ];
  const currentIndex = steps.findIndex((step) => !step.done);
  return (
    <section
      aria-labelledby="onboarding-title"
      className={styles.onboardingCard}
    >
      <SectionHeading
        eyebrow="Первый цикл учёта"
        title="Первые шаги"
        titleId="onboarding-title"
      />
      <ol className={styles.onboardingList}>
        {steps.map((step, index) => {
          const state = step.done
            ? "done"
            : index === currentIndex
              ? "current"
              : "pending";
          return (
            <li data-state={state} key={step.label}>
              <span className={styles.stepIndex}>
                {step.done ? <Icon name="check" /> : index + 1}
              </span>
              <Link to={step.href}>{step.label}</Link>
              <StatusLabel
                showIcon={false}
                tone={
                  step.done
                    ? "success"
                    : state === "current"
                      ? "warning"
                      : "neutral"
                }
                variant="soft"
              >
                {step.done
                  ? "Готово"
                  : state === "current"
                    ? "Сейчас"
                    : "Позже"}
              </StatusLabel>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function SectionHeading({
  action,
  eyebrow,
  title,
  titleId,
}: {
  action?: React.ReactNode;
  eyebrow: string;
  title: string;
  titleId: string;
}) {
  return (
    <header className={styles.sectionHeading}>
      <div>
        <p className={styles.eyebrow}>{eyebrow}</p>
        <h2 id={titleId}>{title}</h2>
      </div>
      {action}
    </header>
  );
}

function EmptySection({
  actionHref,
  actionLabel,
  icon,
  text,
}: {
  actionHref: string;
  actionLabel: string;
  icon: "accounts" | "imports";
  text: string;
}) {
  return (
    <div className={styles.emptySection}>
      <Icon name={icon} size={24} />
      <p>{text}</p>
      <RouterButtonLink icon={icon} to={actionHref}>
        {actionLabel}
      </RouterButtonLink>
    </div>
  );
}

export function documentHref(document: DashboardDocumentDto): string {
  const suffix =
    document.nextStepKind === "detail" ? "" : `/${document.nextStepKind}`;
  return `/imports/documents/${document.id}${suffix}`;
}

function formatPeriod(start: string, end: string): string {
  const startDate = new Date(`${start}T00:00:00Z`);
  const month = new Intl.DateTimeFormat("ru-RU", {
    month: "long",
    timeZone: "UTC",
    year: "numeric",
  }).format(startDate);
  return `${month} · по ${formatIsoDate(end)}`;
}

function formatUploadDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}
