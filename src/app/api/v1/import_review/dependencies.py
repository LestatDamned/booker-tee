from typing import Annotated

from fastapi import Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError
from app.db.session import get_session
from app.features.accounts.service import AccountService
from app.features.categories.service import CategoryService
from app.features.imports.application.review.classification import (
    ImportReviewCategoryCreator,
    ImportReviewDraftEvaluator,
    ImportReviewReferenceReader,
)
from app.features.imports.application.review.confirmation_commands import (
    ImportReviewConfirmationService,
)
from app.features.imports.application.review.lifecycle_commands import (
    ImportReviewLifecycleService,
)
from app.features.imports.application.review.read_model import ImportReviewReader
from app.features.imports.application.review.rule_commands import (
    ImportReviewRuleApplicationService,
)
from app.features.imports.application.review.transfer_commands import ImportReviewTransferService
from app.features.imports.application.review.transfers import ImportReviewTransferReader
from app.features.imports.application.review.undo_commands import ImportReviewUndoService
from app.features.imports.repository import ImportRepository
from app.features.ledger.application.transfer_suggestions import TransferSuggestionUseCase
from app.features.properties.service import PropertyService
from app.features.workspaces.permissions import permission_flags_for


def get_import_review_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportReviewReader:
    return ImportReviewReader(
        ImportRepository(session),
        ImportReviewReferenceReader(
            CategoryService(session),
            PropertyService(session),
        ),
        ImportReviewTransferReader(
            AccountService(session),
            TransferSuggestionUseCase(session),
        ),
    )


def get_import_review_transfer_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportReviewTransferService:
    return ImportReviewTransferService(session)


def get_import_review_lifecycle_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportReviewLifecycleService:
    return ImportReviewLifecycleService(session)


def get_import_review_confirmation_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportReviewConfirmationService:
    return ImportReviewConfirmationService(session)


def get_import_review_undo_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportReviewUndoService:
    return ImportReviewUndoService(session)


def get_import_review_rule_application_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportReviewRuleApplicationService:
    return ImportReviewRuleApplicationService(session)


def get_import_review_draft_evaluator(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportReviewDraftEvaluator:
    return ImportReviewDraftEvaluator(
        ImportRepository(session),
        CategoryService(session),
        PropertyService(session),
    )


def get_import_review_category_creator(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImportReviewCategoryCreator:
    return ImportReviewCategoryCreator(
        ImportRepository(session),
        CategoryService(session),
    )


def require_import_review_write_context(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
) -> ApiRequestContext:
    permissions = permission_flags_for(context.workspace.membership)
    if not (permissions.can_manage_imports and permissions.can_write_financial_data):
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="import_review_write_forbidden",
            message="Недостаточно прав для изменения import review.",
        )
    return context
