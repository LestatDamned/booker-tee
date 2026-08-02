from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from app.api.dependencies import get_api_request_context
from app.api.v1.transaction_rules.dependencies import (
    get_transaction_rule_directory_reader,
    get_transaction_rule_mutation_service,
)
from app.features.ledger.models import OperationType
from app.features.transaction_rules.application.mutations import (
    TransactionRuleCreateResult,
    TransactionRuleEditResult,
    TransactionRuleSeedDefaultsResult,
)
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.schemas import (
    TransactionRuleAppliedFiltersDto,
    TransactionRuleConditionDto,
    TransactionRuleCountsDto,
    TransactionRuleDeleteBlockedReason,
    TransactionRuleDirectoryCapabilitiesDto,
    TransactionRuleDirectoryDto,
    TransactionRuleDirectoryReadonlyReason,
    TransactionRuleDirectoryStatus,
    TransactionRuleOutcomeDto,
    TransactionRulePageDto,
    TransactionRuleReferenceDto,
    TransactionRuleReferencesDto,
    TransactionRuleSummaryCapabilitiesDto,
    TransactionRuleSummaryDto,
    TransactionRuleUsageDto,
)
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


class TransactionRuleDirectoryReaderStub:
    def __init__(self, directory: TransactionRuleDirectoryDto) -> None:
        self.directory = directory
        self.calls: list[dict[str, object]] = []

    async def read(self, **kwargs: object) -> TransactionRuleDirectoryDto:
        self.calls.append(kwargs)
        return self.directory


class TransactionRuleMutationServiceStub:
    def __init__(self, item: TransactionRuleSummaryDto) -> None:
        self.item = item
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.error: Exception | None = None

    async def create(self, **kwargs: object) -> TransactionRuleCreateResult:
        self.calls.append(("create", kwargs))
        if self.error is not None:
            raise self.error
        return TransactionRuleCreateResult(item=self.item, replayed=False)

    async def seed_defaults(self, **kwargs: object) -> TransactionRuleSeedDefaultsResult:
        self.calls.append(("seed", kwargs))
        if self.error is not None:
            raise self.error
        return TransactionRuleSeedDefaultsResult(
            created_rules=3,
            existing_rules=50,
            created_categories=1,
        )

    async def get_for_edit(self, **kwargs: object) -> TransactionRuleEditResult:
        self.calls.append(("edit", kwargs))
        if self.error is not None:
            raise self.error
        return TransactionRuleEditResult(
            item=self.item,
            references=directory().references,
        )

    async def update(self, **kwargs: object) -> TransactionRuleSummaryDto:
        self.calls.append(("update", kwargs))
        if self.error is not None:
            raise self.error
        return self.item


def transaction_rules_app(
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, TransactionRuleDirectoryReaderStub, UUID]:
    context = api_context(role=role)
    can_write = role in {
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.EDITOR,
    }
    reader = TransactionRuleDirectoryReaderStub(directory(can_write=can_write))
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_transaction_rule_directory_reader] = lambda: reader
    return app, reader, context.workspace.workspace.id


def transaction_rules_mutation_app(
    *, role: WorkspaceRole = WorkspaceRole.OWNER
) -> tuple[FastAPI, TransactionRuleMutationServiceStub]:
    app, reader, _ = transaction_rules_app(role=role)
    mutations = TransactionRuleMutationServiceStub(reader.directory.items[0])
    app.dependency_overrides[get_transaction_rule_mutation_service] = lambda: mutations
    return app, mutations


def directory(*, can_write: bool = True) -> TransactionRuleDirectoryDto:
    category = TransactionRuleReferenceDto(id=uuid4(), name="Маркетплейсы", is_active=True)
    property_ = TransactionRuleReferenceDto(id=uuid4(), name="Квартира", is_active=False)
    return TransactionRuleDirectoryDto(
        items=[
            TransactionRuleSummaryDto(
                id=uuid4(),
                name="OZON → Маркетплейсы",
                priority=20,
                is_active=True,
                updated_at=datetime(2026, 8, 2, 9, 0, tzinfo=UTC),
                condition=TransactionRuleConditionDto(
                    pattern="OZON",
                    match_type=TransactionRuleMatchType.CONTAINS,
                    direction=MoneyDirection.OUTFLOW,
                    account=None,
                    amount_min=Decimal("100.00"),
                    amount_max=None,
                ),
                outcome=TransactionRuleOutcomeDto(
                    operation_type=OperationType.EXPENSE,
                    category=category,
                    property=property_,
                    application_mode=TransactionRuleApplicationMode.SUGGEST,
                    auto_description="Покупка на маркетплейсе",
                    affects_profit=True,
                ),
                usage=TransactionRuleUsageDto(direct_raw_suggestion_count=4),
                capabilities=TransactionRuleSummaryCapabilitiesDto(
                    can_update=can_write,
                    can_enable=False,
                    can_disable=can_write,
                    can_delete=False,
                    enable_blocked_reason_code=None,
                    delete_blocked_reason_code=TransactionRuleDeleteBlockedReason.ACTIVE_RULE,
                ),
            )
        ],
        page=TransactionRulePageDto(
            page=1,
            page_size=50,
            total=1,
            total_pages=1,
            has_previous=False,
            has_next=False,
        ),
        counts=TransactionRuleCountsDto(all=1, active=1, disabled=0),
        applied_filters=TransactionRuleAppliedFiltersDto(
            q="ozon",
            category_id=category.id,
            status=TransactionRuleDirectoryStatus.ACTIVE,
        ),
        references=TransactionRuleReferencesDto(
            categories=[category],
            properties=[property_],
        ),
        capabilities=TransactionRuleDirectoryCapabilitiesDto(
            can_create=can_write,
            can_seed_defaults=can_write,
            readonly_reason_code=(
                None
                if can_write
                else TransactionRuleDirectoryReadonlyReason.FINANCIAL_WRITE_FORBIDDEN
            ),
        ),
    )
