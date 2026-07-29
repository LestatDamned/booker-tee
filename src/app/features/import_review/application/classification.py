"""Classification references, draft evaluation, and category creation."""

from typing import Protocol
from uuid import UUID

from app.features.categories.models import Category, CategoryKind
from app.features.import_review.domain.classification import (
    ReviewConfirmabilityInput,
    evaluate_review_confirmability,
    resolve_review_classification,
)
from app.features.import_review.errors import ImportReviewDraftValidationError
from app.features.import_review.schemas.review import (
    ImportReviewCategoryReferenceDto,
    ImportReviewClassificationDto,
    ImportReviewConfirmabilityDto,
    ImportReviewDraftEvaluationDto,
    ImportReviewPropertyReferenceDto,
    ImportReviewReferencesDto,
    ImportReviewRuleSuggestionDto,
    ImportReviewSelectionDto,
)
from app.features.imports.models import RawTransaction, UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationType
from app.features.properties.models import Property


class ImportReviewClassificationDocumentSource(Protocol):
    async def get_document_for_workspace(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument | None: ...


class ImportReviewCategorySource(Protocol):
    async def list_active(self, workspace_id: UUID) -> list[Category]: ...

    async def get_for_workspace(
        self,
        workspace_id: UUID,
        category_id: UUID | None,
    ) -> Category | None: ...


class ImportReviewPropertySource(Protocol):
    async def list_active(self, workspace_id: UUID) -> list[Property]: ...

    async def get_for_workspace(
        self,
        workspace_id: UUID,
        property_id: UUID | None,
    ) -> Property | None: ...


class ImportReviewCategoryWriter(Protocol):
    async def create_custom(
        self,
        *,
        workspace_id: UUID,
        name: str,
        kind: CategoryKind,
        notes: str | None = None,
    ) -> Category: ...


class ImportReviewReferenceReader:
    def __init__(
        self,
        categories: ImportReviewCategorySource,
        properties: ImportReviewPropertySource,
    ) -> None:
        self._categories = categories
        self._properties = properties

    async def read(self, workspace_id: UUID) -> ImportReviewReferencesDto:
        categories = await self._categories.list_active(workspace_id)
        properties = await self._properties.list_active(workspace_id)
        return build_import_review_references(categories, properties)


class ImportReviewDraftEvaluator:
    def __init__(
        self,
        documents: ImportReviewClassificationDocumentSource,
        categories: ImportReviewCategorySource,
        properties: ImportReviewPropertySource,
    ) -> None:
        self._documents = documents
        self._categories = categories
        self._properties = properties

    async def evaluate(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        item_id: UUID,
        operation_type: OperationType | None,
        category_id: UUID | None,
        property_id: UUID | None,
    ) -> ImportReviewDraftEvaluationDto | None:
        document = await self._documents.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            return None
        row = next((item for item in document.raw_transactions if item.id == item_id), None)
        if row is None:
            return None
        category = await self._category(workspace_id, category_id)
        property_ = await self._property(workspace_id, property_id)
        return build_import_review_draft_evaluation(
            document=document,
            row=row,
            explicit_operation_type=operation_type,
            category_id=category.id if category is not None else None,
            property_id=property_.id if property_ is not None else None,
            category_is_uncategorized=(
                category is not None and category.system_key == "uncategorized"
            ),
        )

    async def _category(self, workspace_id: UUID, category_id: UUID | None) -> Category | None:
        try:
            return await self._categories.get_for_workspace(workspace_id, category_id)
        except ValueError as exc:
            raise ImportReviewDraftValidationError(
                field="categoryId",
                message="Категория недоступна в этом workspace.",
            ) from exc

    async def _property(self, workspace_id: UUID, property_id: UUID | None) -> Property | None:
        try:
            return await self._properties.get_for_workspace(workspace_id, property_id)
        except ValueError as exc:
            raise ImportReviewDraftValidationError(
                field="propertyId",
                message="Объект недоступен в этом workspace.",
            ) from exc


class ImportReviewCategoryCreator:
    def __init__(
        self,
        documents: ImportReviewClassificationDocumentSource,
        categories: ImportReviewCategoryWriter,
    ) -> None:
        self._documents = documents
        self._categories = categories

    async def create(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        item_id: UUID,
        name: str,
        kind: CategoryKind,
    ) -> ImportReviewCategoryReferenceDto | None:
        document = await self._documents.get_document_for_workspace(workspace_id, document_id)
        if document is None or not any(row.id == item_id for row in document.raw_transactions):
            return None
        category = await self._categories.create_custom(
            workspace_id=workspace_id,
            name=name,
            kind=kind,
        )
        return category_reference_dto(category)


def build_import_review_references(
    categories: list[Category],
    properties: list[Property],
) -> ImportReviewReferencesDto:
    return ImportReviewReferencesDto(
        categories=tuple(category_reference_dto(category) for category in categories),
        properties=tuple(
            ImportReviewPropertyReferenceDto(id=property_.id, name=property_.name)
            for property_ in properties
        ),
    )


def build_import_review_draft_evaluation(
    *,
    document: UploadedDocument,
    row: RawTransaction,
    explicit_operation_type: OperationType | None,
    category_id: UUID | None,
    property_id: UUID | None,
    category_is_uncategorized: bool,
) -> ImportReviewDraftEvaluationDto:
    classification = resolve_review_classification(
        explicit_operation_type=explicit_operation_type,
        suggested_operation_type=row.suggested_operation_type,
        amount=row.amount,
    )
    confirmability = evaluate_review_confirmability(
        ReviewConfirmabilityInput(
            status=row.status,
            normalization_error=row.normalization_error,
            operation_date=row.operation_date,
            operation_date_raw=row.operation_date_raw,
            amount=row.amount,
            currency=row.currency,
            source_account_id=row.account_id or document.account_id,
            counterparty_account_id=None,
            classification=classification,
            category_id=category_id,
            category_is_uncategorized=category_is_uncategorized,
        )
    )
    return ImportReviewDraftEvaluationDto(
        item_id=row.id,
        classification=ImportReviewClassificationDto(
            operation_type=classification.operation_type,
            source=classification.source,
        ),
        selection=ImportReviewSelectionDto(
            category_id=category_id,
            property_id=property_id,
        ),
        confirmability=ImportReviewConfirmabilityDto(
            can_confirm=confirmability.can_confirm,
            blocking_reason_codes=confirmability.blocking_reason_codes,
        ),
        rule_suggestion=rule_suggestion_dto(row),
    )


def category_reference_dto(category: Category) -> ImportReviewCategoryReferenceDto:
    return ImportReviewCategoryReferenceDto(
        id=category.id,
        name=category.name,
        kind=category.kind,
        is_uncategorized=category.system_key == "uncategorized",
    )


def rule_suggestion_dto(row: RawTransaction) -> ImportReviewRuleSuggestionDto:
    suggestion = row.raw_payload.get("rule_suggestion")
    application_mode = suggestion.get("application_mode") if isinstance(suggestion, dict) else None
    return ImportReviewRuleSuggestionDto(
        is_active=(
            row.status is RawTransactionStatus.SUGGESTED or row.suggested_by_rule_id is not None
        ),
        was_auto_applied=application_mode == "auto_apply",
        rule_id=row.suggested_by_rule_id,
        rule_name=_suggestion_text(suggestion, "rule_name"),
        pattern=_suggestion_text(suggestion, "pattern"),
        operation_type=row.suggested_operation_type,
        category_id=row.suggested_category_id,
        property_id=row.suggested_property_id,
    )


def _suggestion_text(suggestion: object, key: str) -> str | None:
    if not isinstance(suggestion, dict):
        return None
    value = suggestion.get(key)
    return value if isinstance(value, str) and value.strip() else None
