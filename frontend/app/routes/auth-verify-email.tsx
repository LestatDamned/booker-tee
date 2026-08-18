import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router";

import {
  resendEmailVerification,
  verifyEmail,
} from "../features/users/api/auth-api";
import styles from "../features/users/auth/auth-page.module.css";
import { loginHref } from "../session/unauthenticated";
import { useSecretFragment } from "../shared/secret-fragment";
import { Button } from "../ui/button/button";
import { Field } from "../ui/field/field";
import { InlineNotice } from "../ui/inline-notice/inline-notice";

export function meta() {
  return [{ title: "Подтверждение email — Booker Tee" }];
}

type VerificationState = "ready" | "invalid";

export default function VerifyEmailRoute() {
  const fragment = useSecretFragment();
  const [token] = useState(() => fragment.get("token"));
  const [nextPath] = useState(() => fragment.get("next"));
  const emailRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<VerificationState>(
    token ? "ready" : "invalid",
  );
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (state === "invalid") emailRef.current?.focus();
  }, [state]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setInterval(
      () => setCooldown((seconds) => Math.max(0, seconds - 1)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [cooldown]);

  async function confirm() {
    if (!token || pending) return;
    setPending(true);
    setMessage(null);
    const result = await verifyEmail({ token, nextPath });
    setPending(false);
    if (result.status === "success") {
      window.location.assign(result.nextPath);
      return;
    }
    setState("invalid");
    setMessage(result.message);
  }

  async function resend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim()) {
      setMessage("Введите email, указанный при регистрации.");
      emailRef.current?.focus();
      return;
    }
    setPending(true);
    setMessage(null);
    const result = await resendEmailVerification({ email });
    setPending(false);
    setCooldown(result.retryAfterSeconds ?? 60);
    setMessage(
      result.status === "success"
        ? "Если адрес ожидает подтверждения, новое письмо уже отправлено."
        : result.message,
    );
  }

  return (
    <main className={styles.page}>
      <section aria-labelledby="verify-title" className={styles.card}>
        <a className={styles.brand} href="/">
          Booker Tee
        </a>
        <header className={styles.heading}>
          <h1 id="verify-title">Подтвердить email</h1>
          <p>Это завершит регистрацию и создаст личный workspace.</p>
        </header>
        {state === "ready" ? (
          <div className={styles.accepted}>
            <InlineNotice title="Ссылка готова" tone="information">
              Подтверждение произойдёт только после нажатия кнопки.
            </InlineNotice>
            <Button
              isLoading={pending}
              onClick={confirm}
              tone="primary"
              type="button"
            >
              {pending ? "Подтверждаем…" : "Подтвердить email"}
            </Button>
          </div>
        ) : (
          <form className={styles.form} noValidate onSubmit={resend}>
            <InlineNotice title="Нужна новая ссылка" tone="warning">
              {message ??
                "Ссылка недействительна или уже использована. Запросите новую."}
            </InlineNotice>
            <Field htmlFor="verification-email" label="Email" required>
              <input
                autoComplete="email"
                disabled={pending}
                id="verification-email"
                name="email"
                onChange={(event) => setEmail(event.target.value)}
                ref={emailRef}
                required
                type="email"
                value={email}
              />
            </Field>
            <Button
              disabled={cooldown > 0}
              isLoading={pending}
              tone="primary"
              type="submit"
            >
              {pending
                ? "Отправляем…"
                : cooldown > 0
                  ? `Повторить через ${cooldown} сек.`
                  : "Отправить новую ссылку"}
            </Button>
          </form>
        )}
        <p aria-live="polite" className={styles.status}>
          {state === "invalid" ? message : null}
        </p>
        <p className={styles.footer}>
          <Link to={nextPath ? loginHref(nextPath) : "/auth/login"}>
            Вернуться ко входу
          </Link>
        </p>
      </section>
    </main>
  );
}
