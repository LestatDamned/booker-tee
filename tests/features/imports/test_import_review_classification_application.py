from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from app.features.categories.models import CategoryKind
from app.features.categories.service import CategoryError
from app.features.imports.application.review.classification import (
    ImportReviewCategoryCreator,
    ImportReviewDraftEvaluator,
    ImportReviewDraftValidationError,
)
from app.features.imports.domain.review_classification import ReviewClassificationSource
from app.features.imports.domain.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationType


class DocumentSourceStub:
    def __init__(self, document: object | None) -> None:
        self.document = document

    async def get_document_for_workspace(self, *args: object) -> Any:
        return self.document


class CategorySourceStub:
    def __init__(self, category: object | None = None, *, invalid: bool = False) -> None:
        self.category = category
        self.invalid = invalid

    async def get_for_workspace(self, *args: object) -> Any:
        if self.invalid:
            raise CategoryError("not available")
        return self.category


class PropertySourceStub:
    async def get_for_workspace(self, *args: object) -> None:
        return None


class CategoryWriterStub:
    def __init__(self) -> None:
        self.calls = 0

    async def create_custom(self, **kwargs: object) -> Any:
        self.calls += 1
        return SimpleNamespace(
            id=uuid4(),
            name=kwargs["name"],
            kind=kwargs["kind"],
            system_key=None,
        )


@pytest.mark.asyncio
async def test_draft_evaluator_applies_explicit_classification_and_real_category() -> None:
    item = row()
    document = SimpleNamespace(
        id=uuid4(),
        account_id=uuid4(),
        raw_transactions=[item],
    )
    category_id = uuid4()
    category = SimpleNamespace(
        id=category_id,
        system_key=None,
    )
    evaluator = ImportReviewDraftEvaluator(
        cast(Any, DocumentSourceStub(document)),
        cast(Any, CategorySourceStub(category)),
        cast(Any, PropertySourceStub()),
    )

    result = await evaluator.evaluate(
        workspace_id=uuid4(),
        document_id=document.id,
        item_id=item.id,
        operation_type=OperationType.INCOME,
        category_id=category_id,
        property_id=None,
    )

    assert result is not None
    assert result.classification.operation_type is OperationType.INCOME
    assert result.classification.source is ReviewClassificationSource.EXPLICIT
    assert result.selection.category_id == category_id
    assert result.confirmability.can_confirm is True


@pytest.mark.asyncio
async def test_draft_evaluator_rejects_category_outside_workspace() -> None:
    item = row()
    evaluator = ImportReviewDraftEvaluator(
        cast(
            Any,
            DocumentSourceStub(SimpleNamespace(account_id=uuid4(), raw_transactions=[item])),
        ),
        cast(Any, CategorySourceStub(invalid=True)),
        cast(Any, PropertySourceStub()),
    )

    with pytest.raises(ImportReviewDraftValidationError) as error:
        await evaluator.evaluate(
            workspace_id=uuid4(),
            document_id=uuid4(),
            item_id=item.id,
            operation_type=OperationType.EXPENSE,
            category_id=uuid4(),
            property_id=None,
        )

    assert error.value.field == "categoryId"


@pytest.mark.asyncio
async def test_category_creator_does_not_create_for_unknown_review_item() -> None:
    writer = CategoryWriterStub()
    creator = ImportReviewCategoryCreator(
        cast(
            Any,
            DocumentSourceStub(SimpleNamespace(account_id=uuid4(), raw_transactions=[row()])),
        ),
        cast(Any, writer),
    )

    result = await creator.create(
        workspace_id=uuid4(),
        document_id=uuid4(),
        item_id=uuid4(),
        name="Комиссии",
        kind=CategoryKind.EXPENSE,
    )

    assert result is None
    assert writer.calls == 0


def row() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        status=RawTransactionStatus.MATCHED,
        normalization_error=None,
        operation_date=date(2026, 7, 21),
        operation_date_raw=None,
        amount=Decimal("100.00"),
        currency="RUB",
        account_id=None,
        suggested_operation_type=OperationType.EXPENSE,
        suggested_by_rule_id=None,
        raw_payload={},
    )
