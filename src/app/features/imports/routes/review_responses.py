from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response

from app.core.settings import Settings
from app.features.imports.application.review.page_data import ImportReviewPageDataLoader
from app.features.imports.presentation.review.page import (
    ReviewPageContext,
    build_review_page_context,
    review_redirect_url,
)
from app.features.workspaces.service import WorkspaceContext
from app.templating import create_templates

templates = create_templates()


@dataclass(frozen=True)
class ReviewActionResponseRequest:
    document_id: UUID
    raw_transaction_id: UUID
    oob_raw_transaction_ids: frozenset[UUID] = frozenset()
    selected_category_id: UUID | None = None
    open_category_editor: bool = False
    create_category_error: str | None = None
    create_category_initial_name: str | None = None
    refresh_category_options: bool = False
    action_error: str | None = None
    active_panel_type: str | None = None

    def redirect_url(self) -> str:
        return review_redirect_url(self.document_id)

    def response_state(self) -> "ReviewActionResponseState":
        return ReviewActionResponseState(
            raw_transaction_id=self.raw_transaction_id,
            oob_raw_transaction_ids=self.oob_raw_transaction_ids,
            selected_category_id=self.selected_category_id,
            open_category_editor=self.open_category_editor,
            create_category_error=self.create_category_error,
            create_category_initial_name=self.create_category_initial_name,
            refresh_category_options=self.refresh_category_options,
            action_error=self.action_error,
            active_panel_type=self.active_panel_type,
        )


@dataclass(frozen=True)
class ReviewActionResponseState:
    raw_transaction_id: UUID
    oob_raw_transaction_ids: frozenset[UUID]
    selected_category_id: UUID | None = None
    open_category_editor: bool = False
    create_category_error: str | None = None
    create_category_initial_name: str | None = None
    refresh_category_options: bool = False
    action_error: str | None = None
    active_panel_type: str | None = None

    def selected_category_id_by_row(self) -> Mapping[UUID, UUID]:
        if self.selected_category_id is None:
            return {}
        return {self.raw_transaction_id: self.selected_category_id}

    def open_category_editor_by_row(self) -> Mapping[UUID, bool]:
        if not self.open_category_editor:
            return {}
        return {self.raw_transaction_id: True}

    def create_category_error_by_row(self) -> Mapping[UUID, str]:
        if self.create_category_error is None:
            return {}
        return {self.raw_transaction_id: self.create_category_error}

    def create_category_initial_name_by_row(self) -> Mapping[UUID, str]:
        if self.create_category_initial_name is None:
            return {}
        return {self.raw_transaction_id: self.create_category_initial_name}

    def action_error_by_row(self) -> Mapping[UUID, str]:
        if self.action_error is None:
            return {}
        return {self.raw_transaction_id: self.action_error}

    def active_panel_type_by_row(self) -> Mapping[UUID, str]:
        if self.active_panel_type is None:
            return {}
        return {self.raw_transaction_id: self.active_panel_type}

    def oob_row_ids(self, document: object) -> frozenset[UUID]:
        if self.refresh_category_options:
            row_ids = {
                row_id
                for row in getattr(document, "raw_transactions", [])
                if (row_id := getattr(row, "id", None)) is not None
                and self._is_refreshable_row(row)
            }
            return frozenset(row_ids) - {self.raw_transaction_id}
        return self.oob_raw_transaction_ids - {self.raw_transaction_id}

    def template_values(
        self,
        *,
        page_context: ReviewPageContext,
        document: object,
        app_name: str,
        workspace: object,
    ) -> dict[str, object]:
        values = page_context.template_values(app_name=app_name, workspace=workspace)
        oob_row_ids = self.oob_row_ids(document)
        values["current_item"] = page_context.review_item_for(self.raw_transaction_id)
        values["oob_review_items"] = page_context.review_items_for_row_ids(oob_row_ids)
        return values

    def _is_refreshable_row(self, row: object) -> bool:
        row_status = getattr(row, "status", None)
        row_status_value = getattr(row_status, "value", row_status)
        return row_status_value not in {"confirmed", "ignored", "duplicate"}


@dataclass(frozen=True)
class ReviewActionResponseRenderer:
    data_loader: ImportReviewPageDataLoader

    async def render(
        self,
        *,
        request: Request,
        settings: Settings,
        context: WorkspaceContext,
        response_request: ReviewActionResponseRequest,
    ) -> Response:
        if not self._is_htmx_request(request):
            return self._redirect_response(response_request)
        response_state = response_request.response_state()
        document = await self._load_document_or_404(
            context=context,
            document_id=response_request.document_id,
        )
        self._ensure_review_row_exists(
            document=document,
            raw_transaction_id=response_request.raw_transaction_id,
        )
        page_context = await self._build_page_context(
            context=context,
            document=document,
            response_state=response_state,
        )
        return self._template_response(
            request=request,
            settings=settings,
            context=context,
            document=document,
            page_context=page_context,
            response_state=response_state,
        )

    def _redirect_response(
        self,
        response_request: ReviewActionResponseRequest,
    ) -> RedirectResponse:
        return RedirectResponse(
            url=response_request.redirect_url(),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    async def _load_document_or_404(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
    ) -> object:
        document = await self.data_loader.load_document(
            workspace_id=context.workspace.id,
            document_id=document_id,
        )
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return document

    def _ensure_review_row_exists(
        self,
        *,
        document: object,
        raw_transaction_id: UUID,
    ) -> None:
        row = self._review_row_from_document(document, raw_transaction_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    async def _build_page_context(
        self,
        *,
        context: WorkspaceContext,
        document: object,
        response_state: ReviewActionResponseState,
    ) -> ReviewPageContext:
        page_data = await self.data_loader.load_page_data(
            context=context,
            document=document,
        )
        return build_review_page_context(
            document=document,
            accounts=page_data.accounts,
            categories=page_data.categories,
            properties=page_data.properties,
            transfer_suggestions=page_data.transfer_suggestions,
            existing_transfer_suggestions=page_data.existing_transfer_suggestions,
            selected_category_id_by_row=response_state.selected_category_id_by_row(),
            open_category_editor_by_row=response_state.open_category_editor_by_row(),
            create_category_error_by_row=response_state.create_category_error_by_row(),
            create_category_initial_name_by_row=response_state.create_category_initial_name_by_row(),
            action_error_by_row=response_state.action_error_by_row(),
            active_panel_type_by_row=response_state.active_panel_type_by_row(),
        )

    def _template_response(
        self,
        *,
        request: Request,
        settings: Settings,
        context: WorkspaceContext,
        document: object,
        page_context: ReviewPageContext,
        response_state: ReviewActionResponseState,
    ) -> Response:
        template_values = response_state.template_values(
            page_context=page_context,
            document=document,
            app_name=settings.app_name,
            workspace=context.workspace,
        )
        return templates.TemplateResponse(
            request,
            "imports/_review_action_response.html",
            template_values,
        )

    def _is_htmx_request(self, request: Request) -> bool:
        return request.headers.get("hx-request") == "true"

    def _review_row_from_document(
        self,
        document: object,
        raw_transaction_id: UUID,
    ) -> object | None:
        raw_transactions = getattr(document, "raw_transactions", [])
        return next(
            (row for row in raw_transactions if getattr(row, "id", None) == raw_transaction_id),
            None,
        )
