from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.features.categories.models import Category
from app.features.properties.models import Property, PropertyStatus
from app.features.transaction_rules.models import TransactionRule
from app.features.transaction_rules.repository import (
    TransactionRuleDirectoryResult,
    TransactionRuleRepository,
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
    TransactionRuleEnableBlockedReason,
    TransactionRuleOutcomeDto,
    TransactionRulePageDto,
    TransactionRuleReferenceDto,
    TransactionRuleReferencesDto,
    TransactionRuleSummaryCapabilitiesDto,
    TransactionRuleSummaryDto,
    TransactionRuleUsageDto,
)


class TransactionRuleDirectorySource(Protocol):
    async def read_directory(
        self,
        *,
        workspace_id: UUID,
        search: str | None,
        category_id: UUID | None,
        status: TransactionRuleDirectoryStatus,
        page: int,
        page_size: int,
    ) -> TransactionRuleDirectoryResult: ...

    async def list_directory_categories(
        self,
        *,
        workspace_id: UUID,
        current_ids: set[UUID],
    ) -> Sequence[Category]: ...

    async def list_directory_properties(
        self,
        *,
        workspace_id: UUID,
        current_ids: set[UUID],
    ) -> Sequence[Property]: ...


class TransactionRuleDirectoryReader:
    def __init__(self, source: TransactionRuleDirectorySource) -> None:
        self._source = source

    async def read(
        self,
        *,
        workspace_id: UUID,
        can_write: bool,
        search: str | None,
        category_id: UUID | None,
        status: TransactionRuleDirectoryStatus,
        page: int,
        page_size: int,
    ) -> TransactionRuleDirectoryDto:
        result = await self._source.read_directory(
            workspace_id=workspace_id,
            search=search,
            category_id=category_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        category_ids = {
            row.rule.category_id for row in result.rows if row.rule.category_id is not None
        }
        property_ids = {
            row.rule.property_id for row in result.rows if row.rule.property_id is not None
        }
        categories = await self._source.list_directory_categories(
            workspace_id=workspace_id,
            current_ids=category_ids,
        )
        properties = await self._source.list_directory_properties(
            workspace_id=workspace_id,
            current_ids=property_ids,
        )
        total_pages = max(1, (result.total + page_size - 1) // page_size)
        return TransactionRuleDirectoryDto(
            items=[
                transaction_rule_summary(
                    row.rule,
                    direct_raw_suggestion_count=row.direct_raw_suggestion_count,
                    can_write=can_write,
                )
                for row in result.rows
            ],
            page=TransactionRulePageDto(
                page=result.page,
                page_size=page_size,
                total=result.total,
                total_pages=total_pages,
                has_previous=result.page > 1,
                has_next=result.page < total_pages,
            ),
            counts=TransactionRuleCountsDto(
                all=result.all_count,
                active=result.active_count,
                disabled=result.disabled_count,
            ),
            applied_filters=TransactionRuleAppliedFiltersDto(
                q=search,
                category_id=category_id,
                status=status,
            ),
            references=TransactionRuleReferencesDto(
                categories=[category_reference(item) for item in categories],
                properties=[property_reference(item) for item in properties],
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


def transaction_rule_summary(
    rule: TransactionRule,
    *,
    direct_raw_suggestion_count: int,
    can_write: bool,
) -> TransactionRuleSummaryDto:
    enable_blocker = enable_blocked_reason(rule)
    delete_blocker = delete_blocked_reason(
        rule,
        direct_raw_suggestion_count=direct_raw_suggestion_count,
    )
    return TransactionRuleSummaryDto(
        id=rule.id,
        name=rule.name,
        priority=rule.priority,
        is_active=rule.is_active,
        updated_at=rule.updated_at,
        condition=TransactionRuleConditionDto(
            pattern=rule.pattern,
            match_type=rule.match_type,
            direction=rule.direction,
            account=account_reference(rule),
            amount_min=rule.amount_min,
            amount_max=rule.amount_max,
        ),
        outcome=TransactionRuleOutcomeDto(
            operation_type=rule.target_operation_type,
            category=category_reference(rule.category) if rule.category else None,
            property=property_reference(rule.property) if rule.property else None,
            application_mode=rule.application_mode,
            auto_description=rule.auto_description,
            affects_profit=rule.affects_profit,
        ),
        usage=TransactionRuleUsageDto(
            direct_raw_suggestion_count=direct_raw_suggestion_count,
        ),
        capabilities=TransactionRuleSummaryCapabilitiesDto(
            can_update=can_write,
            can_enable=can_write and not rule.is_active and enable_blocker is None,
            can_disable=can_write and rule.is_active,
            can_delete=can_write and delete_blocker is None,
            enable_blocked_reason_code=enable_blocker,
            delete_blocked_reason_code=delete_blocker,
        ),
    )


def enable_blocked_reason(
    rule: TransactionRule,
) -> TransactionRuleEnableBlockedReason | None:
    if rule.category is not None and not rule.category.is_active:
        return TransactionRuleEnableBlockedReason.CATEGORY_INACTIVE
    if rule.property is not None and rule.property.status != PropertyStatus.ACTIVE:
        return TransactionRuleEnableBlockedReason.PROPERTY_ARCHIVED
    if rule.account is not None and not rule.account.is_active:
        return TransactionRuleEnableBlockedReason.ACCOUNT_UNAVAILABLE
    return None


def delete_blocked_reason(
    rule: TransactionRule,
    *,
    direct_raw_suggestion_count: int,
) -> TransactionRuleDeleteBlockedReason | None:
    if rule.is_active:
        return TransactionRuleDeleteBlockedReason.ACTIVE_RULE
    if direct_raw_suggestion_count > 0:
        return TransactionRuleDeleteBlockedReason.RAW_SUGGESTIONS
    return None


def category_reference(category: Category) -> TransactionRuleReferenceDto:
    return TransactionRuleReferenceDto(
        id=category.id,
        name=category.name,
        is_active=category.is_active,
    )


def property_reference(property_: Property) -> TransactionRuleReferenceDto:
    return TransactionRuleReferenceDto(
        id=property_.id,
        name=property_.name,
        is_active=property_.status == PropertyStatus.ACTIVE,
    )


def account_reference(rule: TransactionRule) -> TransactionRuleReferenceDto | None:
    if rule.account is None:
        return None
    return TransactionRuleReferenceDto(
        id=rule.account.id,
        name=rule.account.name,
        is_active=rule.account.is_active,
    )


def build_transaction_rule_directory_reader(
    repository: TransactionRuleRepository,
) -> TransactionRuleDirectoryReader:
    return TransactionRuleDirectoryReader(repository)
