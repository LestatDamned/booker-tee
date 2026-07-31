import { useSearchParams } from "react-router";

import { FoundationGallery } from "../foundation/foundation-gallery";
import { RouteLoadingPage } from "../ui/route-state-page/route-loading-page";
import {
  RouteStatePage,
  type RouteStateKind,
} from "../ui/route-state-page/route-state-page";

export function meta() {
  return [{ title: "UI Foundation — Booker Tee" }];
}

export default function FoundationRoute() {
  const [searchParams] = useSearchParams();
  const stateName = searchParams.get("route-state");

  if (stateName === "loading") {
    return (
      <RouteLoadingPage eyebrow="Booker Tee" title="Загружаем workspace…" />
    );
  }

  const state = routeStateExamples[stateName as RouteStateKind];

  if (state) {
    return (
      <RouteStatePage
        actionHref="/app/foundation"
        actionIcon="back"
        actionLabel="К компонентам"
        eyebrow={state.eyebrow}
        kind={stateName as RouteStateKind}
        title={state.title}
      >
        {state.message}
      </RouteStatePage>
    );
  }

  return <FoundationGallery />;
}

const routeStateExamples: Record<
  RouteStateKind,
  { eyebrow: string; message: string; title: string }
> = {
  unauthenticated: {
    eyebrow: "Сессия не найдена",
    title: "Войдите в Booker Tee",
    message: "Для работы с финансовыми данными нужна активная сессия.",
  },
  forbidden: {
    eyebrow: "Документ импорта",
    title: "Нет доступа к workspace",
    message: "Ваша роль не позволяет открыть этот документ.",
  },
  notFound: {
    eyebrow: "Документ импорта",
    title: "Документ не найден",
    message: "Документ удалён или относится к другому workspace.",
  },
  error: {
    eyebrow: "Ошибка загрузки",
    title: "Не удалось загрузить операции",
    message: "Проверьте соединение и повторите попытку.",
  },
};
