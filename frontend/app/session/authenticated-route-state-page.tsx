import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import { loginHref } from "./unauthenticated";

export type AuthenticatedRouteFailure =
  | { status: "unauthenticated" }
  | { status: "forbidden"; message: string }
  | { status: "error"; message: string };

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
  const forbidden = result.status === "forbidden";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated
          ? loginHref(returnTo)
          : forbidden
            ? "/app"
            : (retryHref ?? returnTo)
      }
      actionLabel={
        unauthenticated ? "Войти" : forbidden ? "На главную" : "Повторить"
      }
      eyebrow={
        unauthenticated
          ? "Сессия не найдена"
          : forbidden
            ? "Доступ ограничен"
            : "Ошибка загрузки"
      }
      kind={
        unauthenticated ? "unauthenticated" : forbidden ? "forbidden" : "error"
      }
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : forbidden
            ? "Нет доступа"
            : errorTitle
      }
    >
      {unauthenticated ? null : result.message}
    </RouteStatePage>
  );
}
