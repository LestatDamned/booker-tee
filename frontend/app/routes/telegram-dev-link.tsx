import { loadSession } from "../api/session";
import {
  loadTelegramDevLinkConfig,
  type TelegramDevLinkConfigResult,
} from "../features/chat-integrations/api/telegram-dev-link-api";
import { TelegramDevLinkPage } from "../features/chat-integrations/telegram-dev-link-page";
import { loginHref } from "../session/unauthenticated";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/telegram-dev-link";

export function meta() {
  return [{ title: "Telegram dev-link — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const [config, session] = await Promise.all([
    loadTelegramDevLinkConfig(request.signal),
    loadSession(request.signal),
  ]);
  const url = new URL(request.url);
  return {
    config,
    initialDisplayName: url.searchParams.get("display_name") ?? "",
    initialExternalUserId: url.searchParams.get("external_user_id") ?? "",
    session,
  };
}

export default function TelegramDevLinkRoute({
  loaderData,
}: Route.ComponentProps) {
  const { config, initialDisplayName, initialExternalUserId, session } =
    loaderData;
  if (
    session.status === "unauthenticated" ||
    config.status === "unauthenticated"
  ) {
    return <TelegramDevLinkRouteState result={{ status: "unauthenticated" }} />;
  }
  if (session.status === "error") {
    return <TelegramDevLinkRouteState result={session} />;
  }
  if (config.status !== "success") {
    return <TelegramDevLinkRouteState result={config} />;
  }
  if (session.status !== "authenticated") {
    return (
      <TelegramDevLinkRouteState
        result={{ status: "error", message: "Сессия не загружена." }}
      />
    );
  }
  return (
    <TelegramDevLinkPage
      initialDisplayName={initialDisplayName}
      initialExternalUserId={initialExternalUserId}
      session={session.session}
    />
  );
}

function TelegramDevLinkRouteState({
  result,
}: {
  result: Exclude<TelegramDevLinkConfigResult, { status: "success" }>;
}) {
  const unauthenticated = result.status === "unauthenticated";
  const notFound = result.status === "not_found";
  return (
    <RouteStatePage
      actionHref={
        unauthenticated
          ? loginHref("/app/chat-integrations/telegram/dev-link")
          : "/app"
      }
      actionLabel={unauthenticated ? "Войти" : "Открыть Booker Tee"}
      eyebrow={
        unauthenticated
          ? "Сессия не найдена"
          : notFound
            ? "Development tool"
            : "Ошибка загрузки"
      }
      kind={
        unauthenticated ? "unauthenticated" : notFound ? "notFound" : "error"
      }
      title={
        unauthenticated
          ? "Войдите в Booker Tee"
          : notFound
            ? "Dev-link недоступен"
            : "Не удалось открыть dev-link"
      }
    >
      {!unauthenticated && !notFound ? result.message : null}
    </RouteStatePage>
  );
}
