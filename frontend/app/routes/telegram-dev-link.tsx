import { loadSession } from "../api/session";
import { TelegramDevLinkPage } from "../features/chat-integrations/telegram-dev-link-page";
import { loginHref } from "../session/unauthenticated";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/telegram-dev-link";

export function meta() {
  return [{ title: "Подключить Telegram — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadSession(request.signal);
}

export default function TelegramLinkRoute({
  loaderData,
}: Route.ComponentProps) {
  if (loaderData.status === "authenticated") {
    return <TelegramDevLinkPage session={loaderData.session} />;
  }
  const unauthenticated = loaderData.status === "unauthenticated";
  return (
    <RouteStatePage
      actionHref={unauthenticated ? loginHref(requestPath) : "/app"}
      actionLabel={unauthenticated ? "Войти" : "Открыть Booker Tee"}
      eyebrow={unauthenticated ? "Сессия не найдена" : "Ошибка загрузки"}
      kind={unauthenticated ? "unauthenticated" : "error"}
      title={
        unauthenticated ? "Войдите в Booker Tee" : "Не удалось открыть привязку"
      }
    >
      {loaderData.status === "error" ? loaderData.message : null}
    </RouteStatePage>
  );
}

const requestPath = "/app/chat-integrations/telegram/link";
