import { useNavigation, useRevalidator } from "react-router";

import type { Route } from "./+types/manual-ledger";
import type { ManualOperationDto } from "../features/manual-ledger/api/manual-ledger-api";
import { ManualLedgerPage } from "../features/manual-ledger/list/manual-ledger-page";
import {
  AuthenticatedRouteStatePage,
  type AuthenticatedRouteFailure,
} from "../session/authenticated-route-state-page";
import { loadManualLedgerRoute } from "./manual-ledger-loader";

export { loadManualLedgerRoute } from "./manual-ledger-loader";

export function meta() {
  return [{ title: "Ручные операции — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadManualLedgerRoute(request);
}

export default function ManualLedgerRoute({
  loaderData,
}: Route.ComponentProps) {
  const revalidator = useRevalidator();
  const navigation = useNavigation();
  return (
    <ManualLedgerRouteView
      loaderData={loaderData}
      navigationPending={navigation.state !== "idle"}
      onOperationDeleted={() => void revalidator.revalidate()}
      onOperationUpdated={() => void revalidator.revalidate()}
      onRefresh={() => void revalidator.revalidate()}
    />
  );
}

export function ManualLedgerRouteView({
  loaderData,
  navigationPending = false,
  onOperationDeleted,
  onOperationUpdated,
  onRefresh,
}: {
  loaderData: Awaited<ReturnType<typeof loadManualLedgerRoute>>;
  navigationPending?: boolean;
  onOperationDeleted?: (operationId: string) => void;
  onOperationUpdated?: (operation: ManualOperationDto) => void;
  onRefresh?: () => void;
}) {
  const { ledger, session } = loaderData;
  if (
    session.status === "unauthenticated" ||
    ledger.status === "unauthenticated"
  ) {
    return <ManualLedgerRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") {
    return <ManualLedgerRouteState result={session} />;
  }
  if (ledger.status === "error") {
    return <ManualLedgerRouteState result={ledger} />;
  }
  if (session.status !== "authenticated") {
    return (
      <ManualLedgerRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <ManualLedgerPage
      ledger={ledger.ledger}
      navigationPending={navigationPending}
      {...(onOperationDeleted === undefined ? {} : { onOperationDeleted })}
      {...(onOperationUpdated === undefined ? {} : { onOperationUpdated })}
      {...(onRefresh === undefined ? {} : { onRefresh })}
      session={session.session}
    />
  );
}

function ManualLedgerRouteState({
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
      returnTo="/app/ledger/manual"
    />
  );
}
