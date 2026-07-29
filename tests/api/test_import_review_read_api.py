from dataclasses import replace
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI

from api_client import ApiTestClient as TestClient
from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.import_review.dependencies import (
    get_import_review_confirmation_service,
    get_import_review_lifecycle_service,
    get_import_review_reader,
    get_import_review_rule_application_service,
    get_import_review_transfer_service,
    get_import_review_undo_service,
)
from app.features.import_review.application.classification import (
    ImportReviewClassificationDto,
    ImportReviewConfirmabilityDto,
    ImportReviewReferencesDto,
    ImportReviewRuleSuggestionDto,
    ImportReviewSelectionDto,
)
from app.features.import_review.application.confirmation import (
    ConfirmImportReviewItemCommand,
    ImportReviewConfirmationConflictError,
    ImportReviewConfirmationResult,
    ImportReviewConfirmationValidationError,
)
from app.features.import_review.application.duplicate_evidence import (
    ImportReviewDuplicateCandidateDto,
    ImportReviewDuplicateEvidenceDto,
    ImportReviewDuplicateMatchingField,
    ImportReviewDuplicateMatchReasonCode,
)
from app.features.import_review.application.lifecycle import (
    ImportReviewLifecycleResult,
)
from app.features.import_review.application.read_model import (
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
from app.features.import_review.application.rules import (
    ImportReviewRuleApplicationResult,
)
from app.features.import_review.application.transfer_options import (
    ImportReviewTransferAccountDto,
    ImportReviewTransferDirection,
    ImportReviewTransferOptionsDto,
)
from app.features.import_review.application.transfers import (
    ImportReviewTransferResult,
    MatchImportReviewRawRowCommand,
)
from app.features.import_review.application.undo import (
    ImportReviewUndoResult,
    UndoImportReviewPostingCommand,
)
from app.features.import_review.application.validation_read_model import (
    ImportReviewBalanceChainDto,
    ImportReviewRowProblemCode,
    ImportReviewRowProblemDto,
    ImportReviewValidationDto,
    ImportReviewValidationReasonCode,
)
from app.features.import_review.domain.classification import ReviewClassificationSource
from app.features.import_review.domain.confirmability import ReviewBlockingReasonCode
from app.features.import_review.domain.lifecycle import (
    ImportReviewLifecycleAction,
    ImportReviewLifecycleConflictError,
)
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.statements.types import RawTransactionStatus
from app.features.imports.statements.validation import StatementValidationStatus
from app.features.ledger.domain.types import OperationType
from app.features.ledger.errors import LedgerPostingError
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
    assert payload["items"][0]["posting"] == {
        "operationId": None,
        "canUndo": False,
    }
    assert payload["items"][0]["duplicateEvidence"] is None
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


def test_import_review_exposes_transfer_account_references() -> None:
    review = review_model()
    assert review.document.source_account is not None
    source = ImportReviewTransferAccountDto(
        id=review.document.source_account.id,
        name=review.document.source_account.name,
        currency=review.document.source_account.currency,
    )
    counterparty = ImportReviewTransferAccountDto(
        id=uuid4(),
        name="Накопительный счёт",
        currency="RUB",
    )
    item = replace(
        review.items[0],
        transfer=ImportReviewTransferOptionsDto(
            direction=ImportReviewTransferDirection.SOURCE_TO_COUNTERPARTY,
            ordinary_operation_type=OperationType.EXPENSE,
            source_account=source,
            counterparty_account=counterparty,
            accounts=(),
            raw_row_candidates=(),
            existing_operation_candidates=(),
        ),
    )
    review = replace(review, items=[item])
    app, _, _ = import_review_app(review)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/import-review/{review.document.id}")

    assert response.status_code == 200
    transfer = response.json()["items"][0]["transfer"]
    assert transfer["sourceAccount"] == {
        "id": str(source.id),
        "name": "Основной",
        "currency": "RUB",
    }
    assert transfer["counterpartyAccount"] == {
        "id": str(counterparty.id),
        "name": "Накопительный счёт",
        "currency": "RUB",
    }


def test_import_review_exposes_server_owned_duplicate_evidence() -> None:
    review = review_model()
    candidate_document_id = uuid4()
    candidate_item_id = uuid4()
    item = replace(
        review.items[0],
        status=RawTransactionStatus.POSSIBLE_DUPLICATE,
        duplicate_evidence=ImportReviewDuplicateEvidenceDto(
            reason_code=(ImportReviewDuplicateMatchReasonCode.SAME_ACCOUNT_DATE_AMOUNT_CURRENCY),
            matching_fields=(
                ImportReviewDuplicateMatchingField.ACCOUNT,
                ImportReviewDuplicateMatchingField.OPERATION_DATE,
                ImportReviewDuplicateMatchingField.AMOUNT,
                ImportReviewDuplicateMatchingField.CURRENCY,
            ),
            candidate=ImportReviewDuplicateCandidateDto(
                item_id=candidate_item_id,
                document_id=candidate_document_id,
                document_filename="previous-statement.pdf",
                operation_id=None,
                operation_date=date(2026, 7, 20),
                description="Покупка",
                amount=Decimal("-1250.50"),
                currency="RUB",
            ),
        ),
    )
    review = replace(review, items=[item])
    app, _, _ = import_review_app(review)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/import-review/{review.document.id}")

    assert response.status_code == 200
    evidence = response.json()["items"][0]["duplicateEvidence"]
    assert evidence == {
        "reasonCode": "same_account_date_amount_currency",
        "matchingFields": ["account", "operation_date", "amount", "currency"],
        "candidate": {
            "itemId": str(candidate_item_id),
            "documentId": str(candidate_document_id),
            "documentFilename": "previous-statement.pdf",
            "operationId": None,
            "operationDate": "2026-07-20",
            "description": "Покупка",
            "amount": "-1250.50",
            "currency": "RUB",
        },
    }


def test_import_review_hides_document_outside_workspace_as_not_found() -> None:
    app, reader, _ = import_review_app(None)

    with TestClient(app) as client:
        response = client.get(f"/api/v1/import-review/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "import_review_not_found"
    assert len(reader.workspace_ids) == 1


class TransferServiceStub:
    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.command = None

    async def execute(self, *, context, command):
        self.command = command
        if self.error is not None:
            raise self.error
        return self.result


class LifecycleServiceStub:
    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.command = None

    async def execute(self, *, workspace_id, command):
        self.command = command
        if self.error is not None:
            raise self.error
        return self.result


class PostingServiceStub:
    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.command = None

    async def execute(self, *, context, command):
        self.command = command
        if self.error is not None:
            raise self.error
        return self.result


class RuleApplicationServiceStub:
    def __init__(self, result: ImportReviewRuleApplicationResult) -> None:
        self.result = result
        self.workspace_id: UUID | None = None
        self.document_id: UUID | None = None

    async def execute(self, *, workspace_id: UUID, document_id: UUID):
        self.workspace_id = workspace_id
        self.document_id = document_id
        return self.result


class MultiReviewReaderStub:
    def __init__(self, reviews: list[ImportReviewReadModel]) -> None:
        self.reviews = {review.document.id: review for review in reviews}

    async def read(self, *, workspace_id, document_id, can_write):
        return self.reviews.get(document_id)


def test_transfer_match_returns_both_affected_document_reviews() -> None:
    primary = review_model()
    paired = replace(
        review_model(),
        document=replace(review_model().document, id=uuid4()),
    )
    item_id = primary.items[0].id
    paired_item_id = paired.items[0].id
    result = ImportReviewTransferResult(
        updated_item_ids=frozenset({item_id, paired_item_id}),
        affected_document_ids=frozenset({primary.document.id, paired.document.id}),
    )
    service = TransferServiceStub(result=result)
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_transfer_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub(
        [primary, paired]
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{primary.document.id}/items/{item_id}/transfer",
            headers={"Idempotency-Key": str(uuid4())},
            json={"kind": "raw_row_match", "matchedItemId": str(paired_item_id)},
        )

    assert response.status_code == 200
    assert {review["document"]["id"] for review in response.json()["reviews"]} == {
        str(primary.document.id),
        str(paired.document.id),
    }
    assert isinstance(service.command, MatchImportReviewRawRowCommand)
    assert service.command.matched_item_id == paired_item_id


def test_apply_rules_returns_summary_and_authoritative_review() -> None:
    review = review_model()
    item_id = review.items[0].id
    service = RuleApplicationServiceStub(
        ImportReviewRuleApplicationResult(
            checked_count=1,
            suggested_count=1,
            updated_item_ids=frozenset({item_id}),
        )
    )
    context = api_context(WorkspaceRole.OWNER)
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_import_review_rule_application_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        response = client.post(f"/api/v1/import-review/{review.document.id}/apply-rules")

    assert response.status_code == 200
    payload = response.json()
    assert payload["documentId"] == str(review.document.id)
    assert payload["checkedCount"] == 1
    assert payload["suggestedCount"] == 1
    assert payload["updatedItemIds"] == [str(item_id)]
    assert payload["review"]["document"]["id"] == str(review.document.id)
    assert service.workspace_id == context.workspace.workspace.id
    assert service.document_id == review.document.id


def test_transfer_request_rejects_impossible_field_combination() -> None:
    review = review_model()
    service = TransferServiceStub()
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_transfer_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{review.items[0].id}/transfer",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "kind": "new_transfer",
                "counterpartyAccountId": str(uuid4()),
                "matchedItemId": str(uuid4()),
            },
        )

    assert response.status_code == 422
    assert service.command is None


def test_transfer_maps_stale_candidate_to_conflict() -> None:
    review = review_model()
    service = TransferServiceStub(error=LedgerPostingError("stale"))
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_transfer_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{review.items[0].id}/transfer",
            headers={"Idempotency-Key": str(uuid4())},
            json={"kind": "existing_operation_link", "operationId": str(uuid4())},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "import_review_transfer_stale"


def test_lifecycle_action_returns_authoritative_review_snapshot() -> None:
    review = review_model()
    item = review.items[0]
    service = LifecycleServiceStub(
        result=ImportReviewLifecycleResult(
            item_id=item.id,
            document_id=review.document.id,
            replayed=False,
        )
    )
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_lifecycle_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{item.id}/lifecycle",
            json={"action": "mark_unique", "expectedStatus": "possible_duplicate"},
        )

    assert response.status_code == 200
    assert response.json()["itemId"] == str(item.id)
    assert response.json()["review"]["document"]["id"] == str(review.document.id)
    assert service.command is not None
    assert service.command.action is ImportReviewLifecycleAction.MARK_UNIQUE
    assert service.command.expected_status is RawTransactionStatus.POSSIBLE_DUPLICATE


def test_lifecycle_stale_state_returns_typed_conflict() -> None:
    review = review_model()
    service = LifecycleServiceStub(error=ImportReviewLifecycleConflictError("changed"))
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_lifecycle_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{review.items[0].id}/lifecycle",
            json={"action": "ignore", "expectedStatus": "matched"},
        )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "import_review_lifecycle_conflict"


def test_lifecycle_requires_expected_status() -> None:
    review = review_model()
    service = LifecycleServiceStub()
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_lifecycle_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{review.items[0].id}/lifecycle",
            json={"action": "ignore"},
        )

    assert response.status_code == 422
    assert service.command is None


def test_lifecycle_requires_write_permission() -> None:
    review = review_model()
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.VIEWER)
    app.dependency_overrides[get_import_review_lifecycle_service] = lambda: LifecycleServiceStub()
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        forbidden = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{review.items[0].id}/lifecycle",
            json={"action": "ignore", "expectedStatus": "matched"},
        )

    assert forbidden.status_code == 403


def test_confirmation_returns_authoritative_review_and_typed_result() -> None:
    review = review_model()
    item = review.items[0]
    operation_id = uuid4()
    service = PostingServiceStub(
        result=ImportReviewConfirmationResult(
            document_id=review.document.id,
            item_id=item.id,
            operation_id=operation_id,
            updated_item_ids=frozenset({item.id}),
            replayed=False,
        )
    )
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_confirmation_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{item.id}/confirm",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "operationType": "expense",
                "categoryId": str(uuid4()),
                "propertyId": None,
                "expectedStatus": "matched",
                "rememberRule": False,
                "rulePattern": None,
            },
        )

    assert response.status_code == 200
    assert response.json()["operationId"] == str(operation_id)
    assert response.json()["reviews"][0]["document"]["id"] == str(review.document.id)
    assert isinstance(service.command, ConfirmImportReviewItemCommand)
    assert service.command.expected_status is RawTransactionStatus.MATCHED


def test_confirmation_requires_manual_pattern_when_creating_rule() -> None:
    review = review_model()
    item = review.items[0]
    service = PostingServiceStub()
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_confirmation_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{item.id}/confirm",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "operationType": "expense",
                "categoryId": str(uuid4()),
                "expectedStatus": "matched",
                "rememberRule": True,
                "rulePattern": "   ",
            },
        )

    assert response.status_code == 422
    assert service.command is None


def test_confirmation_maps_stale_and_capability_failures() -> None:
    review = review_model()
    item = review.items[0]
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    conflict = PostingServiceStub(error=ImportReviewConfirmationConflictError("stale"))
    app.dependency_overrides[get_import_review_confirmation_service] = lambda: conflict
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])
    request = {
        "operationType": "expense",
        "categoryId": str(uuid4()),
        "expectedStatus": "matched",
    }

    with TestClient(app) as client:
        stale = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{item.id}/confirm",
            headers={"Idempotency-Key": str(uuid4())},
            json=request,
        )

    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "import_review_posting_conflict"

    invalid = PostingServiceStub(
        error=ImportReviewConfirmationValidationError(
            blocking_reason_codes=(ReviewBlockingReasonCode.MISSING_CATEGORY,)
        )
    )
    app.dependency_overrides[get_import_review_confirmation_service] = lambda: invalid
    with TestClient(app) as client:
        rejected = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{item.id}/confirm",
            headers={"Idempotency-Key": str(uuid4())},
            json=request,
        )

    assert rejected.status_code == 422
    assert rejected.json()["error"]["fieldErrors"] == {"item": ["missing_category"]}


def test_confirmation_requires_idempotency_header_and_write_permission() -> None:
    review = review_model()
    item = review.items[0]
    service = PostingServiceStub()
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_confirmation_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])
    request = {
        "operationType": "expense",
        "categoryId": str(uuid4()),
        "expectedStatus": "matched",
    }

    with TestClient(app) as client:
        missing_key = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{item.id}/confirm",
            json=request,
        )

    assert missing_key.status_code == 422
    assert service.command is None

    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.VIEWER)
    with TestClient(app) as client:
        forbidden = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{item.id}/confirm",
            headers={"Idempotency-Key": str(uuid4())},
            json=request,
        )

    assert forbidden.status_code == 403


def test_undo_posting_returns_reconciled_review() -> None:
    review = review_model()
    item = review.items[0]
    operation_id = uuid4()
    service = PostingServiceStub(
        result=ImportReviewUndoResult(
            document_id=review.document.id,
            item_id=item.id,
            operation_id=operation_id,
            affected_document_ids=frozenset({review.document.id}),
            updated_item_ids=frozenset({item.id}),
            replayed=False,
        )
    )
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(WorkspaceRole.OWNER)
    app.dependency_overrides[get_import_review_undo_service] = lambda: service
    app.dependency_overrides[get_import_review_reader] = lambda: MultiReviewReaderStub([review])

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{review.document.id}/items/{item.id}/undo-posting",
            json={"expectedOperationId": str(operation_id)},
        )

    assert response.status_code == 200
    assert response.json()["operationId"] == str(operation_id)
    assert isinstance(service.command, UndoImportReviewPostingCommand)


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
