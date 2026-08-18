import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import {
  loadAuthConfig,
  resendEmailVerification,
  signup,
} from "../features/users/api/auth-api";
import styles from "../features/users/auth/auth-page.module.css";
import { Button } from "../ui/button/button";
import { Field } from "../ui/field/field";
import { FormErrorSummary } from "../ui/field/form-error-summary";
import { InlineNotice } from "../ui/inline-notice/inline-notice";
import { PasswordInput } from "../ui/password-input/password-input";
import type { Route } from "./+types/auth-signup";

export function meta() {
  return [{ title: "Регистрация — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadAuthConfig(request.signal);
}

export default function SignupRoute({ loaderData }: Route.ComponentProps) {
  const [searchParams] = useSearchParams();
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [acceptedMessage, setAcceptedMessage] = useState<string | null>(null);
  const [resendStatus, setResendStatus] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const passwordMinLength =
    loaderData.status === "success" ? loaderData.passwordMinLength : 8;

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(
      () => setCooldown((seconds) => Math.max(0, seconds - 1)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [cooldown]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = {
      ...(!email.trim() ? { email: "Введите email." } : {}),
      ...(password.length < passwordMinLength
        ? { password: `Минимум ${passwordMinLength} символов.` }
        : {}),
    };
    setFieldErrors(errors);
    setSubmitError(null);
    if (Object.keys(errors).length > 0) {
      (errors.email ? emailRef : passwordRef).current?.focus();
      return;
    }

    setPending(true);
    const result = await signup({
      email,
      name: name || null,
      password,
      nextPath: searchParams.get("next"),
      invitationToken: searchParams.get("invitation"),
    });
    setPending(false);
    if (result.status === "success") {
      setAcceptedMessage(result.message);
      setCooldown(result.retryAfterSeconds);
      return;
    }
    setFieldErrors(result.fieldErrors);
    setSubmitError(result.message);
    if (result.fieldErrors.email) emailRef.current?.focus();
    else if (result.fieldErrors.password) passwordRef.current?.focus();
  }

  async function resend() {
    if (pending || cooldown > 0) return;
    setPending(true);
    setResendStatus(null);
    const result = await resendEmailVerification({
      email,
      nextPath: searchParams.get("next"),
    });
    setPending(false);
    if (result.status === "success") {
      setResendStatus("Письмо запрошено повторно. Проверьте входящие и спам.");
      setCooldown(result.retryAfterSeconds);
      return;
    }
    setResendStatus(result.message);
    if (result.retryAfterSeconds) setCooldown(result.retryAfterSeconds);
  }

  const invitationToken = searchParams.get("invitation");
  const registrationClosed =
    loaderData.status === "success" &&
    (loaderData.registrationMode === "closed" ||
      (loaderData.registrationMode === "invite_only" && !invitationToken));
  const fullyClosed =
    loaderData.status === "success" && loaderData.registrationMode === "closed";
  return (
    <main className={styles.page}>
      <section aria-labelledby="signup-title" className={styles.card}>
        <a className={styles.brand} href="/">
          Booker Tee
        </a>
        <header className={styles.heading}>
          <h1 id="signup-title">Создать аккаунт</h1>
          <p>Личное пространство будет создано автоматически.</p>
        </header>
        {loaderData.status === "error" ? (
          <InlineNotice title="Не удалось проверить регистрацию" tone="warning">
            {loaderData.message}
          </InlineNotice>
        ) : null}
        {acceptedMessage ? (
          <div className={styles.accepted}>
            <InlineNotice title="Проверьте почту" tone="success">
              {acceptedMessage} Ссылка действует 24 часа.
            </InlineNotice>
            <p>
              Письмо отправлено на <strong>{email}</strong>. Workspace появится
              только после подтверждения адреса.
            </p>
            <div className={styles.actions}>
              <Button
                disabled={cooldown > 0}
                isLoading={pending}
                onClick={resend}
                tone="secondary"
                type="button"
              >
                {cooldown > 0
                  ? `Отправить повторно через ${cooldown} сек.`
                  : "Отправить письмо повторно"}
              </Button>
              <Link to={`/auth/login?${searchParams}`}>Перейти ко входу</Link>
            </div>
            <p aria-live="polite" className={styles.status}>
              {resendStatus}
            </p>
          </div>
        ) : registrationClosed ? (
          <InlineNotice
            title={
              fullyClosed ? "Регистрация закрыта" : "Регистрация по приглашению"
            }
            tone="information"
          >
            {fullyClosed
              ? "Новые аккаунты временно не создаются."
              : "Новые аккаунты создаются только по действующей ссылке-приглашению."}{" "}
            Если аккаунт уже есть, войдите.
          </InlineNotice>
        ) : (
          <form className={styles.form} noValidate onSubmit={submit}>
            {submitError || Object.keys(fieldErrors).length > 0 ? (
              <FormErrorSummary
                message={submitError ?? "Проверьте поля и повторите."}
              />
            ) : null}
            <Field
              htmlFor="signup-name"
              label="Имя"
              hint="Можно добавить позже."
            >
              <input
                autoComplete="name"
                disabled={pending}
                id="signup-name"
                maxLength={255}
                name="name"
                onChange={(event) => setName(event.target.value)}
                value={name}
              />
            </Field>
            <Field
              error={fieldErrors.email}
              errorId="signup-email-error"
              htmlFor="signup-email"
              label="Email"
              required
            >
              <input
                aria-describedby={
                  fieldErrors.email ? "signup-email-error" : undefined
                }
                aria-invalid={Boolean(fieldErrors.email)}
                autoComplete="email"
                disabled={pending}
                id="signup-email"
                name="email"
                onChange={(event) => {
                  setEmail(event.target.value);
                  if (fieldErrors.email)
                    setFieldErrors((current) => ({ ...current, email: "" }));
                }}
                ref={emailRef}
                required
                type="email"
                value={email}
              />
            </Field>
            <Field
              error={fieldErrors.password}
              errorId="signup-password-error"
              hint={`Не менее ${passwordMinLength} символов. Можно вставить из password manager.`}
              htmlFor="signup-password"
              label="Пароль"
              required
            >
              <PasswordInput
                aria-describedby={
                  fieldErrors.password
                    ? "signup-password-error"
                    : "signup-password-hint"
                }
                aria-invalid={Boolean(fieldErrors.password)}
                autoComplete="new-password"
                disabled={pending}
                id="signup-password"
                minLength={passwordMinLength}
                name="password"
                onChange={(event) => {
                  setPassword(event.target.value);
                  if (fieldErrors.password)
                    setFieldErrors((current) => ({ ...current, password: "" }));
                }}
                ref={passwordRef}
                required
                value={password}
              />
            </Field>
            <Button isLoading={pending} tone="primary" type="submit">
              {pending ? "Создаём…" : "Создать аккаунт"}
            </Button>
          </form>
        )}
        {!acceptedMessage ? (
          <p className={styles.footer}>
            Уже есть аккаунт?{" "}
            <Link to={`/auth/login?${searchParams}`}>Войти</Link>
          </p>
        ) : null}
      </section>
    </main>
  );
}
