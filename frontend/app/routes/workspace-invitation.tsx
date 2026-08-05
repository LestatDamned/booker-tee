import { loadSession } from "../api/session";
import {
  loadPublicWorkspaceInvitation,
  type PublicWorkspaceInvitationLoadResult,
} from "../features/workspaces/api/workspace-invitations-api";
import { WorkspaceInvitationPage } from "../features/workspaces/workspace-invitation-page";
import { RouteStatePage } from "../ui/route-state-page/route-state-page";
import type { Route } from "./+types/workspace-invitation";

export function meta() {
  return [{ title: "Приглашение — Booker Tee" }];
}

export async function clientLoader({
  params,
  request,
}: Route.ClientLoaderArgs) {
  const invitationToken = params.invitationToken ?? "";
  const [invitation, session] = await Promise.all([
    loadPublicWorkspaceInvitation(invitationToken, request.signal),
    loadSession(request.signal),
  ]);
  return { invitation, invitationToken, session };
}

export default function WorkspaceInvitationRoute({
  loaderData,
}: Route.ComponentProps) {
  const { invitation, invitationToken, session } = loaderData;
  if (invitation.status !== "success") {
    return <InvitationRouteState result={invitation} />;
  }
  if (session.status === "error") {
    return (
      <RouteStatePage
        actionHref={`/app/workspaces/invitations/${encodeURIComponent(invitationToken)}`}
        actionLabel="Попробовать снова"
        eyebrow="Ошибка загрузки"
        kind="error"
        title="Не удалось проверить сессию"
      >
        {session.message}
      </RouteStatePage>
    );
  }
  return (
    <WorkspaceInvitationPage
      invitation={invitation.invitation}
      invitationToken={invitationToken}
      session={session.status === "authenticated" ? session.session : null}
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
