import type { Route } from "./+types/manual-ledger";
import { loadSession } from "../api/session";
import {
  loadManualLedger,
  type ManualLedgerLoadResult,
} from "../features/manual-ledger/manual-ledger-api";
import { ManualLedgerPage } from "../features/manual-ledger/manual-ledger-page";
import styles from "../styles/shell.module.css";

export function meta() {
  return [{ title: "Ручные операции — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const search = new URL(request.url).search;
  const [session, ledger] = await Promise.all([
    loadSession(),
    loadManualLedger(search),
  ]);
  return { session, ledger };
}

export default function ManualLedgerRoute({
  loaderData,
}: Route.ComponentProps) {
  const { ledger, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    ledger.status === "unauthenticated"
  ) {
    return <RouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") {
    return <RouteState result={session} />;
  }
  if (ledger.status === "error") {
    return <RouteState result={ledger} />;
  }
  if (session.status !== "authenticated") {
    return (
      <RouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return <ManualLedgerPage ledger={ledger.ledger} session={session.session} />;
}

function RouteState({
  result,
}: {
  result: Exclude<ManualLedgerLoadResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  return (
    <main
      className={styles.centeredState}
      role={unauthenticated ? undefined : "alert"}
    >
      <p className={styles.eyebrow}>
        {unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      </p>
      <h1>
        {unauthenticated
          ? "Войдите в Booker Tee"
          : "Не удалось загрузить операции"}
      </h1>
      {!unauthenticated ? <p>{result.message}</p> : null}
      <a
        className={styles.buttonLink}
        href={
          unauthenticated
            ? "/login?next=/app/ledger/manual"
            : window.location.href
        }
      >
        {unauthenticated ? "Войти" : "Повторить"}
      </a>
    </main>
  );
}
