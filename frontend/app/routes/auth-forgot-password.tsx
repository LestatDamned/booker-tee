import { useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";

import { requestPasswordReset } from "../features/users/api/auth-api";
import styles from "../features/users/auth/auth-page.module.css";
import { Button } from "../ui/button/button";
import { Field } from "../ui/field/field";
import { FormErrorSummary } from "../ui/field/form-error-summary";
import { InlineNotice } from "../ui/inline-notice/inline-notice";

export function meta() {
  return [{ title: "Восстановление пароля — Booker Tee" }];
}

export default function ForgotPasswordRoute() {
  const emailRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) {
      setError("Введите email.");
      emailRef.current?.focus();
      return;
    }
    setPending(true);
    setError(null);
    const result = await requestPasswordReset({ email });
    setPending(false);
    if (result.status === "success") {
      setAccepted(result.message);
      return;
    }
    setError(result.message);
  }

  return (
    <main className={styles.page}>
      <section aria-labelledby="forgot-title" className={styles.card}>
        <a className={styles.brand} href="/">
          Booker Tee
        </a>
        <header className={styles.heading}>
          <h1 id="forgot-title">Восстановить пароль</h1>
          <p>Отправим ссылку на подтверждённый email аккаунта.</p>
        </header>
        {accepted ? (
          <InlineNotice title="Проверьте почту" tone="success">
            {accepted} Ссылка действует 30 минут.
          </InlineNotice>
        ) : (
          <form className={styles.form} noValidate onSubmit={submit}>
            {error ? <FormErrorSummary message={error} /> : null}
            <Field htmlFor="forgot-email" label="Email" required>
              <input
                autoComplete="email"
                disabled={pending}
                id="forgot-email"
                name="email"
                onChange={(event) => setEmail(event.target.value)}
                ref={emailRef}
                required
                type="email"
                value={email}
              />
            </Field>
            <Button isLoading={pending} tone="primary" type="submit">
              {pending ? "Отправляем…" : "Получить ссылку"}
            </Button>
          </form>
        )}
        <p className={styles.footer}>
          <Link to="/auth/login">Вернуться ко входу</Link>
        </p>
      </section>
    </main>
  );
}
