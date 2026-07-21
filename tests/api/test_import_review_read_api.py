from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.import_review.dependencies import get_import_review_reader
from app.features.imports.application.review.classification import (
    ImportReviewClassificationDto,
    ImportReviewConfirmabilityDto,
    ImportReviewReferencesDto,
    ImportReviewRuleSuggestionDto,
    ImportReviewSelectionDto,
)
from app.features.imports.application.review.read_model import (
    ImportReviewAccountDto,
    ImportReviewCapabilitiesDto,
    ImportReviewDocumentDto,
    ImportReviewItemDto,
    ImportReviewNormalizedSourceDto,
    ImportReviewQueueDto,
    ImportReviewRawSourceDto,
    ImportReviewReadModel,
    ImportReviewReadonlyReasonCode,
)
from app.features.imports.application.review.validation_read_model import (
    ImportReviewBalanceChainDto,
    ImportReviewRowProblemCode,
    ImportReviewRowProblemDto,
    ImportReviewValidationDto,
    ImportReviewValidationReasonCode,
)
from app.features.imports.domain.review_classification import ReviewClassificationSource
from app.features.imports.domain.review_confirmability import ReviewBlockingReasonCode
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.domain.validation import StatementValidationStatus
from app.features.imports.models import UploadedDocumentStatus
from app.features.ledger.domain.types import OperationType
from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


class ImportReviewReaderStub:
    def __init__(self, review: ImportReviewReadModel | None) -> None:
        self.review = review
        self.workspace_ids: list[UUID] = []
        self.can_write_values: list[bool] = []

    async def read(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        can_write: bool,
    ) -> ImportReviewReadModel | None:
        self.workspace_ids.append(workspace_id)
        self.can_write_values.append(can_write)
        if self.review is None or self.review.document.id != document_id:
            return None
        capabilities = ImportReviewCapabilitiesDto(
            can_write=can_write,
            readonly_reason_code=(
                None if can_write else ImportReviewReadonlyReasonCode.FINANCIAL_WRITE_FORBIDDEN
            ),
        )
        return replace(self.review, capabilities=capabilities)


def test_import_review_returns_typed_queue_and_source_data() -> None:
    review = review_model()
    app, reader, workspace_id = import_review_app(review)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/import-review/{review.document.id}")

    assert response.status_code == 200
    payload = response.json()
    assert review.document.source_account is not None
    assert payload["document"] == {
        "id": str(review.document.id),
        "filename": "statement.pdf",
        "status": "requires_review",
        "sourceAccount": {
            "id": str(review.document.source_account.id),
            "name": "Основной",
            "currency": "RUB",
        },
    }
    assert payload["queue"] == {
        "total": 1,
        "completed": 0,
        "remaining": 1,
        "firstRemainingItemId": str(review.items[0].id),
        "orderedItemIds": [str(review.items[0].id)],
    }
    assert payload["items"][0]["status"] == "matched"
    assert payload["items"][0]["isTerminal"] is False
    assert payload["items"][0]["isReviewable"] is True
    assert payload["items"][0]["raw"]["amount"] == "-1250,50"
    assert payload["items"][0]["normalized"]["amount"] == "-1250.50"
    assert payload["items"][0]["classification"] == {
        "operationType": "expense",
        "source": "inferred",
    }
    assert payload["items"][0]["confirmability"] == {
        "canConfirm": False,
        "blockingReasonCodes": ["missing_category"],
    }
    assert payload["references"] == {"categories": [], "properties": []}
    assert payload["validation"]["reasonCode"] == "control_totals_mismatch"
    assert payload["validation"]["calculatedTotalOutflow"] == "1250.50"
    assert payload["validation"]["rowProblems"][0]["itemId"] == str(review.items[0].id)
    assert payload["validation"]["rowProblems"][0]["expectedBalanceAfter"] == "9000.00"
    assert payload["capabilities"] == {
        "canWrite": True,
        "readonlyReasonCode": None,
    }
    assert reader.workspace_ids == [workspace_id]
    assert reader.can_write_values == [True]


def test_import_review_exposes_readonly_capability_for_viewer() -> None:
    review = review_model()
    app, reader, _ = import_review_app(review, role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/import-review/{review.document.id}")

    assert response.status_code == 200
    assert response.json()["capabilities"] == {
        "canWrite": False,
        "readonlyReasonCode": "financial_write_forbidden",
    }
    assert reader.can_write_values == [False]


def test_import_review_hides_document_outside_workspace_as_not_found() -> None:
    app, reader, _ = import_review_app(None)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/import-review/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "import_review_not_found"
    assert len(reader.workspace_ids) == 1


def import_review_app(
    review: ImportReviewReadModel | None,
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, ImportReviewReaderStub, UUID]:
    app = create_app()
    context = api_context(role)
    reader = ImportReviewReaderStub(review)
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_import_review_reader] = lambda: reader
    return app, reader, context.workspace.workspace.id


def api_context(role: WorkspaceRole) -> ApiRequestContext:
    user_id = uuid4()
    workspace_id = uuid4()
    user = User(id=user_id, email="max@example.test", name="Max", password_hash="hash")
    workspace = Workspace(
        id=workspace_id,
        owner_id=user_id,
        name="Дом",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
    )
    membership = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    return ApiRequestContext(
        workspace=WorkspaceContext(user=user, workspace=workspace, membership=membership),
        csrf_token="csrf-token",
    )


def review_model() -> ImportReviewReadModel:
    account = ImportReviewAccountDto(id=uuid4(), name="Основной", currency="RUB")
    item_id = uuid4()
    return ImportReviewReadModel(
        document=ImportReviewDocumentDto(
            id=uuid4(),
            filename="statement.pdf",
            status=UploadedDocumentStatus.REQUIRES_REVIEW,
            source_account=account,
        ),
        queue=ImportReviewQueueDto(
            total=1,
            completed=0,
            remaining=1,
            first_remaining_item_id=item_id,
            ordered_item_ids=(item_id,),
        ),
        items=[
            ImportReviewItemDto(
                id=item_id,
                row_index=1,
                status=RawTransactionStatus.MATCHED,
                is_terminal=False,
                is_reviewable=True,
                source_account=account,
                raw=ImportReviewRawSourceDto(
                    operation_date="20.07.2026",
                    posting_date=None,
                    description="Покупка",
                    amount="-1250,50",
                    currency="RUB",
                    balance_after="10000,00",
                    account_hint="*1234",
                ),
                normalized=ImportReviewNormalizedSourceDto(
                    operation_date=date(2026, 7, 20),
                    posting_date=None,
                    description="Покупка",
                    amount=Decimal("-1250.50"),
                    currency="RUB",
                    balance_after=Decimal("10000.00"),
                ),
                classification=ImportReviewClassificationDto(
                    operation_type=OperationType.EXPENSE,
                    source=ReviewClassificationSource.INFERRED,
                ),
                selection=ImportReviewSelectionDto(
                    category_id=None,
                    property_id=None,
                ),
                confirmability=ImportReviewConfirmabilityDto(
                    can_confirm=False,
                    blocking_reason_codes=(ReviewBlockingReasonCode.MISSING_CATEGORY,),
                ),
                rule_suggestion=ImportReviewRuleSuggestionDto(
                    is_active=False,
                    was_auto_applied=False,
                    rule_id=None,
                ),
            )
        ],
        references=ImportReviewReferencesDto(categories=(), properties=()),
        validation=ImportReviewValidationDto(
            status=StatementValidationStatus.MISMATCH,
            reason_code=ImportReviewValidationReasonCode.CONTROL_TOTALS_MISMATCH,
            currency="RUB",
            extracted_count=1,
            normalized_count=1,
            needs_review_count=0,
            calculated_total_inflow=Decimal("0.00"),
            calculated_total_outflow=Decimal("1250.50"),
            ignored_total_inflow=Decimal("0.00"),
            ignored_total_outflow=Decimal("0.00"),
            statement_total_inflow=Decimal("0.00"),
            statement_total_outflow=Decimal("1200.00"),
            opening_balance=Decimal("10250.50"),
            closing_balance=Decimal("9000.00"),
            inflow_difference=Decimal("0.00"),
            outflow_difference=Decimal("50.50"),
            unexplained_inflow_difference=Decimal("0.00"),
            unexplained_outflow_difference=Decimal("50.50"),
            balance_chain=ImportReviewBalanceChainDto(
                status=StatementValidationStatus.MISMATCH,
                direction="ascending",
                checked_pair_count=1,
                mismatch_count=1,
            ),
            row_problems=(
                ImportReviewRowProblemDto(
                    item_id=item_id,
                    row_index=1,
                    previous_item_id=uuid4(),
                    previous_row_index=0,
                    code=ImportReviewRowProblemCode.BALANCE_CHAIN_MISMATCH,
                    expected_balance_after=Decimal("9000.00"),
                    actual_balance_after=Decimal("9050.50"),
                ),
            ),
        ),
        capabilities=ImportReviewCapabilitiesDto(
            can_write=True,
            readonly_reason_code=None,
        ),
    )
