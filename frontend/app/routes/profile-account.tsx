import { useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { loadSession } from "../api/session";
import {
  confirmEmailChange,
  deactivateAccount,
  loadAccount,
  loadDeactivationImpact,
  requestEmailChange,
  type DeactivationImpactDto,
} from "../features/users/api/account-api";
import styles from "../features/users/profile/profile-page.module.css";
import { AppShell } from "../shell/app-shell";
import { useSecretFragment } from "../shared/secret-fragment";
import { AuthenticatedRouteStatePage } from "../session/authenticated-route-state-page";
import { Button } from "../ui/button/button";
import { ConfirmationDialog } from "../ui/confirmation-dialog/confirmation-dialog";
import { Field } from "../ui/field/field";
import { FormErrorSummary } from "../ui/field/form-error-summary";
import { FormActions } from "../ui/field/form-layout";
import { InlineNotice } from "../ui/inline-notice/inline-notice";
import { PageFrame } from "../ui/page-frame/page-frame";
import { PageHeader } from "../ui/page-header/page-header";
import { PasswordInput } from "../ui/password-input/password-input";
import { WorkbenchSurface } from "../ui/workbench-surface/workbench-surface";
import type { Route } from "./+types/profile-account";

export function meta() {
  return [{ title: "Управление аккаунтом — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const [session, account, impact] = await Promise.all([
    loadSession(request.signal),
    loadAccount(request.signal),
    loadDeactivationImpact(request.signal),
  ]);
  return { session, account, impact };
}

export default function ProfileAccountRoute({
  loaderData,
}: Route.ComponentProps) {
  const { session, account, impact } = loaderData;
  if (session.status === "loading")
    return <RouteError message="Сессия ещё не загружена." />;
  if (session.status !== "authenticated") {
    return (
      <AuthenticatedRouteStatePage
        errorTitle="Не удалось открыть управление аккаунтом"
        result={session}
        returnTo="/app/profile/account"
      />
    );
  }
  if (account.status !== "success" || impact.status !== "success") {
    return (
      <RouteError
        message={
          account.status === "error"
            ? account.message
            : impact.status === "error"
              ? impact.message
              : "Данные аккаунта не загружены."
        }
      />
    );
  }
  return (
    <AppShell session={session.session}>
      <AccountPage
        csrfToken={session.session.csrfToken}
        currentEmail={account.account.email}
        impact={impact.impact}
      />
    </AppShell>
  );
}

export function AccountPage({
  csrfToken,
  currentEmail,
  impact,
}: {
  csrfToken: string;
  currentEmail: string;
  impact: DeactivationImpactDto;
}) {
  const [searchParams] = useSearchParams();
  const fragment = useSecretFragment();
  const [confirmationToken] = useState(() => fragment.get("token"));
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [targetEmail, setTargetEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [deactivationOpen, setDeactivationOpen] = useState(false);
  const [deactivationPassword, setDeactivationPassword] = useState("");
  const [deactivationConfirmation, setDeactivationConfirmation] = useState("");
  const [deactivationErrors, setDeactivationErrors] = useState<
    Record<string, string>
  >({});

  async function submitEmail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = {
      ...(!targetEmail ? { targetEmail: "Введите новый email." } : {}),
      ...(!currentPassword
        ? { currentPassword: "Введите текущий пароль." }
        : {}),
    };
    setErrors(nextErrors);
    setMessage(null);
    if (Object.keys(nextErrors).length) {
      (nextErrors.targetEmail ? emailRef : passwordRef).current?.focus();
      return;
    }
    setPending(true);
    const result = await requestEmailChange(
      targetEmail,
      currentPassword,
      csrfToken,
    );
    setPending(false);
    if (result.status === "unauthenticated") return redirectToLogin();
    if (result.status === "error") {
      setErrors(result.fieldErrors);
      setMessage(result.message);
      return;
    }
    setCurrentPassword("");
    setMessage(result.message);
  }

  async function confirmEmail() {
    if (!confirmationToken) return;
    setPending(true);
    setMessage(null);
    const result = await confirmEmailChange(confirmationToken, csrfToken);
    if (result.status === "unauthenticated") return redirectToLogin();
    if (result.status === "success") {
      window.location.assign("/app/profile/account?emailChanged=1");
      return;
    }
    setPending(false);
    setMessage(result.message);
  }

  async function confirmDeactivation() {
    const nextErrors = {
      ...(!deactivationPassword
        ? { currentPassword: "Введите текущий пароль." }
        : {}),
      ...(deactivationConfirmation !== "ДЕАКТИВИРОВАТЬ"
        ? { confirmation: "Введите ДЕАКТИВИРОВАТЬ без изменений." }
        : {}),
    };
    setDeactivationErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    setPending(true);
    const result = await deactivateAccount(
      deactivationPassword,
      deactivationConfirmation,
      csrfToken,
    );
    if (result.status === "unauthenticated" || result.status === "success") {
      window.location.assign("/app/auth/login?deactivated=1");
      return;
    }
    setPending(false);
    setDeactivationErrors(result.fieldErrors);
    setMessage(result.message);
    setDeactivationOpen(false);
  }

  return (
    <PageFrame aria-labelledby="account-title">
      <div className={styles.content}>
        <Link to="/profile">← Профиль</Link>
        <PageHeader
          description="Изменение адреса для входа и безопасная деактивация аккаунта."
          eyebrow="Аккаунт"
          title="Управление аккаунтом"
          titleId="account-title"
        />
        {message ? (
          <InlineNotice
            aria-live="polite"
            tone={Object.keys(errors).length ? "danger" : "success"}
          >
            {message}
          </InlineNotice>
        ) : null}
        {searchParams.get("emailChanged") === "1" ? (
          <InlineNotice tone="success">
            Email изменён. Остальные сессии завершены.
          </InlineNotice>
        ) : null}
        <WorkbenchSurface>
          {confirmationToken ? (
            <section className={styles.form}>
              <div className={styles.sectionHeading}>
                <h2>Подтвердить новый email</h2>
                <p>Изменение завершит остальные активные сессии.</p>
              </div>
              <FormActions>
                <Button
                  isLoading={pending}
                  onClick={confirmEmail}
                  tone="primary"
                >
                  Подтвердить изменение
                </Button>
              </FormActions>
            </section>
          ) : (
            <form className={styles.form} noValidate onSubmit={submitEmail}>
              <div className={styles.sectionHeading}>
                <h2>Изменить email</h2>
                <p>
                  Сейчас вы входите как {currentEmail}. Новый адрес нужно
                  подтвердить письмом.
                </p>
              </div>
              {Object.keys(errors).length ? (
                <FormErrorSummary message="Проверьте поля." />
              ) : null}
              <Field
                error={errors.targetEmail}
                errorId="target-email-error"
                htmlFor="target-email"
                label="Новый email"
                required
              >
                <input
                  aria-invalid={Boolean(errors.targetEmail)}
                  autoComplete="email"
                  disabled={pending}
                  id="target-email"
                  onChange={(event) => setTargetEmail(event.target.value)}
                  ref={emailRef}
                  type="email"
                  value={targetEmail}
                />
              </Field>
              <Field
                error={errors.currentPassword}
                errorId="email-password-error"
                htmlFor="email-password"
                label="Текущий пароль"
                required
              >
                <PasswordInput
                  aria-invalid={Boolean(errors.currentPassword)}
                  autoComplete="current-password"
                  disabled={pending}
                  id="email-password"
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  ref={passwordRef}
                  value={currentPassword}
                />
              </Field>
              <FormActions>
                <Button isLoading={pending} tone="primary" type="submit">
                  Отправить подтверждение
                </Button>
              </FormActions>
            </form>
          )}
          <section className={styles.dangerZone}>
            <div className={styles.sectionHeading}>
              <h2>Деактивировать аккаунт</h2>
              <p>
                Финансовые записи сохранятся, доступ и все сессии будут
                отключены. Самостоятельного восстановления нет.
              </p>
            </div>
            {impact.blockers.length ? (
              <InlineNotice tone="warning">
                Сначала передайте владение или отдельно деактивируйте общие
                пространства.
              </InlineNotice>
            ) : null}
            <ul
              aria-label="Препятствия для деактивации"
              className={styles.blockers}
            >
              {impact.blockers.map((blocker) => (
                <li className={styles.blocker} key={blocker.workspaceId}>
                  <strong>{blocker.workspaceName}</strong>
                  <p>
                    Других активных участников: {blocker.activeOtherMemberCount}
                  </p>
                  <Link to={`/workspaces/${blocker.workspaceId}/settings`}>
                    Управлять владельцем и состоянием
                  </Link>
                </li>
              ))}
            </ul>
            {impact.autoDeactivatedWorkspaceCount ? (
              <p>
                Личных пространств будет деактивировано:{" "}
                {impact.autoDeactivatedWorkspaceCount}.
              </p>
            ) : null}
            <FormActions>
              <Button
                disabled={!impact.canDeactivate}
                onClick={() => setDeactivationOpen(true)}
                tone="danger"
              >
                Деактивировать аккаунт
              </Button>
            </FormActions>
          </section>
        </WorkbenchSurface>
      </div>
      {deactivationOpen ? (
        <ConfirmationDialog
          confirmLabel="Деактивировать"
          description="Доступ будет немедленно закрыт на всех устройствах. Финансовые данные не удаляются."
          onCancel={() => setDeactivationOpen(false)}
          onConfirm={confirmDeactivation}
          pending={pending}
          title="Деактивировать аккаунт?"
        >
          {Object.keys(deactivationErrors).length ? (
            <FormErrorSummary message="Проверьте подтверждение." />
          ) : null}
          <Field
            error={deactivationErrors.currentPassword}
            htmlFor="deactivation-password"
            label="Текущий пароль"
            required
          >
            <PasswordInput
              autoComplete="current-password"
              id="deactivation-password"
              onChange={(event) => setDeactivationPassword(event.target.value)}
              value={deactivationPassword}
            />
          </Field>
          <Field
            error={deactivationErrors.confirmation}
            hint="Введите ДЕАКТИВИРОВАТЬ"
            htmlFor="deactivation-confirmation"
            label="Контрольная фраза"
            required
          >
            <input
              autoComplete="off"
              id="deactivation-confirmation"
              onChange={(event) =>
                setDeactivationConfirmation(event.target.value)
              }
              value={deactivationConfirmation}
            />
          </Field>
        </ConfirmationDialog>
      ) : null}
    </PageFrame>
  );
}

function redirectToLogin() {
  window.location.assign("/app/auth/login?next=%2Fapp%2Fprofile%2Faccount");
}

function RouteError({ message }: { message: string }) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось открыть управление аккаунтом"
      result={{ status: "error", message }}
      returnTo="/app/profile/account"
    />
  );
}
