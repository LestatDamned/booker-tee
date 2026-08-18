import { useEffect, useState } from "react";

import { loadSession } from "../api/session";
import {
  loadPublicWorkspaceInvitation,
  type PublicWorkspaceInvitationLoadResult,
} from "../features/workspaces/api/workspace-invitations-api";
import { WorkspaceInvitationPage } from "../features/workspaces/workspace-invitation-page";
import { useSecretFragment } from "../shared/secret-fragment";
import { RouteLoadingPage } from "../ui/route-state-page/route-loading-page";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/workspace-invitation";

export function meta() {
  return [{ title: "Приглашение — Booker Tee" }];
}

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  return loadSession(request.signal);
}

export default function WorkspaceInvitationRoute({
  loaderData,
}: Route.ComponentProps) {
  const fragment = useSecretFragment();
  const [invitationToken] = useState(() => fragment.get("token") ?? "");
  const [invitation, setInvitation] =
    useState<PublicWorkspaceInvitationLoadResult | null>(() =>
      invitationToken ? null : { status: "not_found" },
    );

  useEffect(() => {
    if (!invitationToken) return;
    const controller = new AbortController();
    void loadPublicWorkspaceInvitation(invitationToken, controller.signal)
      .then(setInvitation)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError")
          return;
        setInvitation({
          status: "error",
          message: "Не удалось открыть приглашение.",
        });
      });
    return () => controller.abort();
  }, [invitationToken]);

  if (!invitation) {
    return <RouteLoadingPage eyebrow="Приглашение" title="Открываем ссылку…" />;
  }
  if (invitation.status !== "success") {
    return <InvitationRouteState result={invitation} />;
  }
  if (loaderData.status === "error") {
    return (
      <RouteStatePage
        actionHref={`/app/workspaces/invitation#${new URLSearchParams({ token: invitationToken })}`}
        actionLabel="Попробовать снова"
        eyebrow="Ошибка загрузки"
        kind="error"
        title="Не удалось проверить сессию"
      >
        {loaderData.message}
      </RouteStatePage>
    );
  }
  return (
    <WorkspaceInvitationPage
      invitation={invitation.invitation}
      invitationToken={invitationToken}
      session={
        loaderData.status === "authenticated" ? loaderData.session : null
      }
    />
  );
}

function InvitationRouteState({
  result,
}: {
  result: Exclude<PublicWorkspaceInvitationLoadResult, { status: "success" }>;
}) {
  const notFound = result.status === "not_found";
  return (
    <RouteStatePage
      actionHref="/app"
      actionLabel="Открыть Booker Tee"
      eyebrow={notFound ? "Ссылка недействительна" : "Ошибка загрузки"}
      kind={notFound ? "notFound" : "error"}
      title={
        notFound ? "Приглашение недоступно" : "Не удалось открыть приглашение"
      }
    >
      {notFound
        ? "Ссылка могла истечь, быть отозвана или уже использована."
        : result.message}
    </RouteStatePage>
  );
}
