from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category, CategoryKind
from app.features.categories.repository import CategoryRepository
from app.features.workspaces.models import WorkspaceType


class CategoryError(ValueError):
    pass


@dataclass(frozen=True)
class SystemCategorySeed:
    system_key: str
    name: str
    kind: CategoryKind
    sort_order: int


@dataclass(frozen=True)
class DefaultCategorySeed:
    name: str
    kind: CategoryKind
    sort_order: int


SYSTEM_CATEGORY_SEEDS = [
    SystemCategorySeed("uncategorized", "Без категории", CategoryKind.MIXED, 10),
    SystemCategorySeed("transfer", "Перевод", CategoryKind.TRANSFER, 20),
    SystemCategorySeed("adjustment", "Корректировка", CategoryKind.ADJUSTMENT, 30),
    SystemCategorySeed("refund", "Возврат", CategoryKind.MIXED, 40),
    SystemCategorySeed("duplicate", "Дубль", CategoryKind.MIXED, 50),
    SystemCategorySeed("ignore", "Не учитывать", CategoryKind.MIXED, 60),
    SystemCategorySeed("income", "Прочий доход", CategoryKind.INCOME, 70),
    SystemCategorySeed("expense", "Прочий расход", CategoryKind.EXPENSE, 80),
    SystemCategorySeed("rent", "Арендный доход", CategoryKind.INCOME, 90),
]


DEFAULT_CATEGORY_SEEDS = [
    DefaultCategorySeed("Зарплата", CategoryKind.INCOME, 200),
    DefaultCategorySeed("Проценты и кэшбэк", CategoryKind.INCOME, 210),
    DefaultCategorySeed("Возврат от продавца", CategoryKind.INCOME, 220),
    DefaultCategorySeed("Компенсация", CategoryKind.INCOME, 230),
    DefaultCategorySeed("Продукты", CategoryKind.EXPENSE, 300),
    DefaultCategorySeed("Кафе и рестораны", CategoryKind.EXPENSE, 310),
    DefaultCategorySeed("Транспорт", CategoryKind.EXPENSE, 320),
    DefaultCategorySeed("Такси", CategoryKind.EXPENSE, 330),
    DefaultCategorySeed("Авто", CategoryKind.EXPENSE, 340),
    DefaultCategorySeed("Маркетплейсы", CategoryKind.EXPENSE, 350),
    DefaultCategorySeed("Аренда жилья/помещения", CategoryKind.EXPENSE, 360),
    DefaultCategorySeed("Ипотека и кредиты", CategoryKind.EXPENSE, 370),
    DefaultCategorySeed("Коммунальные услуги", CategoryKind.EXPENSE, 380),
    DefaultCategorySeed("Связь и интернет", CategoryKind.EXPENSE, 390),
    DefaultCategorySeed("Подписки и сервисы", CategoryKind.EXPENSE, 400),
    DefaultCategorySeed("Красота и здоровье", CategoryKind.EXPENSE, 410),
    DefaultCategorySeed("Одежда", CategoryKind.EXPENSE, 420),
    DefaultCategorySeed("Дом и быт", CategoryKind.EXPENSE, 430),
    DefaultCategorySeed("Ремонт", CategoryKind.EXPENSE, 440),
    DefaultCategorySeed("Подарки и помощь", CategoryKind.EXPENSE, 450),
    DefaultCategorySeed("Налоги и штрафы", CategoryKind.EXPENSE, 460),
    DefaultCategorySeed("Комиссия банка", CategoryKind.EXPENSE, 470),
]


PROPERTY_MANAGEMENT_CATEGORY_SEEDS = [
    DefaultCategorySeed("Компенсация коммунальных услуг", CategoryKind.INCOME, 500),
    DefaultCategorySeed("Удержанный залог", CategoryKind.INCOME, 510),
    DefaultCategorySeed("Хозтовары", CategoryKind.EXPENSE, 520),
    DefaultCategorySeed("Управление/обслуживание", CategoryKind.EXPENSE, 530),
    DefaultCategorySeed("Страхование", CategoryKind.EXPENSE, 540),
    DefaultCategorySeed("Налоги", CategoryKind.EXPENSE, 550),
    DefaultCategorySeed("Проценты по ипотеке", CategoryKind.EXPENSE, 560),
]


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.categories = CategoryRepository(session)

    async def list_or_seed_defaults(
        self,
        workspace_id: UUID,
        workspace_type: WorkspaceType | None = None,
    ) -> list[Category]:
        await self.seed_defaults(workspace_id, workspace_type)
        return await self.categories.list_for_workspace(workspace_id)

    async def seed_defaults(
        self,
        workspace_id: UUID,
        workspace_type: WorkspaceType | None = None,
    ) -> None:
        existing = await self.categories.list_for_workspace(workspace_id)
        existing_by_key = {
            category.system_key: category for category in existing if category.system_key
        }
        existing_names = {category.name for category in existing}
        for seed in SYSTEM_CATEGORY_SEEDS:
            existing_category = existing_by_key.get(seed.system_key)
            if existing_category is not None:
                existing_category.name = seed.name
                existing_category.kind = seed.kind
                existing_category.is_system = True
                existing_category.sort_order = seed.sort_order
                continue
            await self.categories.create(
                Category(
                    workspace_id=workspace_id,
                    name=seed.name,
                    kind=seed.kind,
                    is_system=True,
                    system_key=seed.system_key,
                    sort_order=seed.sort_order,
                )
            )
        for seed in self._default_category_seeds(workspace_type):
            if seed.name in existing_names:
                continue
            await self.categories.create(
                Category(
                    workspace_id=workspace_id,
                    name=seed.name,
                    kind=seed.kind,
                    is_system=False,
                    sort_order=seed.sort_order,
                )
            )
        await self.session.commit()

    async def get_uncategorized(self, workspace_id: UUID) -> Category:
        return await self.get_system(workspace_id, "uncategorized")

    async def get_system(self, workspace_id: UUID, system_key: str) -> Category:
        await self.seed_defaults(workspace_id)
        category = await self.categories.get_system_category(workspace_id, system_key)
        if category is None:
            raise CategoryError(f"{system_key} system category is not available.")
        return category

    async def get_for_workspace(
        self,
        workspace_id: UUID,
        category_id: UUID | None,
    ) -> Category | None:
        if category_id is None:
            return None
        category = await self.categories.get_for_workspace(workspace_id, category_id)
        if category is None:
            raise CategoryError("Category is not available in this workspace.")
        return category

    async def create_custom(
        self,
        *,
        workspace_id: UUID,
        name: str,
        kind: CategoryKind,
    ) -> Category:
        cleaned_name = " ".join(name.split())
        if not cleaned_name:
            raise CategoryError("Category name is required.")
        category = await self.categories.create(
            Category(
                workspace_id=workspace_id,
                name=cleaned_name,
                kind=kind,
                is_system=False,
                sort_order=500,
            )
        )
        await self.session.commit()
        return category

    @staticmethod
    def _default_category_seeds(
        workspace_type: WorkspaceType | None,
    ) -> list[DefaultCategorySeed]:
        seeds = [*DEFAULT_CATEGORY_SEEDS]
        if workspace_type == WorkspaceType.PROPERTY_MANAGEMENT:
            seeds.extend(PROPERTY_MANAGEMENT_CATEGORY_SEEDS)
        return seeds
