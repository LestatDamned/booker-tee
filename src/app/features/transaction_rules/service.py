import re
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category, CategoryKind
from app.features.categories.repository import CategoryRepository
from app.features.categories.service import CategoryError, CategoryService
from app.features.imports.models import RawTransaction, RawTransactionStatus
from app.features.imports.repository import ImportRepository
from app.features.ledger.models import OperationType
from app.features.properties.service import PropertyError, PropertyService
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.repository import TransactionRuleRepository
from app.features.workspaces.service import WorkspaceContext


class TransactionRuleError(ValueError):
    pass


@dataclass(frozen=True)
class ExpobankFixtureRuleSeed:
    category_name: str
    category_kind: CategoryKind
    pattern: str
    direction: MoneyDirection = MoneyDirection.OUTFLOW


@dataclass(frozen=True)
class RuleApplicationSummary:
    checked_count: int
    suggested_count: int


EXPOBANK_FIXTURE_RULE_SEEDS = [
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "KRASNOE&BELOE"),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "SBER*5411*SAMOKA"),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "SAMOKA"),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "KOMANDOR"),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, 'ООО "АГРОТОРГ"'),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "MAGNIT MM"),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "KRASNYJ YAR"),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "PYATEROCHKA"),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "KUPEC"),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "ALLEYA"),
    ExpobankFixtureRuleSeed("Продукты", CategoryKind.EXPENSE, "YUMAMART"),
    ExpobankFixtureRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "KAZANKEBAB"),
    ExpobankFixtureRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "ALIBI"),
    ExpobankFixtureRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "KAKAYA-TO RYUMOCHNAYA"),
    ExpobankFixtureRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "KULA BAR"),
    ExpobankFixtureRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "AMMA INDIYA"),
    ExpobankFixtureRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "DO YOU D ALEKSEEVA"),
    ExpobankFixtureRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "Veesp"),
    ExpobankFixtureRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, 'ООО "ВИСП"'),
    ExpobankFixtureRuleSeed("Авто", CategoryKind.EXPENSE, "GAZPROMNEFT"),
    ExpobankFixtureRuleSeed("Связь", CategoryKind.EXPENSE, "VTB Mobile"),
    ExpobankFixtureRuleSeed("Связь", CategoryKind.EXPENSE, "Telecoma"),
    ExpobankFixtureRuleSeed("Сервисы", CategoryKind.EXPENSE, 'ООО БАНК "ПЭЙДЖИН"'),
    ExpobankFixtureRuleSeed("Сервисы", CategoryKind.EXPENSE, "SMART GLOCAL SERVICES"),
]

RULE_SUGGESTABLE_STATUSES = {
    RawTransactionStatus.NORMALIZED,
    RawTransactionStatus.SUGGESTED,
    RawTransactionStatus.MATCHED,
    RawTransactionStatus.NEEDS_REVIEW,
    RawTransactionStatus.POSSIBLE_DUPLICATE,
}

MERCHANT_PATTERN = re.compile(r"\sв\s(.+?)\sпо\s(?:карте|платежу)", re.IGNORECASE)


class TransactionRuleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.categories = CategoryRepository(session)
        self.imports = ImportRepository(session)
        self.rules = TransactionRuleRepository(session)

    async def list_rules(self, workspace_id: UUID) -> list[TransactionRule]:
        return await self.rules.list_for_workspace(workspace_id)

    async def create_rule(
        self,
        *,
        context: WorkspaceContext,
        name: str | None,
        pattern: str,
        match_type: TransactionRuleMatchType,
        category_id: UUID | None,
        property_id: UUID | None,
        target_operation_type: OperationType | None,
        direction: MoneyDirection,
        account_id: UUID | None = None,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
        auto_description: str | None = None,
        affects_profit: bool | None = True,
        application_mode: TransactionRuleApplicationMode = TransactionRuleApplicationMode.SUGGEST,
    ) -> TransactionRule:
        try:
            category = await CategoryService(self.session).get_for_workspace(
                context.workspace.id,
                category_id,
            )
            property_ = await PropertyService(self.session).get_for_workspace(
                context.workspace.id,
                property_id,
            )
        except (CategoryError, PropertyError) as exc:
            raise TransactionRuleError(str(exc)) from exc

        cleaned_pattern = clean_rule_pattern(pattern)
        cleaned_name = clean_rule_name(name) or build_rule_name(
            pattern=cleaned_pattern,
            match_type=match_type,
            category_name=category.name if category else None,
            target_operation_type=target_operation_type,
        )
        existing = await self.rules.find_existing(
            workspace_id=context.workspace.id,
            pattern=cleaned_pattern,
            category_id=category.id if category else None,
        )
        if existing is not None:
            return existing

        rule = await self.rules.create(
            TransactionRule(
                workspace_id=context.workspace.id,
                name=cleaned_name,
                match_type=match_type,
                pattern=cleaned_pattern,
                application_mode=application_mode,
                account_id=account_id,
                amount_min=amount_min,
                amount_max=amount_max,
                direction=direction,
                target_operation_type=target_operation_type,
                category_id=category.id if category else None,
                property_id=property_.id if property_ else None,
                auto_description=clean_description(auto_description),
                affects_profit=affects_profit,
                created_by_user_id=context.user.id,
            )
        )
        await self.session.commit()
        return rule

    async def update_rule(
        self,
        *,
        context: WorkspaceContext,
        rule_id: UUID,
        name: str | None,
        pattern: str,
        match_type: TransactionRuleMatchType,
        category_id: UUID | None,
        property_id: UUID | None,
        target_operation_type: OperationType | None,
        direction: MoneyDirection,
        application_mode: TransactionRuleApplicationMode,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
    ) -> TransactionRule:
        rule = await self.rules.get_for_workspace(context.workspace.id, rule_id)
        if rule is None:
            raise TransactionRuleError("Правило не найдено в этом workspace.")
        try:
            category = await CategoryService(self.session).get_for_workspace(
                context.workspace.id,
                category_id,
            )
            property_ = await PropertyService(self.session).get_for_workspace(
                context.workspace.id,
                property_id,
            )
        except (CategoryError, PropertyError) as exc:
            raise TransactionRuleError(str(exc)) from exc
        cleaned_pattern = clean_rule_pattern(pattern)
        rule.name = clean_rule_name(name) or build_rule_name(
            pattern=cleaned_pattern,
            match_type=match_type,
            category_name=category.name if category else None,
            target_operation_type=target_operation_type,
        )
        rule.pattern = cleaned_pattern
        rule.match_type = match_type
        rule.category_id = category.id if category else None
        rule.property_id = property_.id if property_ else None
        rule.target_operation_type = target_operation_type
        rule.direction = direction
        rule.application_mode = application_mode
        rule.amount_min = amount_min
        rule.amount_max = amount_max
        await self.session.commit()
        return rule

    async def set_rule_active(
        self,
        *,
        workspace_id: UUID,
        rule_id: UUID,
        is_active: bool,
    ) -> TransactionRule:
        rule = await self.rules.get_for_workspace(workspace_id, rule_id)
        if rule is None:
            raise TransactionRuleError("Правило не найдено в этом workspace.")
        rule.is_active = is_active
        await self.session.commit()
        return rule

    async def delete_rule(self, *, workspace_id: UUID, rule_id: UUID) -> None:
        rule = await self.rules.get_for_workspace(workspace_id, rule_id)
        if rule is None:
            raise TransactionRuleError("Правило не найдено в этом workspace.")
        await self.rules.delete(rule)
        await self.session.commit()

    async def create_rule_from_raw_confirmation(
        self,
        *,
        context: WorkspaceContext,
        document_id: UUID,
        raw_transaction_id: UUID,
        category_id: UUID,
        property_id: UUID | None,
        pattern: str | None,
    ) -> TransactionRule:
        raw_transaction = await self.imports.get_raw_transaction_for_workspace(
            context.workspace.id,
            document_id,
            raw_transaction_id,
        )
        if raw_transaction is None:
            raise TransactionRuleError("Raw transaction row was not found.")
        inferred_pattern = pattern or infer_rule_pattern(raw_transaction)
        target_operation_type = operation_type_for_raw_transaction(raw_transaction)
        return await self.create_rule(
            context=context,
            name=f"{inferred_pattern} -> category",
            pattern=inferred_pattern,
            match_type=TransactionRuleMatchType.CONTAINS,
            category_id=category_id,
            property_id=property_id,
            target_operation_type=target_operation_type,
            direction=direction_for_raw_transaction(raw_transaction),
            application_mode=TransactionRuleApplicationMode.SUGGEST,
        )

    async def seed_expobank_fixture_rules(self, context: WorkspaceContext) -> list[TransactionRule]:
        created_or_existing: list[TransactionRule] = []
        for seed in EXPOBANK_FIXTURE_RULE_SEEDS:
            category = await self._get_or_create_category(
                workspace_id=context.workspace.id,
                name=seed.category_name,
                kind=seed.category_kind,
            )
            existing = await self.rules.find_existing(
                workspace_id=context.workspace.id,
                pattern=seed.pattern,
                category_id=category.id,
            )
            if existing is not None:
                existing.application_mode = TransactionRuleApplicationMode.AUTO_APPLY
                created_or_existing.append(existing)
                continue
            created_or_existing.append(
                await self.rules.create(
                    TransactionRule(
                        workspace_id=context.workspace.id,
                        name=f"{seed.pattern} -> {seed.category_name}",
                        match_type=TransactionRuleMatchType.CONTAINS,
                        pattern=seed.pattern,
                        application_mode=TransactionRuleApplicationMode.AUTO_APPLY,
                        direction=seed.direction,
                        target_operation_type=OperationType.EXPENSE,
                        category_id=category.id,
                        affects_profit=True,
                        created_by_user_id=context.user.id,
                    )
                )
            )
        await self.session.commit()
        return created_or_existing

    async def apply_rules_to_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> RuleApplicationSummary:
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise TransactionRuleError("Document was not found.")
        summary = await self.apply_rules_to_raw_transactions(
            workspace_id=workspace_id,
            raw_transactions=document.raw_transactions,
        )
        await self.session.commit()
        return summary

    async def apply_rules_to_raw_transactions(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> RuleApplicationSummary:
        rules = await self.rules.list_active_for_workspace(workspace_id)
        suggested_count = 0
        checked_count = 0
        for raw_transaction in raw_transactions:
            if not can_suggest_raw_transaction(raw_transaction):
                continue
            checked_count += 1
            clear_rule_suggestion(raw_transaction)
            for rule in rules:
                if rule_matches_raw_transaction(rule, raw_transaction):
                    apply_rule_suggestion(raw_transaction, rule)
                    suggested_count += 1
                    break
        await self.session.flush()
        return RuleApplicationSummary(
            checked_count=checked_count,
            suggested_count=suggested_count,
        )

    async def _get_or_create_category(
        self,
        *,
        workspace_id: UUID,
        name: str,
        kind: CategoryKind,
    ) -> Category:
        category = await self.categories.get_by_name_for_workspace(workspace_id, name)
        if category is not None:
            return category
        return await self.categories.create(
            Category(
                workspace_id=workspace_id,
                name=name,
                kind=kind,
                is_system=False,
                sort_order=300,
            )
        )


def rule_matches_raw_transaction(rule: TransactionRule, raw_transaction: RawTransaction) -> bool:
    if raw_transaction.workspace_id != rule.workspace_id:
        return False
    if rule.account_id is not None and raw_transaction.account_id != rule.account_id:
        return False
    if not direction_matches(rule.direction, raw_transaction.amount):
        return False
    if not amount_matches(rule, raw_transaction.amount):
        return False

    description = normalized_text(
        raw_transaction.description_normalized or raw_transaction.description_raw
    )
    pattern = normalized_text(rule.pattern)
    if not description or not pattern:
        return False
    if rule.match_type == TransactionRuleMatchType.EXACT:
        return description == pattern
    return pattern in description


def apply_rule_suggestion(raw_transaction: RawTransaction, rule: TransactionRule) -> None:
    raw_transaction.suggested_category_id = rule.category_id
    raw_transaction.suggested_property_id = rule.property_id
    raw_transaction.suggested_operation_type = rule.target_operation_type
    raw_transaction.suggested_by_rule_id = rule.id
    raw_transaction.raw_payload = {
        **(raw_transaction.raw_payload or {}),
        "rule_suggestion": {
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "pattern": rule.pattern,
            "application_mode": rule.application_mode.value,
        },
    }
    if raw_transaction.status == RawTransactionStatus.NORMALIZED:
        raw_transaction.status = RawTransactionStatus.SUGGESTED


def clear_rule_suggestion(raw_transaction: RawTransaction) -> None:
    raw_transaction.suggested_category_id = None
    raw_transaction.suggested_property_id = None
    raw_transaction.suggested_operation_type = None
    raw_transaction.suggested_by_rule_id = None
    payload = dict(raw_transaction.raw_payload or {})
    payload.pop("rule_suggestion", None)
    raw_transaction.raw_payload = payload
    if raw_transaction.status == RawTransactionStatus.SUGGESTED:
        raw_transaction.status = RawTransactionStatus.NORMALIZED


def rule_suggestion_auto_applies(raw_transaction: RawTransaction) -> bool:
    payload = raw_transaction.raw_payload or {}
    suggestion = payload.get("rule_suggestion")
    if not isinstance(suggestion, dict):
        return False
    return suggestion.get("application_mode") == TransactionRuleApplicationMode.AUTO_APPLY.value


def can_suggest_raw_transaction(raw_transaction: RawTransaction) -> bool:
    return (
        raw_transaction.linked_operation_id is None
        and raw_transaction.status in RULE_SUGGESTABLE_STATUSES
    )


def direction_matches(direction: MoneyDirection, amount: Decimal | None) -> bool:
    if direction == MoneyDirection.ANY:
        return True
    if amount is None:
        return False
    if direction == MoneyDirection.INFLOW:
        return amount > Decimal("0.00")
    return amount < Decimal("0.00")


def amount_matches(rule: TransactionRule, amount: Decimal | None) -> bool:
    if amount is None:
        return rule.amount_min is None and rule.amount_max is None
    absolute_amount = abs(amount)
    if rule.amount_min is not None and absolute_amount < rule.amount_min:
        return False
    if rule.amount_max is not None and absolute_amount > rule.amount_max:
        return False
    return True


def direction_for_raw_transaction(raw_transaction: RawTransaction) -> MoneyDirection:
    if raw_transaction.amount is None:
        return MoneyDirection.ANY
    if raw_transaction.amount > Decimal("0.00"):
        return MoneyDirection.INFLOW
    if raw_transaction.amount < Decimal("0.00"):
        return MoneyDirection.OUTFLOW
    return MoneyDirection.ANY


def operation_type_for_raw_transaction(raw_transaction: RawTransaction) -> OperationType | None:
    if raw_transaction.amount is None:
        return None
    if raw_transaction.amount > Decimal("0.00"):
        return OperationType.INCOME
    if raw_transaction.amount < Decimal("0.00"):
        return OperationType.EXPENSE
    return None


def infer_rule_pattern(raw_transaction: RawTransaction) -> str:
    description = raw_transaction.description_normalized or raw_transaction.description_raw or ""
    match = MERCHANT_PATTERN.search(description)
    if match:
        return clean_rule_pattern(match.group(1))
    if "|" in description:
        return clean_rule_pattern(description.rsplit("|", maxsplit=1)[-1])
    return clean_rule_pattern(description)


def clean_rule_name(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def clean_rule_pattern(value: str | None) -> str:
    cleaned = clean_rule_name(value)
    if cleaned is None:
        raise TransactionRuleError("Rule pattern is required.")
    return cleaned[:255]


def clean_description(value: str | None) -> str | None:
    cleaned = clean_rule_name(value)
    return cleaned[:1000] if cleaned else None


def build_rule_name(
    *,
    pattern: str,
    match_type: TransactionRuleMatchType,
    category_name: str | None,
    target_operation_type: OperationType | None,
) -> str:
    target = clean_rule_name(category_name) or (
        target_operation_type.value if target_operation_type else None
    )
    if target:
        return f"{pattern} -> {target}"
    return f"{match_type.value}: {pattern}"


def normalized_text(value: str | None) -> str:
    return " ".join((value or "").casefold().split())
