import { useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { loadSession } from "../api/session";
import { changePassword } from "../features/users/api/account-api";
import { loadAuthConfig } from "../features/users/api/auth-api";
import styles from "../features/users/profile/profile-page.module.css";
import { AppShell } from "../shell/app-shell";
import { AuthenticatedRouteStatePage } from "../session/authenticated-route-state-page";
import { Button } from "../ui/button/button";
import { Field } from "../ui/field/field";
import { FormErrorSummary } from "../ui/field/form-error-summary";
import { FormActions } from "../ui/field/form-layout";
import { InlineNotice } from "../ui/inline-notice/inline-notice";
import { PageFrame } from "../ui/page-frame/page-frame";
import { PageHeader } from "../ui/page-header/page-header";
import { PasswordInput } from "../ui/password-input/password-input";
import { WorkbenchSurface } from "../ui/workbench-surface/workbench-surface";
import type { Route } from "./+types/profile-security";

export function meta() {
  return [{ title: "Безопасность профиля — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const [session, config] = await Promise.all([
    loadSession(request.signal),
    loadAuthConfig(request.signal),
  ]);
  return { session, config };
}

export default function ProfileSecurityRoute({
  loaderData,
}: Route.ComponentProps) {
  if (loaderData.session.status === "loading") {
    return (
      <AuthenticatedRouteStatePage
        errorTitle="Не удалось открыть безопасность профиля"
        result={{ status: "error", message: "Сессия ещё не загружена." }}
        returnTo="/app/profile/security"
      />
    );
  }
  if (loaderData.session.status !== "authenticated") {
    return (
      <AuthenticatedRouteStatePage
        errorTitle="Не удалось открыть безопасность профиля"
        result={loaderData.session}
        returnTo="/app/profile/security"
      />
    );
  }
  const minimum =
    loaderData.config.status === "success"
      ? loaderData.config.passwordMinLength
      : 8;
  return (
    <AppShell session={loaderData.session.session}>
      <SecurityPage
        csrfToken={loaderData.session.session.csrfToken}
        minimum={minimum}
      />
    </AppShell>
  );
}

function SecurityPage({
  csrfToken,
  minimum,
}: {
  csrfToken: string;
  minimum: number;
}) {
  const [searchParams] = useSearchParams();
  const currentRef = useRef<HTMLInputElement>(null);
  const nextRef = useRef<HTMLInputElement>(null);
  const confirmationRef = useRef<HTMLInputElement>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors = {
      ...(!currentPassword
        ? { currentPassword: "Введите текущий пароль." }
        : {}),
      ...(newPassword.length < minimum
        ? { newPassword: `Минимум ${minimum} символов.` }
        : {}),
      ...(newPassword !== confirmation
        ? { confirmation: "Пароли не совпадают." }
        : {}),
    };
    setErrors(nextErrors);
    setMessage(null);
    if (Object.keys(nextErrors).length > 0) {
      (nextErrors.currentPassword
        ? currentRef
        : nextErrors.newPassword
          ? nextRef
          : confirmationRef
      ).current?.focus();
      return;
    }
    setPending(true);
    const result = await changePassword(
      currentPassword,
      newPassword,
      csrfToken,
    );
    setPending(false);
    if (result.status === "unauthenticated") {
      window.location.assign(
        "/app/auth/login?next=%2Fapp%2Fprofile%2Fsecurity",
      );
      return;
    }
    if (result.status === "success") {
      window.location.assign("/app/profile/security?changed=1");
      return;
    }
    setErrors(result.fieldErrors);
    setMessage(result.message);
    if (result.fieldErrors.currentPassword) currentRef.current?.focus();
    else if (result.fieldErrors.newPassword) nextRef.current?.focus();
  }

  return (
    <PageFrame aria-labelledby="security-title">
      <div className={styles.content}>
        <Link to="/profile">← Профиль</Link>
        <PageHeader
          description="Изменение пароля завершит остальные активные сессии."
          eyebrow="Аккаунт"
          title="Безопасность"
          titleId="security-title"
        />
        <WorkbenchSurface>
          <form className={styles.form} noValidate onSubmit={submit}>
            <div className={styles.sectionHeading}>
              <h2>Изменить пароль</h2>
              <p>Используйте длинную уникальную фразу или password manager.</p>
            </div>
            {searchParams.get("changed") === "1" ? (
              <InlineNotice tone="success">
                Пароль изменён. Остальные сессии завершены.
              </InlineNotice>
            ) : null}
            {message || Object.keys(errors).length > 0 ? (
              <FormErrorSummary message={message ?? "Проверьте поля."} />
            ) : null}
            <Field
              error={errors.currentPassword}
              errorId="current-password-error"
              htmlFor="current-password"
              label="Текущий пароль"
              required
            >
              <PasswordInput
                aria-describedby={
                  errors.currentPassword ? "current-password-error" : undefined
                }
                aria-invalid={Boolean(errors.currentPassword)}
                autoComplete="current-password"
                disabled={pending}
                id="current-password"
                name="currentPassword"
                onChange={(event) => setCurrentPassword(event.target.value)}
                ref={currentRef}
                required
                value={currentPassword}
              />
            </Field>
            <Field
              error={errors.newPassword}
              errorId="new-password-error"
              hint={`Не менее ${minimum} символов. Без обязательных цифр и спецсимволов.`}
              htmlFor="new-password"
              label="Новый пароль"
              required
            >
              <PasswordInput
                aria-describedby={
                  errors.newPassword
                    ? "new-password-error"
                    : "new-password-hint"
                }
                aria-invalid={Boolean(errors.newPassword)}
                autoComplete="new-password"
                disabled={pending}
                id="new-password"
                minLength={minimum}
                name="newPassword"
                onChange={(event) => setNewPassword(event.target.value)}
                ref={nextRef}
                required
                value={newPassword}
              />
            </Field>
            <Field
              error={errors.confirmation}
              errorId="password-confirmation-error"
              htmlFor="password-confirmation"
              label="Повторите новый пароль"
              required
            >
              <PasswordInput
                aria-describedby={
                  errors.confirmation
                    ? "password-confirmation-error"
                    : undefined
                }
                aria-invalid={Boolean(errors.confirmation)}
                autoComplete="new-password"
                disabled={pending}
                id="password-confirmation"
                name="confirmation"
                onChange={(event) => setConfirmation(event.target.value)}
                ref={confirmationRef}
                required
                value={confirmation}
              />
            </Field>
            <FormActions>
              <Button isLoading={pending} tone="primary" type="submit">
                {pending ? "Меняем…" : "Изменить пароль"}
              </Button>
            </FormActions>
          </form>
        </WorkbenchSurface>
      </div>
    </PageFrame>
  );
}
