from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.features.accounts.models import Account
from app.features.categories.models import Category
from app.features.imports.models import RawTransaction
from app.features.properties.models import Property, PropertyStatus
from app.features.transaction_rules.models import TransactionRule
from app.features.transaction_rules.schemas import TransactionRuleDirectoryStatus


@dataclass(frozen=True)
class TransactionRuleDirectoryRow:
    rule: TransactionRule
    direct_raw_suggestion_count: int


@dataclass(frozen=True)
class TransactionRuleDirectoryResult:
    rows: Sequence[TransactionRuleDirectoryRow]
    page: int
    total: int
    all_count: int
    active_count: int
    disabled_count: int


class TransactionRuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_workspace(self, workspace_id: UUID) -> list[TransactionRule]:
        result = await self.session.execute(
            select(TransactionRule)
            .options(
                selectinload(TransactionRule.category),
                selectinload(TransactionRule.property),
                selectinload(TransactionRule.account),
            )
            .where(TransactionRule.workspace_id == workspace_id)
            .order_by(TransactionRule.priority, TransactionRule.name, TransactionRule.id)
        )
        return list(result.scalars().all())

    async def read_directory(
        self,
        *,
        workspace_id: UUID,
        search: str | None,
        category_id: UUID | None,
        status: TransactionRuleDirectoryStatus,
        page: int,
        page_size: int,
    ) -> TransactionRuleDirectoryResult:
        category = aliased(Category)
        property_ = aliased(Property)
        account = aliased(Account)
        base = (
            select(TransactionRule)
            .outerjoin(category, TransactionRule.category_id == category.id)
            .outerjoin(property_, TransactionRule.property_id == property_.id)
            .outerjoin(account, TransactionRule.account_id == account.id)
            .where(TransactionRule.workspace_id == workspace_id)
        )
        base = self._directory_filters(
            base,
            search=search,
            category_id=category_id,
            category=category,
            property_=property_,
            account=account,
        )
        filtered = (
            base.with_only_columns(
                TransactionRule.id.label("rule_id"),
                TransactionRule.is_active.label("is_active"),
            )
            .order_by(None)
            .subquery()
        )
        count_result = await self.session.execute(
            select(
                func.count(filtered.c.rule_id),
                func.count(filtered.c.rule_id).filter(filtered.c.is_active.is_(True)),
                func.count(filtered.c.rule_id).filter(filtered.c.is_active.is_(False)),
            )
        )
        all_count, active_count, disabled_count = count_result.one()

        page_query = base
        if status == TransactionRuleDirectoryStatus.ACTIVE:
            page_query = page_query.where(TransactionRule.is_active.is_(True))
            total = active_count
        elif status == TransactionRuleDirectoryStatus.DISABLED:
            page_query = page_query.where(TransactionRule.is_active.is_(False))
            total = disabled_count
        else:
            total = all_count
        total_pages = max(1, (total + page_size - 1) // page_size)
        normalized_page = min(page, total_pages)

        raw_count = (
            select(func.count(RawTransaction.id))
            .where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.suggested_by_rule_id == TransactionRule.id,
            )
            .correlate(TransactionRule)
            .scalar_subquery()
        )
        result = await self.session.execute(
            page_query.with_only_columns(TransactionRule, raw_count)
            .options(
                selectinload(TransactionRule.category),
                selectinload(TransactionRule.property),
                selectinload(TransactionRule.account),
            )
            .order_by(TransactionRule.priority, TransactionRule.name, TransactionRule.id)
            .offset((normalized_page - 1) * page_size)
            .limit(page_size)
        )
        return TransactionRuleDirectoryResult(
            rows=[
                TransactionRuleDirectoryRow(
                    rule=rule,
                    direct_raw_suggestion_count=direct_count,
                )
                for rule, direct_count in result.all()
            ],
            page=normalized_page,
            total=total,
            all_count=all_count,
            active_count=active_count,
            disabled_count=disabled_count,
        )

    async def list_directory_categories(
        self,
        *,
        workspace_id: UUID,
        current_ids: set[UUID],
    ) -> list[Category]:
        result = await self.session.execute(
            select(Category)
            .where(
                Category.workspace_id == workspace_id,
                or_(Category.is_active.is_(True), Category.id.in_(current_ids)),
            )
            .order_by(Category.is_active.desc(), Category.sort_order, Category.name, Category.id)
        )
        return list(result.scalars().all())

    async def list_directory_properties(
        self,
        *,
        workspace_id: UUID,
        current_ids: set[UUID],
    ) -> list[Property]:
        result = await self.session.execute(
            select(Property)
            .where(
                Property.workspace_id == workspace_id,
                or_(Property.status == PropertyStatus.ACTIVE, Property.id.in_(current_ids)),
            )
            .order_by(Property.status, Property.name, Property.id)
        )
        return list(result.scalars().all())

    @staticmethod
    def _directory_filters(
        query: Select[tuple[TransactionRule]],
        *,
        search: str | None,
        category_id: UUID | None,
        category: Any,
        property_: Any,
        account: Any,
    ) -> Select[tuple[TransactionRule]]:
        if category_id is not None:
            query = query.where(TransactionRule.category_id == category_id)
        if search is not None:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    TransactionRule.name.ilike(pattern),
                    TransactionRule.pattern.ilike(pattern),
                    category.name.ilike(pattern),
                    property_.name.ilike(pattern),
                    account.name.ilike(pattern),
                )
            )
        return query

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[TransactionRule]:
        result = await self.session.execute(
            select(TransactionRule)
            .where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.is_active.is_(True),
            )
            .order_by(TransactionRule.priority, TransactionRule.created_at)
        )
        return list(result.scalars().all())

    async def list_for_category(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
    ) -> list[TransactionRule]:
        result = await self.session.execute(
            select(TransactionRule)
            .options(
                selectinload(TransactionRule.category),
                selectinload(TransactionRule.property),
                selectinload(TransactionRule.account),
            )
            .where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.category_id == category_id,
            )
            .order_by(TransactionRule.priority, TransactionRule.name)
        )
        return list(result.scalars().all())

    async def list_category_preview(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        limit: int,
    ) -> list[TransactionRule]:
        result = await self.session.execute(
            select(TransactionRule)
            .where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.category_id == category_id,
            )
            .order_by(TransactionRule.priority, TransactionRule.name)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_category_rules(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
    ) -> tuple[int, int]:
        active_count = func.count(TransactionRule.id).filter(TransactionRule.is_active.is_(True))
        result = await self.session.execute(
            select(func.count(TransactionRule.id), active_count).where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.category_id == category_id,
            )
        )
        row = result.one()
        return row[0], row[1]

    async def get_for_workspace(
        self,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> TransactionRule | None:
        result = await self.session.execute(
            select(TransactionRule)
            .options(
                selectinload(TransactionRule.category),
                selectinload(TransactionRule.property),
                selectinload(TransactionRule.account),
            )
            .where(
                TransactionRule.id == rule_id,
                TransactionRule.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_for_workspace_for_update(
        self,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> TransactionRule | None:
        result = await self.session.execute(
            select(TransactionRule)
            .where(
                TransactionRule.id == rule_id,
                TransactionRule.workspace_id == workspace_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create(self, rule: TransactionRule) -> TransactionRule:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def count_direct_raw_suggestions(
        self,
        *,
        workspace_id: UUID,
        rule_id: UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count(RawTransaction.id)).where(
                RawTransaction.workspace_id == workspace_id,
                RawTransaction.suggested_by_rule_id == rule_id,
            )
        )
        return result.scalar_one()

    async def delete(self, rule: TransactionRule) -> None:
        await self.session.delete(rule)
        await self.session.flush()
