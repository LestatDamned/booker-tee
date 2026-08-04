import { useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import { login } from "../features/users/api/auth-api";
import styles from "../features/users/auth/auth-page.module.css";
import { Button } from "../ui/button/button";
import { Field } from "../ui/field/field";
import {
  FormErrorSummary,
  type FormErrorSummaryItem,
} from "../ui/field/form-error-summary";
import { InlineNotice } from "../ui/inline-notice/inline-notice";
import { PasswordInput } from "../ui/password-input/password-input";

export function meta() {
  return [{ title: "Вход — Booker Tee" }];
}

export default function LoginRoute() {
  const [searchParams] = useSearchParams();
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const errors = validateLogin(email, password);
    setFieldErrors(errors);
    setSubmitError(null);
    if (Object.keys(errors).length > 0) {
      focusFirstError(errors, emailRef.current, passwordRef.current);
      return;
    }

    setPending(true);
    const result = await login({
      email,
      password,
      nextPath: searchParams.get("next"),
    });
    setPending(false);
    if (result.status === "success") {
      window.location.assign(result.nextPath);
      return;
    }
    setFieldErrors(result.fieldErrors);
    setSubmitError(result.message);
    focusFirstError(result.fieldErrors, emailRef.current, passwordRef.current);
  }

  const summaryErrors = loginSummaryErrors(fieldErrors);
  return (
    <main className={styles.page}>
      <section aria-labelledby="login-title" className={styles.card}>
        <a className={styles.brand} href="/">
          Booker Tee
        </a>
        <header className={styles.heading}>
          <h1 id="login-title">Вход</h1>
          <p>Вернитесь к своим финансовым данным.</p>
        </header>
        {searchParams.get("passwordReset") === "1" ? (
          <InlineNotice tone="success">
            Пароль изменён. Войдите с новым паролем.
          </InlineNotice>
        ) : null}
        <form className={styles.form} noValidate onSubmit={submit}>
          {submitError || summaryErrors.length > 0 ? (
            <FormErrorSummary
              errors={summaryErrors}
              headingLevel={3}
              message={submitError ?? "Проверьте поля и повторите вход."}
            />
          ) : null}
          <Field
            error={fieldErrors.email}
            errorId="login-email-error"
            htmlFor="login-email"
            label="Email"
            required
          >
            <input
              aria-describedby={
                fieldErrors.email ? "login-email-error" : undefined
              }
              aria-invalid={Boolean(fieldErrors.email)}
              autoComplete="email"
              disabled={pending}
              id="login-email"
              name="email"
              onBlur={() =>
                setFieldErrors((current) => ({
                  ...current,
                  ...(!email.trim() ? { email: "Введите email." } : {}),
                }))
              }
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
            errorId="login-password-error"
            htmlFor="login-password"
            label="Пароль"
            required
          >
            <PasswordInput
              aria-describedby={
                fieldErrors.password ? "login-password-error" : undefined
              }
              aria-invalid={Boolean(fieldErrors.password)}
              autoComplete="current-password"
              disabled={pending}
              id="login-password"
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
            {pending ? "Входим…" : "Войти"}
          </Button>
        </form>
        <p className={styles.footer}>
          <Link to="/auth/forgot-password">Забыли пароль?</Link>
        </p>
        <p className={styles.footer}>
          Нет аккаунта? <Link to={`/auth/signup?${searchParams}`}>Создать</Link>
        </p>
      </section>
    </main>
  );
}

function validateLogin(email: string, password: string) {
  return {
    ...(!email.trim() ? { email: "Введите email." } : {}),
    ...(!password ? { password: "Введите пароль." } : {}),
  };
}

function focusFirstError(
  errors: Record<string, string>,
  email: HTMLInputElement | null,
  password: HTMLInputElement | null,
) {
  if (errors.email) email?.focus();
  else if (errors.password) password?.focus();
}

function loginSummaryErrors(
  errors: Record<string, string>,
): FormErrorSummaryItem[] {
  return [
    ...(errors.email
      ? [{ fieldId: "login-email", label: "Email", message: errors.email }]
      : []),
    ...(errors.password
      ? [
          {
            fieldId: "login-password",
            label: "Пароль",
            message: errors.password,
          },
        ]
      : []),
  ];
}
