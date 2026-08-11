import { Link } from "react-router";

import type { SessionDto } from "../../api/session";
import { formatIsoDate } from "../../shared/date/format-date";
import {
  decimalSign,
  formatMoneyAmount,
} from "../../shared/money/format-money";
import { AppShell } from "../../shell/app-shell";
import { RouterButtonLink } from "../../ui/button/button";
import { Icon, type IconName } from "../../ui/icon/icon";
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
              <PrimaryAction
                action={dashboard.capabilities.primaryAction}
                period={dashboard.period}
              />
            }
            title="Обзор"
            titleId="dashboard-title"
          />

          <AttentionStatus attention={dashboard.attention} />

          {dashboard.attention.total === 0 &&
          !dashboard.onboarding.isComplete ? (
            <NextStep dashboard={dashboard} />
          ) : null}

          <div className={styles.primaryGrid}>
            <MoneySummary
              currentPeriod={dashboard.currentPeriod}
              period={dashboard.period}
              summary={dashboard.summary}
            />
            <AccountsSection dashboard={dashboard} />
          </div>

          <LatestDocumentSection document={dashboard.recentDocuments[0]} />
        </div>
      </PageFrame>
    </AppShell>
  );
}

function PrimaryAction({
  action,
  period,
}: {
  action: DashboardOverviewDto["capabilities"]["primaryAction"];
  period: DashboardOverviewDto["period"];
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
      <RouterButtonLink icon="plus" to="/operations" tone="primary">
        Добавить операцию
      </RouterButtonLink>
    );
  }
  return (
    <RouterButtonLink icon="reports" to={reportHref(period)} tone="primary">
      Открыть отчёт
    </RouterButtonLink>
  );
}

function AttentionStatus({
  attention,
}: {
  attention: DashboardOverviewDto["attention"];
}) {
  if (attention.total === 0) {
    return (
      <div className={styles.statusStrip} data-tone="success" role="status">
        <Icon name="check" size={20} weight="fill" />
        <strong>Нет открытых импортов на проверке</strong>
      </div>
    );
  }
  const firstDocument = attention.items[0];
  return (
    <section
      aria-labelledby="attention-title"
      className={styles.attentionStrip}
    >
      <Icon name="warning" size={22} weight="fill" />
      <div>
        <h2 id="attention-title">Требует внимания</h2>
        <p>Документов в очереди: {attention.total}</p>
      </div>
      <RouterButtonLink
        icon="imports"
        to={
          attention.total === 1 && firstDocument
            ? documentHref(firstDocument)
            : "/imports?state=attention"
        }
      >
        Проверить
      </RouterButtonLink>
    </section>
  );
}

function MoneySummary({
  currentPeriod,
  period,
  summary,
}: {
  currentPeriod: DashboardOverviewDto["currentPeriod"];
  period: DashboardOverviewDto["period"];
  summary: DashboardOverviewDto["summary"];
}) {
  const resultSign = decimalSign(summary.profit);
  return (
    <section aria-labelledby="month-result-title" className={styles.moneyCard}>
      <SectionHeading
        action={
          <RouterButtonLink icon="reports" to={reportHref(period)}>
            Открыть отчёт
          </RouterButtonLink>
        }
        eyebrow={`${formatMonth(period.start)} · полный месяц`}
        title="Финансовый итог"
        titleId="month-result-title"
      />
      <div className={styles.resultValue}>
        <span>Результат</span>
        <MoneyValue
          amount={formatMoneyAmount(
            summary.profit,
            resultSign === 1 ? "income" : resultSign === -1 ? "expense" : null,
          )}
          currency={summary.currency}
          size="prominent"
          tone={resultSign === -1 ? "expense" : "profit"}
        />
      </div>
      <div className={styles.moneyFacts}>
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
      </div>
      <footer className={styles.moneyFooter}>
        <span>Подтверждённые операции · без внутренних переводов</span>
        <Link className={styles.textLink} to={reportHref(currentPeriod)}>
          {formatMonth(currentPeriod.start)} на сегодня
        </Link>
      </footer>
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
    <div className={styles.moneyMetric}>
      <span>{label}</span>
      <MoneyValue
        amount={amount}
        currency={currency}
        size="compact"
        tone={tone}
      />
    </div>
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

function LatestDocumentSection({
  document,
}: {
  document: DashboardDocumentDto | undefined;
}) {
  if (!document) return null;
  const status = documentStatuses[document.status];
  return (
    <section
      aria-labelledby="latest-document-title"
      className={styles.latestDocument}
    >
      <Icon name="source" size={22} />
      <div className={styles.latestDocumentIdentity}>
        <p className={styles.eyebrow} id="latest-document-title">
          Последний импорт
        </p>
        <Link to={documentHref(document)}>{document.filename}</Link>
        <small>
          {document.account?.name ?? "Счёт не указан"} ·{" "}
          {formatUploadDate(document.createdAt)}
          {document.statementPeriodEnd
            ? ` · выписка по ${formatIsoDate(document.statementPeriodEnd)}`
            : null}
        </small>
      </div>
      <StatusLabel tone={status.tone} variant="soft">
        {status.label}
      </StatusLabel>
      <RouterButtonLink icon="imports" to="/imports">
        Все импорты
      </RouterButtonLink>
    </section>
  );
}

function NextStep({ dashboard }: { dashboard: DashboardOverviewDto }) {
  const step = nextStep(dashboard);
  if (!step) return null;
  return (
    <section aria-labelledby="next-step-title" className={styles.nextStep}>
      <Icon name={step.icon} size={22} />
      <div>
        <p className={styles.eyebrow}>Следующий шаг</p>
        <h2 id="next-step-title">{step.title}</h2>
      </div>
      <RouterButtonLink icon={step.icon} to={step.href}>
        {step.action}
      </RouterButtonLink>
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

function nextStep(
  dashboard: DashboardOverviewDto,
): { action: string; href: string; icon: IconName; title: string } | null {
  if (
    !dashboard.onboarding.hasAccounts &&
    dashboard.capabilities.canWriteFinancialData
  ) {
    return {
      action: "Добавить счёт",
      href: "/accounts",
      icon: "accounts",
      title: "Добавьте первый счёт",
    };
  }
  if (!dashboard.onboarding.hasDocuments && dashboard.capabilities.canUpload) {
    return {
      action: "Загрузить",
      href: "/imports/upload",
      icon: "imports",
      title: "Загрузите первую выписку",
    };
  }
  if (
    !dashboard.onboarding.hasConfirmedActivity &&
    dashboard.capabilities.canWriteFinancialData
  ) {
    const document = dashboard.recentDocuments[0];
    return {
      action: "Продолжить",
      href: document ? documentHref(document) : "/operations",
      icon: document ? "imports" : "plus",
      title: "Подтвердите первые операции",
    };
  }
  return null;
}

function reportHref(period: DashboardOverviewDto["period"]): string {
  const search = new URLSearchParams({
    date_from: period.start,
    date_to: period.end,
  });
  return `/reports?${search.toString()}`;
}

function formatMonth(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    month: "long",
    timeZone: "UTC",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00Z`));
}

function formatUploadDate(value: string): string {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}
