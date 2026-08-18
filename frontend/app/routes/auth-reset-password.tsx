import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";

import { loadAuthConfig, resetPassword } from "../features/users/api/auth-api";
import styles from "../features/users/auth/auth-page.module.css";
import { useSecretFragment } from "../shared/secret-fragment";
import { Button } from "../ui/button/button";
import { Field } from "../ui/field/field";
import { FormErrorSummary } from "../ui/field/form-error-summary";
import { InlineNotice } from "../ui/inline-notice/inline-notice";
import { PasswordInput } from "../ui/password-input/password-input";
import type { Route } from "./+types/auth-reset-password";

export function meta() {
  return [{ title: "Новый пароль — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadAuthConfig(request.signal);
}

export default function ResetPasswordRoute({
  loaderData,
}: Route.ComponentProps) {
  const fragment = useSecretFragment();
  const [token] = useState(() => fragment.get("token"));
  const minimum =
    loaderData.status === "success" ? loaderData.passwordMinLength : 8;
  const passwordRef = useRef<HTMLInputElement>(null);
  const confirmationRef = useRef<HTMLInputElement>(null);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const nextErrors = {
      ...(password.length < minimum
        ? { newPassword: `Минимум ${minimum} символов.` }
        : {}),
      ...(password !== confirmation
        ? { confirmation: "Пароли не совпадают." }
        : {}),
    };
    setErrors(nextErrors);
    setMessage(null);
    if (Object.keys(nextErrors).length > 0) {
      (nextErrors.newPassword ? passwordRef : confirmationRef).current?.focus();
      return;
    }
    setPending(true);
    const result = await resetPassword({ token, newPassword: password });
    setPending(false);
    if (result.status === "success") {
      window.location.assign("/app/auth/login?passwordReset=1");
      return;
    }
    setErrors(result.fieldErrors);
    setMessage(result.message);
    if (result.fieldErrors.newPassword) passwordRef.current?.focus();
  }

  return (
    <main className={styles.page}>
      <section aria-labelledby="reset-title" className={styles.card}>
        <a className={styles.brand} href="/">
          Booker Tee
        </a>
        <header className={styles.heading}>
          <h1 id="reset-title">Задать новый пароль</h1>
          <p>После изменения все прежние сессии будут завершены.</p>
        </header>
        {!token ? (
          <InlineNotice title="Нужна новая ссылка" tone="warning">
            Ссылка отсутствует или уже была открыта без token. Запросите новую.
          </InlineNotice>
        ) : (
          <form className={styles.form} noValidate onSubmit={submit}>
            {message || Object.keys(errors).length > 0 ? (
              <FormErrorSummary message={message ?? "Проверьте поля."} />
            ) : null}
            <Field
              error={errors.newPassword}
              errorId="reset-password-error"
              hint={`Не менее ${minimum} символов. Разрешены пробелы и вставка из password manager.`}
              htmlFor="reset-password"
              label="Новый пароль"
              required
            >
              <PasswordInput
                aria-describedby={
                  errors.newPassword
                    ? "reset-password-error"
                    : "reset-password-hint"
                }
                aria-invalid={Boolean(errors.newPassword)}
                autoComplete="new-password"
                disabled={pending}
                id="reset-password"
                minLength={minimum}
                name="newPassword"
                onChange={(event) => setPassword(event.target.value)}
                ref={passwordRef}
                required
                value={password}
              />
            </Field>
            <Field
              error={errors.confirmation}
              errorId="reset-confirmation-error"
              htmlFor="reset-confirmation"
              label="Повторите пароль"
              required
            >
              <PasswordInput
                aria-describedby={
                  errors.confirmation ? "reset-confirmation-error" : undefined
                }
                aria-invalid={Boolean(errors.confirmation)}
                autoComplete="new-password"
                disabled={pending}
                id="reset-confirmation"
                name="confirmation"
                onChange={(event) => setConfirmation(event.target.value)}
                ref={confirmationRef}
                required
                value={confirmation}
              />
            </Field>
            <Button isLoading={pending} tone="primary" type="submit">
              {pending ? "Меняем…" : "Изменить пароль"}
            </Button>
          </form>
        )}
        <p className={styles.footer}>
          <Link to="/auth/forgot-password">Запросить новую ссылку</Link>
        </p>
      </section>
    </main>
  );
}
