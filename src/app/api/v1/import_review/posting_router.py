from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import ApiRequestContext
from app.api.errors import ApiError, api_error_responses
from app.api.v1.import_review.dependencies import (
    get_import_review_confirmation_service,
    get_import_review_reader,
    get_import_review_undo_service,
    require_import_review_write_context,
)
from app.api.v1.import_review.schemas.requests import (
    ImportReviewConfirmationApiRequest,
    ImportReviewUndoApiRequest,
)
from app.api.v1.import_review.schemas.responses import (
    ImportReviewApiResponse,
    ImportReviewPostingMutationApiResponse,
)
from app.features.import_review.application.confirmation import (
    ConfirmImportReviewItemCommand,
    ImportReviewConfirmationConflictError,
    ImportReviewConfirmationService,
    ImportReviewConfirmationValidationError,
)
from app.features.import_review.application.read_model import (
    ImportReviewReader,
    ImportReviewReadModel,
)
from app.features.import_review.application.undo import (
    ImportReviewUndoService,
    UndoImportReviewPostingCommand,
)
from app.features.imports.errors import RawTransactionReviewError
from app.features.ledger.errors import LedgerPostingError
from app.features.transaction_rules.errors import TransactionRuleError

router = APIRouter()


@router.post(
    "/{document_id}/items/{item_id}/confirm",
    response_model=ImportReviewPostingMutationApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def confirm_import_review_item(
    document_id: UUID,
    item_id: UUID,
    request: ImportReviewConfirmationApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_import_review_write_context),
    ],
    confirmations: Annotated[
        ImportReviewConfirmationService,
        Depends(get_import_review_confirmation_service),
    ],
    reader: Annotated[ImportReviewReader, Depends(get_import_review_reader)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> ImportReviewPostingMutationApiResponse:
    try:
        result = await confirmations.execute(
            context=context.workspace,
            command=ConfirmImportReviewItemCommand(
                document_id=document_id,
                item_id=item_id,
                operation_type=request.operation_type,
                category_id=request.category_id,
                property_id=request.property_id,
                expected_status=request.expected_status,
                remember_rule=request.remember_rule,
                rule_pattern=request.rule_pattern,
                idempotency_key=idempotency_key,
            ),
        )
    except ImportReviewConfirmationConflictError as exc:
        raise _posting_conflict() from exc
    except ImportReviewConfirmationValidationError as exc:
        field_errors = dict(exc.field_errors)
        if exc.blocking_reason_codes:
            field_errors["item"] = [reason.value for reason in exc.blocking_reason_codes]
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_import_review_confirmation",
            message="Строку нельзя подтвердить с выбранными значениями.",
            field_errors=field_errors or None,
        ) from exc
    except TransactionRuleError as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="invalid_import_review_rule",
            message="Правило не удалось сохранить.",
            field_errors={"rulePattern": [str(exc)]},
        ) from exc
    except RawTransactionReviewError as exc:
        raise _posting_item_not_found() from exc

    review = await _read_review(reader, context, document_id)
    return ImportReviewPostingMutationApiResponse(
        primary_document_id=document_id,
        item_id=item_id,
        operation_id=result.operation_id,
        updated_item_ids=sorted(result.updated_item_ids, key=str),
        replayed=result.replayed,
        reviews=[ImportReviewApiResponse.model_validate(review)],
    )


@router.post(
    "/{document_id}/items/{item_id}/undo-posting",
    response_model=ImportReviewPostingMutationApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def undo_import_review_posting(
    document_id: UUID,
    item_id: UUID,
    request: ImportReviewUndoApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_import_review_write_context),
    ],
    undo: Annotated[ImportReviewUndoService, Depends(get_import_review_undo_service)],
    reader: Annotated[ImportReviewReader, Depends(get_import_review_reader)],
) -> ImportReviewPostingMutationApiResponse:
    try:
        result = await undo.execute(
            context=context.workspace,
            command=UndoImportReviewPostingCommand(
                document_id=document_id,
                item_id=item_id,
                expected_operation_id=request.expected_operation_id,
            ),
        )
    except ImportReviewConfirmationConflictError as exc:
        raise _posting_conflict() from exc
    except LedgerPostingError as exc:
        raise _posting_conflict() from exc
    except RawTransactionReviewError as exc:
        raise _posting_item_not_found() from exc

    reviews = [
        ImportReviewApiResponse.model_validate(
            await _read_review(reader, context, affected_document_id),
        )
        for affected_document_id in sorted(result.affected_document_ids, key=str)
    ]
    return ImportReviewPostingMutationApiResponse(
        primary_document_id=document_id,
        item_id=item_id,
        operation_id=result.operation_id,
        updated_item_ids=sorted(result.updated_item_ids, key=str),
        replayed=result.replayed,
        reviews=reviews,
    )


async def _read_review(
    reader: ImportReviewReader,
    context: ApiRequestContext,
    document_id: UUID,
) -> ImportReviewReadModel:
    review = await reader.read(
        workspace_id=context.workspace.workspace.id,
        document_id=document_id,
        can_write=True,
    )
    if review is None:
        raise RuntimeError("Import review disappeared after posting mutation.")
    return review


def _posting_conflict() -> ApiError:
    return ApiError(
        status_code=status.HTTP_409_CONFLICT,
        code="import_review_posting_conflict",
        message="Строка или связанная операция уже изменилась. Обновите review.",
    )


def _posting_item_not_found() -> ApiError:
    return ApiError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="import_review_item_not_found",
        message="Строка import review не найдена.",
    )
