from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category, CategoryKind
from app.features.categories.repository import CategoryRepository
from app.features.ledger.models import OperationType
from app.features.transaction_rules.domain.text import normalized_text
from app.features.transaction_rules.models import (
    MoneyDirection,
    TransactionRule,
    TransactionRuleApplicationMode,
    TransactionRuleMatchType,
)
from app.features.transaction_rules.repository import TransactionRuleRepository
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class DefaultMerchantRuleSeed:
    category_name: str
    category_kind: CategoryKind
    pattern: str
    direction: MoneyDirection = MoneyDirection.OUTFLOW


DEFAULT_MERCHANT_RULE_SEEDS = [
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "KRASNOE&BELOE"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "SAMOKA"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "KOMANDOR"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, 'ООО "АГРОТОРГ"'),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "MAGNIT MM"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "KRASNYJ YAR"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "PYATEROCHKA"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "KUPEC"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "ALLEYA"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "YUMAMART"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "FASOL"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "BRISTOL"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "KALINA MALINA"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "BATON"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "KALINAMALINA"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "RUSSKIJ RAZGULYAJKA"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "Lenta"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "YARCHE"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "OKEY"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "KAZANKEBAB"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "ALIBI"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "KAKAYA-TO RYUMOCHNAYA"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "KULA BAR"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "AMMA INDIYA"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "AKADEMIYA KOFE"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "CHICKEN DENER"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "LUDWIG64"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "KOFEJNYA ZIZZI"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "SHARMA DYONER KHAUS"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "SUBITO"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "GREEN HOUSE"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "Rostics"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "BLOOM COFFEE"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "YANDEX EDA"),
    DefaultMerchantRuleSeed("Кафе и рестораны", CategoryKind.EXPENSE, "ESTAFETTE"),
    DefaultMerchantRuleSeed("Продукты", CategoryKind.EXPENSE, "DO YOU D ALEKSEEVA"),
    DefaultMerchantRuleSeed("Авто", CategoryKind.EXPENSE, "GAZPROMNEFT"),
    DefaultMerchantRuleSeed("Транспорт", CategoryKind.EXPENSE, "KRASAVTOTRANS_TPP"),
    DefaultMerchantRuleSeed("Транспорт", CategoryKind.EXPENSE, "URENT"),
    DefaultMerchantRuleSeed("Такси", CategoryKind.EXPENSE, "YANDEX GO"),
    DefaultMerchantRuleSeed("Такси", CategoryKind.EXPENSE, "YANDEX TAXI"),
    DefaultMerchantRuleSeed("Такси", CategoryKind.EXPENSE, "YANDEX FASTEN"),
    DefaultMerchantRuleSeed("Маркетплейсы", CategoryKind.EXPENSE, "OZON"),
    DefaultMerchantRuleSeed("Маркетплейсы", CategoryKind.EXPENSE, "wildberries.ru"),
    DefaultMerchantRuleSeed("Связь и интернет", CategoryKind.EXPENSE, "VTB Mobile"),
    DefaultMerchantRuleSeed("Связь и интернет", CategoryKind.EXPENSE, "T-Mobile"),
    DefaultMerchantRuleSeed("Связь и интернет", CategoryKind.EXPENSE, "TELECOMA"),
    DefaultMerchantRuleSeed("Подписки и сервисы", CategoryKind.EXPENSE, 'ООО БАНК "ПЭЙДЖИН"'),
    DefaultMerchantRuleSeed("Подписки и сервисы", CategoryKind.EXPENSE, "SMART GLOCAL SERVICES"),
    DefaultMerchantRuleSeed("Подписки и сервисы", CategoryKind.EXPENSE, "Veesp"),
    DefaultMerchantRuleSeed("Подписки и сервисы", CategoryKind.EXPENSE, 'ООО "ВИСП"'),
    DefaultMerchantRuleSeed("Подписки и сервисы", CategoryKind.EXPENSE, "YANDEX PLUS"),
    DefaultMerchantRuleSeed("Красота и здоровье", CategoryKind.EXPENSE, "ЕКАТЕРИНБУРГ ЯБЛОКО"),
]


class DefaultMerchantRuleSeeder:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.categories = CategoryRepository(session)
        self.rules = TransactionRuleRepository(session)

    async def seed(self, context: WorkspaceContext) -> list[TransactionRule]:
        created_or_existing: list[TransactionRule] = []
        existing_by_identity = {
            (normalized_text(rule.pattern), rule.category_id): rule
            for rule in await self.rules.list_for_workspace(context.workspace.id)
        }
        for seed in DEFAULT_MERCHANT_RULE_SEEDS:
            category = await self._get_or_create_category(
                workspace_id=context.workspace.id,
                name=seed.category_name,
                kind=seed.category_kind,
            )
            rule_identity = (normalized_text(seed.pattern), category.id)
            existing = existing_by_identity.get(rule_identity)
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
            existing_by_identity[rule_identity] = created_or_existing[-1]
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
