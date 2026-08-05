import { useRef, useState, type FormEvent } from "react";

import type { SessionDto } from "../../api/session";
import { AppShell } from "../../shell/app-shell";
import { Button } from "../../ui/button/button";
import { Field } from "../../ui/field/field";
import { InlineNotice } from "../../ui/inline-notice/inline-notice";
import { PageFrame } from "../../ui/page-frame/page-frame";
import { PageHeader } from "../../ui/page-header/page-header";
import { bindTelegramDevLink } from "./api/telegram-dev-link-api";
import styles from "./telegram-dev-link-page.module.css";

export function TelegramDevLinkPage({
  initialDisplayName,
  initialExternalUserId,
  navigate = (href) => window.location.assign(href),
  session,
}: {
  initialDisplayName: string;
  initialExternalUserId: string;
  navigate?: (href: string) => void;
  session: SessionDto;
}) {
  const externalUserIdRef = useRef<HTMLInputElement>(null);
  const [externalUserId, setExternalUserId] = useState(initialExternalUserId);
  const [displayName, setDisplayName] = useState(initialDisplayName);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{
    message: string;
    tone: "danger" | "success";
  } | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanExternalUserId = externalUserId.trim();
    if (!cleanExternalUserId) {
      setFieldError("Введите Telegram ID.");
      externalUserIdRef.current?.focus();
      return;
    }
    setPending(true);
    setFieldError(null);
    setNotice(null);
    const result = await bindTelegramDevLink({
      csrfToken: session.csrfToken,
      displayName: displayName.trim(),
      externalUserId: cleanExternalUserId,
    });
    setPending(false);
    if (result.status === "success") {
      setNotice({
        message: "Telegram аккаунт привязан к текущему workspace.",
        tone: "success",
      });
      return;
    }
    if (result.status === "unauthenticated") {
      navigate(
        "/app/auth/login?next=%2Fapp%2Fchat-integrations%2Ftelegram%2Fdev-link",
      );
      return;
    }
    setNotice({
      message:
        result.status === "not_found"
          ? "Dev-link недоступен в этом окружении."
          : result.message,
      tone: "danger",
    });
  }

  return (
    <AppShell session={session}>
      <PageFrame className={styles.content} mobileTop="compact">
        <PageHeader
          description="Локальная привязка Telegram ID к текущему пользователю и workspace."
          eyebrow="Development tool"
          title="Telegram dev-link"
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

          {notice ? (
            <InlineNotice
              role={notice.tone === "danger" ? "alert" : "status"}
              tone={notice.tone}
            >
              {notice.message}
            </InlineNotice>
          ) : null}

          <form
            className={styles.form}
            noValidate
            onSubmit={(event) => void submit(event)}
          >
            <Field
              error={fieldError ?? undefined}
              errorId="telegram-external-user-id-error"
              htmlFor="telegram-external-user-id"
              label="Telegram ID"
              required
            >
              <input
                aria-describedby={
                  fieldError ? "telegram-external-user-id-error" : undefined
                }
                aria-invalid={Boolean(fieldError)}
                disabled={pending}
                id="telegram-external-user-id"
                inputMode="numeric"
                maxLength={128}
                name="externalUserId"
                onChange={(event) => {
                  setExternalUserId(event.target.value);
                  if (fieldError) setFieldError(null);
                }}
                ref={externalUserIdRef}
                required
                value={externalUserId}
              />
            </Field>
            <Field htmlFor="telegram-display-name" label="Имя в Telegram">
              <input
                disabled={pending}
                id="telegram-display-name"
                maxLength={255}
                name="displayName"
                onChange={(event) => setDisplayName(event.target.value)}
                value={displayName}
              />
            </Field>
            <Button isLoading={pending} tone="primary" type="submit">
              {pending ? "Привязываем…" : "Привязать Telegram"}
            </Button>
          </form>
        </section>
      </PageFrame>
    </AppShell>
  );
}
