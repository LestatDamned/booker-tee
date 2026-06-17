from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category, CategoryKind
from app.features.categories.repository import CategoryRepository
from app.features.ledger.models import OperationType
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.repository import TransactionRuleRepository
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class ExpobankFixtureRuleSeed:
    category_name: str
    category_kind: CategoryKind
    pattern: str
    direction: MoneyDirection = MoneyDirection.OUTFLOW


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
    ExpobankFixtureRuleSeed("Авто", CategoryKind.EXPENSE, "GAZPROMNEFT"),
    ExpobankFixtureRuleSeed("Связь", CategoryKind.EXPENSE, "VTB Mobile"),
    ExpobankFixtureRuleSeed("Связь", CategoryKind.EXPENSE, "Telecoma"),
    ExpobankFixtureRuleSeed("Сервисы", CategoryKind.EXPENSE, 'ООО БАНК "ПЭЙДЖИН"'),
    ExpobankFixtureRuleSeed("Сервисы", CategoryKind.EXPENSE, "SMART GLOCAL SERVICES"),
    ExpobankFixtureRuleSeed("Сервисы", CategoryKind.EXPENSE, "Veesp"),
    ExpobankFixtureRuleSeed("Сервисы", CategoryKind.EXPENSE, 'ООО "ВИСП"'),
]


class ExpobankFixtureRuleSeeder:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.categories = CategoryRepository(session)
        self.rules = TransactionRuleRepository(session)

    async def seed(self, context: WorkspaceContext) -> list[TransactionRule]:
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

    async def _get_or_create_category(
        self,
        *,
        workspace_id,
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
