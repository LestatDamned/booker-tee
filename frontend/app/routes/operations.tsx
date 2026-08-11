import { useNavigation, useRevalidator } from "react-router";

import type { Route } from "./+types/operations";
import { ManualLedgerPage } from "../features/manual-ledger/list/manual-ledger-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
import { loadOperationsRoute } from "./operations-loader";

export { loadOperationsRoute } from "./operations-loader";

export function meta() {
  return [{ title: "Операции — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadOperationsRoute(request);
}

export default function OperationsRoute({ loaderData }: Route.ComponentProps) {
  const revalidator = useRevalidator();
  const navigation = useNavigation();
  return (
    <OperationsRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
      onRefresh={() => void revalidator.revalidate()}
    />
  );
}

export function OperationsRouteView({
  loaderData,
  navigationPending = false,
  onRefresh,
}: {
  loaderData: Awaited<ReturnType<typeof loadOperationsRoute>>;
  navigationPending?: boolean;
  onRefresh?: () => void;
}) {
  const { operations, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    operations.status === "unauthenticated"
  ) {
    return <OperationsRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error")
    return <OperationsRouteState result={session} />;
  if (operations.status === "error") {
    return <OperationsRouteState result={operations} />;
  }
  if (session.status !== "authenticated") {
    return (
      <OperationsRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <ManualLedgerPage
      ledger={operations.operations}
      navigationPending={navigationPending}
      {...(onRefresh === undefined ? {} : { onRefresh })}
      session={session.session}
    />
  );
}

function OperationsRouteState({
  result,
}: {
  result: AuthenticatedRouteFailure;
}) {
  return (
    <AuthenticatedRouteStatePage
      errorTitle="Не удалось загрузить операции"
      {...(result.status === "error"
        ? { retryHref: window.location.href }
        : {})}
      result={result}
      returnTo="/app/operations"
    />
  );
}
