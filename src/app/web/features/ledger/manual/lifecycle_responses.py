from fastapi import Request, status
from fastapi.responses import RedirectResponse, Response

from app.features.ledger.mapping.dto import ManualOperationView
from app.features.ledger.service import LedgerPostingService
from app.features.workspaces.service import WorkspaceContext
from app.web.features.ledger.manual.presenter import ManualLedgerPresenter
from app.web.features.ledger.manual.queries import ManualLedgerPageQuery
from app.web.features.ledger.manual.query_state import (
    ManualLedgerListQuery,
    clear_operation_target_url,
    target_operation_url,
)
from app.web.features.ledger.manual.renderer import ManualLedgerRenderer
from app.web.features.ledger.manual.response_scope import (
    ManualLedgerUpdateResponseScope,
    ManualLedgerUpdateScope,
)
from app.web.ui.responses import is_htmx_request


class ManualLedgerLifecycleResponses:
    def __init__(
        self,
        *,
        ledger: LedgerPostingService,
        renderer: ManualLedgerRenderer,
    ) -> None:
        self._ledger = ledger
        self._renderer = renderer

    async def status_changed(
        self,
        request: Request,
        *,
        context: WorkspaceContext,
        previous: ManualOperationView,
        updated: ManualOperationView,
        return_to: str,
    ) -> Response:
        if not is_htmx_request(request):
            return RedirectResponse(
                url=target_operation_url(return_to, updated.id),
                status_code=status.HTTP_303_SEE_OTHER,
            )

        list_query = ManualLedgerListQuery.from_return_to(return_to)
        scope = ManualLedgerUpdateResponseScope().resolve(
            previous=previous,
            updated=updated,
            filters=list_query.filters,
        )
        if scope is ManualLedgerUpdateScope.REPLACE_LIST:
            return await self._replace_list(
                request,
                context=context,
                return_to=return_to,
            )

        row = ManualLedgerPresenter().present_row(
            updated,
            focused_operation_id=list_query.focused_operation_id,
            can_write=True,
            return_to=return_to,
            reset_edit_panel=True,
        )
        return self._renderer.row(request, row)

    async def deleted(
        self,
        request: Request,
        *,
        context: WorkspaceContext,
        return_to: str,
    ) -> Response:
        settled_url = clear_operation_target_url(return_to)
        if not is_htmx_request(request):
            return RedirectResponse(
                url=settled_url,
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return await self._replace_list(
            request,
            context=context,
            return_to=settled_url,
        )

    async def error_row(
        self,
        request: Request,
        *,
        operation: ManualOperationView,
        return_to: str,
        message: str,
    ) -> Response:
        list_query = ManualLedgerListQuery.from_return_to(return_to)
        row = ManualLedgerPresenter().present_row(
            operation,
            focused_operation_id=list_query.focused_operation_id,
            can_write=True,
            return_to=return_to,
            request_error=message,
        )
        return self._renderer.row(
            request,
            row,
            response_status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    async def _replace_list(
        self,
        request: Request,
        *,
        context: WorkspaceContext,
        return_to: str,
    ) -> Response:
        list_query = ManualLedgerListQuery.from_return_to(return_to)
        page_data = await ManualLedgerPageQuery(self._ledger).execute(
            workspace_id=context.workspace.id,
            query=list_query,
        )
        presenter = ManualLedgerPresenter()
        page = presenter.present(
            workspace_name=context.workspace.name,
            operations=page_data.operations,
            page=page_data.page,
            filters=list_query.filters,
            focused_operation_id=list_query.focused_operation_id,
            can_write=True,
            reset_edit_panels=True,
        )
        replace_url = presenter.list_url(
            filters=list_query.filters,
            page=page_data.page.page,
            per_page=page_data.page.per_page,
            focused_operation_id=list_query.focused_operation_id,
        )
        return self._renderer.results(
            request,
            page,
            replace_url=replace_url,
        )
