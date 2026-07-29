from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import FastAPI

from api_client import ApiTestClient as TestClient
from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.import_review.dependencies import (
    get_import_review_category_creator,
    get_import_review_draft_evaluator,
)
from app.features.categories.models import CategoryKind
from app.features.categories.service import CategoryError
from app.features.import_review.domain.classification import ReviewClassificationSource
from app.features.import_review.errors import ImportReviewDraftValidationError
from app.features.import_review.schemas.review import (
    ImportReviewCategoryReferenceDto,
    ImportReviewClassificationDto,
    ImportReviewConfirmabilityDto,
    ImportReviewDraftEvaluationDto,
    ImportReviewRuleSuggestionDto,
    ImportReviewSelectionDto,
)
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


@dataclass
class DraftEvaluatorStub:
    result: ImportReviewDraftEvaluationDto | None
    error: ImportReviewDraftValidationError | None = None

    async def evaluate(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.kwargs = kwargs
        return self.result


@dataclass
class CategoryCreatorStub:
    result: ImportReviewCategoryReferenceDto | None
    error: CategoryError | None = None

    async def create(self, **kwargs):
        if self.error is not None:
            raise self.error
        self.kwargs = kwargs
        return self.result


def test_draft_evaluation_returns_server_owned_classification_and_capability() -> None:
    document_id = uuid4()
    item_id = uuid4()
    category_id = uuid4()
    evaluator = DraftEvaluatorStub(evaluation(item_id=item_id, category_id=category_id))
    app = mutation_app(evaluator=evaluator)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{document_id}/items/{item_id}/draft-evaluation",
            json={
                "operationType": "expense",
                "categoryId": str(category_id),
                "propertyId": None,
            },
        )

    assert response.status_code == 200
    assert response.json()["classification"] == {
        "operationType": "expense",
        "source": "explicit",
    }
    assert response.json()["confirmability"] == {
        "canConfirm": True,
        "blockingReasonCodes": [],
    }
    assert evaluator.kwargs["document_id"] == document_id
    assert evaluator.kwargs["category_id"] == category_id


def test_draft_evaluation_rejects_cross_workspace_reference_as_field_error() -> None:
    evaluator = DraftEvaluatorStub(
        result=None,
        error=ImportReviewDraftValidationError(
            field="categoryId",
            message="Категория недоступна в этом workspace.",
        ),
    )
    app = mutation_app(evaluator=evaluator)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{uuid4()}/items/{uuid4()}/draft-evaluation",
            json={"operationType": "expense", "categoryId": str(uuid4())},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_import_review_draft"
    assert response.json()["error"]["fieldErrors"] == {
        "categoryId": ["Категория недоступна в этом workspace."]
    }


def test_viewer_cannot_evaluate_or_create_draft_references() -> None:
    app = mutation_app(role=WorkspaceRole.VIEWER)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{uuid4()}/items/{uuid4()}/draft-evaluation",
            json={},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "import_review_write_forbidden"


def test_create_category_returns_small_reference_contract() -> None:
    document_id = uuid4()
    item_id = uuid4()
    category = ImportReviewCategoryReferenceDto(
        id=uuid4(),
        name="Комиссии",
        kind=CategoryKind.EXPENSE,
        is_uncategorized=False,
    )
    creator = CategoryCreatorStub(category)
    app = mutation_app(creator=creator)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{document_id}/items/{item_id}/categories",
            json={"name": "Комиссии", "kind": "expense"},
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(category.id),
        "name": "Комиссии",
        "kind": "expense",
        "isUncategorized": False,
    }
    assert creator.kwargs["document_id"] == document_id
    assert creator.kwargs["item_id"] == item_id


def test_create_category_keeps_name_error_in_typed_422() -> None:
    creator = CategoryCreatorStub(result=None, error=CategoryError("Category name is required."))
    app = mutation_app(creator=creator)

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/import-review/{uuid4()}/items/{uuid4()}/categories",
            json={"name": "  ", "kind": "expense"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["fieldErrors"] == {"name": ["Category name is required."]}


def mutation_app(
    *,
    evaluator: DraftEvaluatorStub | None = None,
    creator: CategoryCreatorStub | None = None,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: api_context(role)
    app.dependency_overrides[get_import_review_draft_evaluator] = lambda: (
        evaluator or DraftEvaluatorStub(None)
    )
    app.dependency_overrides[get_import_review_category_creator] = lambda: (
        creator or CategoryCreatorStub(None)
    )
    return app


def evaluation(
    *,
    item_id: UUID,
    category_id: UUID,
) -> ImportReviewDraftEvaluationDto:
    return ImportReviewDraftEvaluationDto(
        item_id=item_id,
        classification=ImportReviewClassificationDto(
            operation_type=OperationType.EXPENSE,
            source=ReviewClassificationSource.EXPLICIT,
        ),
        selection=ImportReviewSelectionDto(
            category_id=category_id,
            property_id=None,
        ),
        confirmability=ImportReviewConfirmabilityDto(
            can_confirm=True,
            blocking_reason_codes=(),
        ),
        rule_suggestion=ImportReviewRuleSuggestionDto(
            is_active=True,
            was_auto_applied=False,
            rule_id=uuid4(),
        ),
    )


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
