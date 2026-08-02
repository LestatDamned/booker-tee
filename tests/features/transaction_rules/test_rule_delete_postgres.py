import os
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.features.categories.models import Category, CategoryKind
from app.features.imports.documents.types import (
    ParseAttemptStatus,
    UploadedDocumentStatus,
)
from app.features.imports.models import ParseAttempt, RawTransaction, UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.models import OperationType
from app.features.transaction_rules.application.commands import CreateTransactionRuleCommand
from app.features.transaction_rules.application.rule_management import (
    TransactionRuleManagementUseCase,
)
from app.features.transaction_rules.errors import TransactionRuleCreateReplayConflictError
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.repository import TransactionRuleRepository
from app.features.transaction_rules.schemas import TransactionRuleDirectoryStatus
from app.features.users.models import User
from app.features.workspaces.domain.types import WorkspaceType
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL rule repository tests.",
)


@pytest.mark.asyncio
async def test_database_rejects_rule_delete_when_raw_provenance_is_added() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ids = await seed_rule_suggestion(sessions)

    try:
        async with sessions() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    delete(TransactionRule).where(TransactionRule.id == ids.rule_id)
                )
            await session.rollback()

        async with sessions() as session:
            raw_rule_id = await session.scalar(
                select(RawTransaction.suggested_by_rule_id).where(
                    RawTransaction.id == ids.raw_transaction_id
                )
            )
        assert raw_rule_id == ids.rule_id
    finally:
        await delete_rule_suggestion(sessions, ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_workspace_delete_still_cascades_raw_rows_and_rules() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ids = await seed_rule_suggestion(sessions)

    try:
        async with sessions() as session:
            await session.execute(delete(Workspace).where(Workspace.id == ids.workspace_id))
            await session.execute(delete(User).where(User.id == ids.user_id))
            await session.commit()

        async with sessions() as session:
            assert await session.get(TransactionRule, ids.rule_id) is None
            assert await session.get(RawTransaction, ids.raw_transaction_id) is None
    finally:
        await delete_rule_suggestion(sessions, ids)
        await engine.dispose()


@pytest.mark.asyncio
async def test_directory_sql_filters_counts_orders_pages_and_isolates_workspaces() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    local = await seed_rule_suggestion(sessions)
    foreign = await seed_rule_suggestion(sessions)
    category_id = uuid4()
    active_rule_id = uuid4()

    try:
        async with sessions() as session:
            local_rule = await session.get(TransactionRule, local.rule_id)
            assert local_rule is not None
            local_rule.category_id = category_id
            session.add_all(
                [
                    Category(
                        id=category_id,
                        workspace_id=local.workspace_id,
                        name="Marketplaces",
                        kind=CategoryKind.EXPENSE,
                    ),
                    TransactionRule(
                        id=active_rule_id,
                        workspace_id=local.workspace_id,
                        name="Alpha market rule",
                        pattern="TRAVEL",
                        priority=5,
                        is_active=True,
                        category_id=category_id,
                        created_by_user_id=local.user_id,
                    ),
                ]
            )
            await session.commit()

        async with sessions() as session:
            repository = TransactionRuleRepository(session)
            first = await repository.read_directory(
                workspace_id=local.workspace_id,
                search="market",
                category_id=category_id,
                status=TransactionRuleDirectoryStatus.ALL,
                page=1,
                page_size=1,
            )
            second = await repository.read_directory(
                workspace_id=local.workspace_id,
                search="market",
                category_id=category_id,
                status=TransactionRuleDirectoryStatus.ALL,
                page=2,
                page_size=1,
            )
            foreign_result = await repository.read_directory(
                workspace_id=foreign.workspace_id,
                search=None,
                category_id=None,
                status=TransactionRuleDirectoryStatus.ALL,
                page=1,
                page_size=50,
            )

        assert (first.all_count, first.active_count, first.disabled_count) == (2, 1, 1)
        assert first.total == 2
        assert first.rows[0].rule.id == active_rule_id
        assert second.rows[0].rule.id == local.rule_id
        assert second.rows[0].direct_raw_suggestion_count == 1
        assert foreign_result.total == 1
        assert foreign_result.rows[0].rule.id == foreign.rule_id
    finally:
        await delete_rule_suggestion(sessions, local)
        await delete_rule_suggestion(sessions, foreign)
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_idempotency_replays_exact_payload_and_rejects_key_reuse() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ids = await seed_rule_suggestion(sessions)
    key = uuid4()

    try:
        async with sessions() as session:
            user = await session.get(User, ids.user_id)
            workspace = await session.get(Workspace, ids.workspace_id)
            assert user is not None and workspace is not None
            context = WorkspaceContext(
                user=user,
                workspace=workspace,
                membership=WorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=user.id,
                ),
            )
            command = CreateTransactionRuleCommand(
                name="Idempotent API rule",
                pattern="API RETRY",
                match_type=TransactionRuleMatchType.CONTAINS,
                category_id=None,
                property_id=None,
                target_operation_type=OperationType.EXPENSE,
                direction=MoneyDirection.OUTFLOW,
            )
            management = TransactionRuleManagementUseCase(session)
            created = await management.create_rule_idempotently(
                context=context,
                command=command,
                idempotency_key=key,
            )
            replay = await management.create_rule_idempotently(
                context=context,
                command=command,
                idempotency_key=key,
            )

            assert created.replayed is False
            assert replay.replayed is True
            assert replay.rule.id == created.rule.id
            with pytest.raises(TransactionRuleCreateReplayConflictError):
                await management.create_rule_idempotently(
                    context=context,
                    command=replace(command, pattern="DIFFERENT"),
                    idempotency_key=key,
                )

            await session.execute(
                delete(TransactionRule).where(TransactionRule.id == created.rule.id)
            )
            await session.commit()
    finally:
        await delete_rule_suggestion(sessions, ids)
        await engine.dispose()


class RuleSuggestionIds:
    def __init__(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        document_id: UUID,
        rule_id: UUID,
        raw_transaction_id: UUID,
    ) -> None:
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.document_id = document_id
        self.rule_id = rule_id
        self.raw_transaction_id = raw_transaction_id


async def seed_rule_suggestion(sessions) -> RuleSuggestionIds:
    user_id = uuid4()
    workspace_id = uuid4()
    document_id = uuid4()
    attempt_id = uuid4()
    rule_id = uuid4()
    raw_transaction_id = uuid4()
    async with sessions() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    email=f"rule-delete-{user_id}@example.test",
                    password_hash="hash",
                    name="Rule delete guard",
                ),
                Workspace(
                    id=workspace_id,
                    owner_id=user_id,
                    name="Rule delete guard",
                    type=WorkspaceType.PERSONAL,
                    default_currency="RUB",
                ),
                UploadedDocument(
                    id=document_id,
                    workspace_id=workspace_id,
                    status=UploadedDocumentStatus.REQUIRES_REVIEW,
                    original_filename="rule-delete.pdf",
                    storage_key=f"tests/rule-delete/{document_id}",
                    sha256_hash=uuid4().hex * 2,
                ),
                ParseAttempt(
                    id=attempt_id,
                    workspace_id=workspace_id,
                    uploaded_document_id=document_id,
                    parser_name="rule-delete-test",
                    status=ParseAttemptStatus.REQUIRES_REVIEW,
                ),
                TransactionRule(
                    id=rule_id,
                    workspace_id=workspace_id,
                    name="Referenced rule",
                    pattern="REFERENCE",
                    is_active=False,
                    created_by_user_id=user_id,
                ),
                RawTransaction(
                    id=raw_transaction_id,
                    workspace_id=workspace_id,
                    uploaded_document_id=document_id,
                    parse_attempt_id=attempt_id,
                    row_index=0,
                    status=RawTransactionStatus.SUGGESTED,
                    raw_payload={"rule_suggestion": {"rule_id": str(rule_id)}},
                    suggested_by_rule_id=rule_id,
                ),
            ]
        )
        await session.commit()
    return RuleSuggestionIds(
        user_id=user_id,
        workspace_id=workspace_id,
        document_id=document_id,
        rule_id=rule_id,
        raw_transaction_id=raw_transaction_id,
    )


async def delete_rule_suggestion(sessions, ids: RuleSuggestionIds) -> None:
    async with sessions() as session:
        await session.execute(
            delete(RawTransaction).where(RawTransaction.id == ids.raw_transaction_id)
        )
        await session.execute(delete(TransactionRule).where(TransactionRule.id == ids.rule_id))
        await session.execute(
            delete(UploadedDocument).where(UploadedDocument.id == ids.document_id)
        )
        await session.execute(delete(Workspace).where(Workspace.id == ids.workspace_id))
        await session.execute(delete(User).where(User.id == ids.user_id))
        await session.commit()
