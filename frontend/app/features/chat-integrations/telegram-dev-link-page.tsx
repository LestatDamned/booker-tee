import { useState } from "react";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { Button } from "../../ui/button/button";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import {
  issueTelegramLinkCode,
  type TelegramLinkCode,
} from "./api/telegram-dev-link-api";
import styles from "./telegram-dev-link-page.module.css";

export function TelegramDevLinkPage({ session }: { session: SessionDto }) {
  const [linkCode, setLinkCode] = useState<TelegramLinkCode | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function issueCode() {
    setPending(true);
    setError(null);
    const result = await issueTelegramLinkCode(session.csrfToken);
    setPending(false);
    if (result.status === "success") {
      setLinkCode(result.linkCode);
      return;
    }
    setError(
      result.status === "unauthenticated"
        ? "Сессия истекла. Войди снова."
        : result.message,
    );
  }

  return (
    <AppShell session={session}>
      <PageFrame className={styles.content} mobileTop="compact">
        <PageHeader
          description="Создай одноразовый код и отправь его боту в личном чате."
          eyebrow="Telegram"
          title="Подключить Telegram"
        />
        <section aria-label="Привязка Telegram" className={styles.surface}>
          <dl className={styles.context}>
            <div>
              <dt>Workspace</dt>
              <dd>{session.workspace.name}</dd>
            </div>
            <div>
              <dt>Пользователь</dt>
              <dd>{session.user.email}</dd>
            </div>
          </dl>

          {error ? (
            <InlineNotice role="alert" tone="danger">
              {error}
            </InlineNotice>
          ) : null}

          {linkCode ? (
            <InlineNotice role="status" tone="success">
              Отправь боту команду в течение 10 минут:
              <code className={styles.code}>{linkCode.command}</code>
            </InlineNotice>
          ) : null}

          <Button
            isLoading={pending}
            onClick={() => void issueCode()}
            tone="primary"
            type="button"
          >
            {pending
              ? "Создаём…"
              : linkCode
                ? "Создать новый код"
                : "Получить код"}
          </Button>
        </section>
      </PageFrame>
    </AppShell>
  );
}
