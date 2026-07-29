from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.features.import_review.application.commands.confirmation import (
    ConfirmImportReviewItemCommand,
    ImportReviewConfirmationActor,
    ImportReviewConfirmationConflictError,
    ImportReviewConfirmationResult,
    ImportReviewConfirmationService,
    ImportReviewConfirmationValidationError,
)
from app.features.import_review.domain.confirmability import ReviewBlockingReasonCode
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.models import RawTransaction
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.features.transaction_rules.errors import TransactionRuleError


class SessionStub:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class ImportRepositoryStub:
    def __init__(self, row: object, *, duplicate: bool = False) -> None:
        self.row = row
        self.duplicate = duplicate

    async def get_raw_transaction_for_workspace(self, *args: object) -> object:
        return self.row

    async def get_document_for_workspace_for_update(self, *args: object) -> object:
        return cast(Any, self.row).uploaded_document

    async def mark_document_status(self, document: object, status: object) -> None:
        cast(Any, document).status = status

    async def has_confirmed_raw_transaction_with_dedupe_hash(
        self,
        **kwargs: object,
    ) -> bool:
        return self.duplicate

    async def link_raw_transaction_to_operation(
        self,
        raw_transaction: object,
        *,
        operation_id: UUID,
    ) -> None:
        cast(Any, raw_transaction).status = RawTransactionStatus.CONFIRMED
        cast(Any, raw_transaction).linked_operation_id = operation_id


class LedgerRepositoryStub:
    def __init__(self, operation: object | None = None) -> None:
        self.operation = operation

    async def get_operation_by_idempotency_key(self, **kwargs: object) -> object | None:
        return self.operation


class ReferenceResolverStub:
    def __init__(self, account_id: UUID) -> None:
        self.account = SimpleNamespace(id=account_id, currency="RUB")
        self.account_ids: list[UUID] = []

    async def get_account(
        self,
        workspace_id: UUID,
        account_id: UUID,
    ) -> object:
        self.account_ids.append(account_id)
        return self.account

    async def get_category_or_uncategorized(
        self,
        workspace_id: UUID,
        category_id: UUID,
    ) -> object:
        return SimpleNamespace(id=category_id, system_key=None)

    async def get_property(self, workspace_id: UUID, property_id: UUID | None) -> object | None:
        return SimpleNamespace(id=property_id) if property_id is not None else None


class PostingStub:
    def __init__(self, operation_id: UUID) -> None:
        self.operation_id = operation_id
        self.calls: list[dict[str, object]] = []

    async def post_imported_income_expense(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return SimpleNamespace(id=self.operation_id)


class RuleCreatorStub:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    async def create_and_apply(self, **kwargs: object) -> object:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return SimpleNamespace(updated_raw_transaction_ids=frozenset({uuid4()}))


@pytest.mark.asyncio
async def test_confirmation_posts_once_with_server_checked_references() -> None:
    row = confirmable_row()
    command = confirmation_command(row)
    operation_id = uuid4()
    session = SessionStub()
    service = confirmation_service(session, row, operation_id=operation_id)

    result = await service.execute(context=workspace_context(), command=command)

    posting = cast(PostingStub, service._actor._posting)
    references = cast(ReferenceResolverStub, service._actor._references)
    assert result.operation_id == operation_id
    assert result.replayed is False
    assert result.updated_item_ids == frozenset({row.id})
    assert references.account_ids == [row.account_id]
    assert posting.calls[0]["account"] is references.account
    assert posting.calls[0]["idempotency_key"] == command.idempotency_key
    assert cast(Any, posting.calls[0]["category"]).id == command.category_id
    assert row.status is RawTransactionStatus.CONFIRMED
    assert row.linked_operation_id == operation_id
    assert session.commits == 1


@pytest.mark.asyncio
async def test_confirmation_replays_same_committed_idempotency_key() -> None:
    row = confirmable_row(status=RawTransactionStatus.CONFIRMED)
    command = confirmation_command(row, expected_status=RawTransactionStatus.MATCHED)
    operation_id = uuid4()
    service = confirmation_service(SessionStub(), row, operation_id=operation_id)
    row.linked_operation_id = operation_id
    service._actor._ledger = cast(
        Any,
        LedgerRepositoryStub(
            SimpleNamespace(
                id=operation_id,
                status=OperationStatus.CONFIRMED,
                idempotency_fingerprint=service._actor.fingerprint(command),
                extra_metadata={
                    "raw_transaction_id": str(row.id),
                    "uploaded_document_id": str(row.uploaded_document_id),
                },
            )
        ),
    )

    result = await service.execute(context=workspace_context(), command=command)

    assert result.replayed is True
    assert cast(PostingStub, service._actor._posting).calls == []


@pytest.mark.asyncio
async def test_confirmation_rejects_stale_status_and_dedupe() -> None:
    row = confirmable_row(status=RawTransactionStatus.NEEDS_REVIEW)
    command = confirmation_command(row, expected_status=RawTransactionStatus.MATCHED)
    stale = confirmation_service(SessionStub(), row)

    with pytest.raises(ImportReviewConfirmationConflictError, match="status has changed"):
        await stale.execute(context=workspace_context(), command=command)

    row.status = RawTransactionStatus.MATCHED
    duplicate = confirmation_service(SessionStub(), row, duplicate=True)
    with pytest.raises(ImportReviewConfirmationConflictError, match="dedupe hash"):
        await duplicate.execute(
            context=workspace_context(),
            command=confirmation_command(row),
        )


@pytest.mark.asyncio
async def test_confirmation_rechecks_amount_type_and_rolls_back_rule_failure() -> None:
    row = confirmable_row()
    invalid = confirmation_service(SessionStub(), row)
    invalid_command = confirmation_command(row, operation_type=OperationType.INCOME)

    with pytest.raises(ImportReviewConfirmationValidationError) as invalid_result:
        await invalid.execute(context=workspace_context(), command=invalid_command)

    assert invalid_result.value.blocking_reason_codes == (
        ReviewBlockingReasonCode.OPERATION_TYPE_AMOUNT_MISMATCH,
    )

    session = SessionStub()
    service = confirmation_service(session, row)
    service._actor._rule_creator = cast(
        Any,
        RuleCreatorStub(TransactionRuleError("bad pattern")),
    )
    with pytest.raises(TransactionRuleError, match="bad pattern"):
        await service.execute(
            context=workspace_context(),
            command=confirmation_command(row, remember_rule=True),
        )

    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_confirmation_requires_manual_rule_pattern_before_posting() -> None:
    row = confirmable_row()
    service = confirmation_service(SessionStub(), row)
    command = confirmation_command(row, remember_rule=True)
    command = replace(command, rule_pattern="   ")

    with pytest.raises(ImportReviewConfirmationValidationError) as result:
        await service.execute(context=workspace_context(), command=command)

    assert result.value.field_errors == {
        "rulePattern": ["Укажите текст, по которому определять похожие строки."]
    }
    assert cast(PostingStub, service._actor._posting).calls == []


@pytest.mark.asyncio
async def test_confirmation_actor_leaves_transaction_to_outer_workflow() -> None:
    row = confirmable_row()
    session = SessionStub()
    actor = confirmation_actor(session, row)

    await actor.apply(
        context=workspace_context(),
        command=replace(confirmation_command(row), operation_type=None),
    )

    assert session.commits == 0
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_confirmation_service_recovers_idempotent_replay_after_integrity_race() -> None:
    row = confirmable_row()
    command = confirmation_command(row)
    replay = ImportReviewConfirmationResult(
        document_id=row.uploaded_document_id,
        item_id=row.id,
        operation_id=uuid4(),
        updated_item_ids=frozenset({row.id}),
        replayed=True,
    )

    class RacingActorStub:
        async def apply(self, **_kwargs: object) -> object:
            raise IntegrityError("insert operation", {}, Exception("unique violation"))

        async def find_replay(self, **_kwargs: object) -> object:
            return replay

    session = SessionStub()
    service = ImportReviewConfirmationService(
        cast(Any, session),
        cast(Any, RacingActorStub()),
    )

    result = await service.execute(context=workspace_context(), command=command)

    assert result is replay
    assert session.commits == 0
    assert session.rollbacks == 1


def confirmation_service(
    session: SessionStub,
    row: object,
    *,
    operation_id: UUID | None = None,
    duplicate: bool = False,
) -> ImportReviewConfirmationService:
    actor = confirmation_actor(
        session,
        row,
        operation_id=operation_id,
        duplicate=duplicate,
    )
    return ImportReviewConfirmationService(cast(Any, session), actor)


def confirmation_actor(
    session: SessionStub,
    row: object,
    *,
    operation_id: UUID | None = None,
    duplicate: bool = False,
) -> ImportReviewConfirmationActor:
    actor = ImportReviewConfirmationActor(cast(Any, session))
    imports = ImportRepositoryStub(row, duplicate=duplicate)
    actor._documents = cast(Any, imports)
    actor._review_repository = cast(Any, imports)
    actor._ledger = cast(Any, LedgerRepositoryStub())
    actor._references = cast(
        Any,
        ReferenceResolverStub(cast(Any, row).account_id),
    )
    actor._posting = cast(Any, PostingStub(operation_id or uuid4()))
    actor._rule_creator = cast(Any, RuleCreatorStub())
    return actor


def confirmation_command(
    row: object,
    *,
    expected_status: RawTransactionStatus = RawTransactionStatus.MATCHED,
    operation_type: OperationType = OperationType.EXPENSE,
    remember_rule: bool = False,
) -> ConfirmImportReviewItemCommand:
    return ConfirmImportReviewItemCommand(
        document_id=cast(Any, row).uploaded_document_id,
        item_id=cast(Any, row).id,
        operation_type=operation_type,
        category_id=uuid4(),
        property_id=None,
        expected_status=expected_status,
        remember_rule=remember_rule,
        rule_pattern="Магазин" if remember_rule else None,
        idempotency_key=uuid4(),
    )


def confirmable_row(
    *,
    status: RawTransactionStatus = RawTransactionStatus.MATCHED,
) -> SimpleNamespace:
    document_id = uuid4()
    account_id = uuid4()
    document = SimpleNamespace(
        id=document_id,
        account_id=account_id,
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        parse_attempts=[],
        raw_transactions=[],
    )
    row = SimpleNamespace(
        id=uuid4(),
        uploaded_document_id=document_id,
        uploaded_document=document,
        status=status,
        linked_operation_id=None,
        normalization_error=None,
        operation_date=date(2026, 7, 21),
        operation_date_raw=None,
        posting_date=None,
        amount=Decimal("-1250.50"),
        currency="RUB",
        description_normalized="Магазин",
        description_raw="Магазин",
        balance_after=Decimal("10000.00"),
        account_id=account_id,
        suggested_operation_type=None,
        suggested_category_id=None,
        suggested_property_id=None,
        suggested_by_rule_id=None,
        raw_payload={},
        dedupe_hash="same-row",
    )
    document.raw_transactions = [row]
    return row


def workspace_context() -> Any:
    return SimpleNamespace(
        workspace=SimpleNamespace(id=uuid4()),
        user=SimpleNamespace(id=uuid4()),
    )


def test_confirmed_dedupe_hash_has_database_race_guard() -> None:
    table = cast(Any, RawTransaction.__table__)
    index = next(
        index
        for index in table.indexes
        if index.name == "uq_raw_transactions_workspace_confirmed_dedupe_hash"
    )

    assert index.unique is True
    assert str(index.dialect_options["postgresql"]["where"]) == (
        "status = 'confirmed' AND dedupe_hash IS NOT NULL"
    )
