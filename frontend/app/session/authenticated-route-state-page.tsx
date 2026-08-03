import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import { loginHref } from "./unauthenticated";

export type AuthenticatedRouteFailure =
  { status: "unauthenticated" } | { status: "error"; message: string };

export function AuthenticatedRouteStatePage({
  errorTitle,
  retryHref,
  result,
  returnTo,
}: {
  errorTitle: string;
  retryHref?: string;
  result: AuthenticatedRouteFailure;
  returnTo: string;
}) {
  const unauthenticated = result.status === "unauthenticated";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated ? loginHref(returnTo) : (retryHref ?? returnTo)
      }
      actionLabel={unauthenticated ? "Войти" : "Повторить"}
      eyebrow={unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      kind={unauthenticated ? "unauthenticated" : "error"}
      title={unauthenticated ? "Войдите в Booker Tee" : errorTitle}
    >
      {unauthenticated ? null : result.message}
    </RouteStatePage>
  );
}
