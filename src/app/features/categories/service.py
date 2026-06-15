from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category, CategoryKind
from app.features.categories.repository import CategoryRepository


class CategoryError(ValueError):
    pass


@dataclass(frozen=True)
class SystemCategorySeed:
    system_key: str
    name: str
    kind: CategoryKind
    sort_order: int


SYSTEM_CATEGORY_SEEDS = [
    SystemCategorySeed("uncategorized", "Без категории", CategoryKind.MIXED, 10),
    SystemCategorySeed("income", "Доход", CategoryKind.INCOME, 20),
    SystemCategorySeed("expense", "Расход", CategoryKind.EXPENSE, 30),
    SystemCategorySeed("transfer", "Перевод", CategoryKind.TRANSFER, 40),
    SystemCategorySeed("adjustment", "Корректировка", CategoryKind.ADJUSTMENT, 50),
    SystemCategorySeed("refund", "Возврат", CategoryKind.MIXED, 60),
    SystemCategorySeed("duplicate", "Дубль", CategoryKind.MIXED, 70),
    SystemCategorySeed("ignore", "Не учитывать", CategoryKind.MIXED, 80),
    SystemCategorySeed("bank_fee", "Комиссия банка", CategoryKind.EXPENSE, 90),
    SystemCategorySeed("rent", "Аренда", CategoryKind.INCOME, 100),
    SystemCategorySeed("utilities", "Коммунальные услуги", CategoryKind.EXPENSE, 110),
    SystemCategorySeed("repair", "Ремонт", CategoryKind.EXPENSE, 120),
    SystemCategorySeed("other", "Другое", CategoryKind.MIXED, 130),
]


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.categories = CategoryRepository(session)

    async def list_or_seed_defaults(self, workspace_id: UUID) -> list[Category]:
        await self.seed_defaults(workspace_id)
        return await self.categories.list_for_workspace(workspace_id)

    async def seed_defaults(self, workspace_id: UUID) -> None:
        existing = await self.categories.list_for_workspace(workspace_id)
        existing_keys = {category.system_key for category in existing if category.system_key}
        for seed in SYSTEM_CATEGORY_SEEDS:
            if seed.system_key in existing_keys:
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
