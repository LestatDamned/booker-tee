from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from app.features.users.service import safe_next_path

router = APIRouter(include_in_schema=False)


def redirect_to_react(request: Request, target: str) -> RedirectResponse:
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(
        url=target,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


def redirect_auth_to_react(request: Request, target: str) -> RedirectResponse:
    next_path = request.query_params.get("next")
    if next_path is not None:
        target = f"{target}?{urlencode({'next': safe_next_path(next_path)})}"
    return RedirectResponse(
        url=target,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/login")
async def historical_login(request: Request) -> RedirectResponse:
    return redirect_auth_to_react(request, "/app/auth/login")


@router.get("/signup")
async def historical_signup(request: Request) -> RedirectResponse:
    return redirect_auth_to_react(request, "/app/auth/signup")


@router.get("/users")
async def historical_user_profile(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/profile")


@router.get("/dashboard")
async def historical_dashboard(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app")


@router.get("/dashboard/summary")
async def historical_dashboard_summary(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app")


@router.get("/ledger/manual")
async def historical_manual_ledger(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/ledger/manual")


@router.get("/accounts")
async def historical_accounts(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/accounts")


@router.get("/accounts/{account_id}")
async def historical_account_detail(
    request: Request,
    account_id: UUID,
) -> RedirectResponse:
    return redirect_to_react(request, f"/app/accounts/{account_id}")


@router.get("/imports")
async def historical_imports(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/imports")


@router.get("/imports/upload")
async def historical_import_upload(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/imports/upload")


@router.get("/imports/documents/{document_id}")
async def historical_import_document(
    request: Request,
    document_id: UUID,
) -> RedirectResponse:
    return redirect_to_react(request, f"/app/imports/documents/{document_id}")


@router.get("/imports/documents/{document_id}/mapping")
async def historical_import_mapping(
    request: Request,
    document_id: str,
) -> RedirectResponse:
    return redirect_to_react(
        request,
        f"/app/imports/documents/{document_id}/mapping",
    )


@router.get("/imports/documents/{document_id}/review")
async def historical_import_review(
    request: Request,
    document_id: str,
) -> RedirectResponse:
    return redirect_to_react(
        request,
        f"/app/imports/documents/{document_id}/review",
    )


@router.get("/reports")
async def historical_reports(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/reports")


@router.get("/properties")
async def historical_properties(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/properties")


@router.get("/categories")
async def historical_categories(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/categories")


@router.get("/categories/{category_id}")
async def historical_category_detail(
    request: Request,
    category_id: UUID,
) -> RedirectResponse:
    return redirect_to_react(request, f"/app/categories/{category_id}")


@router.get("/rules")
async def historical_transaction_rules(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/rules")


@router.get("/workspaces")
async def historical_workspaces(request: Request) -> RedirectResponse:
    return redirect_to_react(request, "/app/workspaces")


@router.get("/workspaces/invitations/{invitation_token}")
async def historical_workspace_invitation(
    request: Request,
    invitation_token: str,
) -> RedirectResponse:
    return redirect_to_react(
        request,
        f"/app/workspaces/invitations/{invitation_token}",
    )


@router.get("/chat-integrations/telegram/dev-link")
async def historical_telegram_dev_link(request: Request) -> RedirectResponse:
    return redirect_to_react(
        request,
        "/app/chat-integrations/telegram/dev-link",
    )
