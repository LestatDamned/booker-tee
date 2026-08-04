import { useState, type FormEvent } from "react";

import { AppShell } from "../shell/app-shell";
import { logout, updateAccount } from "../features/users/api/account-api";
import styles from "../features/users/profile/profile-page.module.css";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
import { Button } from "../ui/button/button";
import { RouterButtonLink } from "../ui/button/button";
import { Field } from "../ui/field/field";
import { FormErrorSummary } from "../ui/field/form-error-summary";
import { FormActions } from "../ui/field/form-layout";
import { InlineNotice } from "../ui/inline-notice/inline-notice";
import { PageFrame } from "../ui/page-frame/page-frame";
import { PageHeader } from "../ui/page-header/page-header";
import { WorkbenchSurface } from "../ui/workbench-surface/workbench-surface";
import type { Route } from "./+types/profile";
import { loadProfileRoute } from "./profile-loader";

export { loadProfileRoute } from "./profile-loader";

export function meta() {
  return [{ title: "Профиль — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadProfileRoute(request);
}

export default function ProfileRoute({ loaderData }: Route.ComponentProps) {
  const { account, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    account.status === "unauthenticated"
  ) {
    return <ProfileRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") return <ProfileRouteState result={session} />;
  if (account.status === "error") return <ProfileRouteState result={account} />;
  if (session.status !== "authenticated" || account.status !== "success") {
    return (
      <ProfileRouteState
        result={{ status: "error", message: "Профиль не загружен." }}
      />
    );
  }
  return (
    <AppShell session={session.session}>
      <ProfilePage
        account={account.account}
        csrfToken={session.session.csrfToken}
      />
    </AppShell>
  );
}

function ProfilePage({
  account,
  csrfToken,
}: {
  account: { email: string; name: string | null };
  csrfToken: string;
}) {
  const [name, setName] = useState(account.name ?? "");
  const [pending, setPending] = useState(false);
  const [logoutPending, setLogoutPending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setMessage(null);
    const result = await updateAccount(name, csrfToken);
    setPending(false);
    if (result.status === "unauthenticated") {
      window.location.assign("/app/auth/login?next=%2Fapp%2Fprofile");
    } else if (result.status === "error") {
      setError(result.message);
    } else {
      setName(result.account.name ?? "");
      setMessage("Профиль сохранён.");
    }
  }

  async function signOut() {
    setLogoutPending(true);
    setError(null);
    const result = await logout(csrfToken);
    if (result.status === "error") {
      setLogoutPending(false);
      setError(result.message ?? "Не удалось выйти.");
      return;
    }
    window.location.assign("/app/auth/login");
  }

  return (
    <PageFrame aria-labelledby="profile-title">
      <div className={styles.content}>
        <PageHeader
          description="Личные данные аккаунта и управление текущей сессией."
          eyebrow="Аккаунт"
          title="Профиль"
          titleId="profile-title"
        />
        <WorkbenchSurface>
          <form className={styles.form} noValidate onSubmit={save}>
            <div className={styles.sectionHeading}>
              <h2>Личные данные</h2>
              <p>Имя отображается в интерфейсе. Email пока нельзя изменить.</p>
            </div>
            {error ? <FormErrorSummary message={error} /> : null}
            {message ? (
              <InlineNotice aria-live="polite" tone="success">
                {message}
              </InlineNotice>
            ) : null}
            <Field
              htmlFor="profile-name"
              label="Имя"
              hint="Можно оставить пустым."
            >
              <input
                autoComplete="name"
                disabled={pending}
                id="profile-name"
                maxLength={255}
                name="name"
                onChange={(event) => setName(event.target.value)}
                value={name}
              />
            </Field>
            <Field
              htmlFor="profile-email"
              label="Email"
              hint="Изменение email появится на следующем этапе."
            >
              <input
                className={styles.readOnly}
                id="profile-email"
                readOnly
                type="email"
                value={account.email}
              />
            </Field>
            <FormActions>
              <Button isLoading={pending} tone="primary" type="submit">
                {pending ? "Сохраняем…" : "Сохранить"}
              </Button>
            </FormActions>
            <FormActions>
              <RouterButtonLink to="/profile/security">
                Безопасность и пароль
              </RouterButtonLink>
              <RouterButtonLink to="/profile/sessions">
                Активные сессии
              </RouterButtonLink>
            </FormActions>
          </form>
          <div className={styles.dangerZone}>
            <div className={styles.sectionHeading}>
              <h2>Текущая сессия</h2>
              <p>Выход отзовёт серверную сессию на этом устройстве.</p>
            </div>
            <FormActions>
              <Button
                isLoading={logoutPending}
                onClick={signOut}
                tone="dangerSecondary"
              >
                {logoutPending ? "Выходим…" : "Выйти"}
              </Button>
            </FormActions>
          </div>
        </WorkbenchSurface>
      </div>
    </PageFrame>
  );
}

function ProfileRouteState({ result }: { result: AuthenticatedRouteFailure }) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить профиль"
      result={result}
      returnTo="/app/profile"
    />
  );
}
