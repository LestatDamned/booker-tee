"""russian system category names

Revision ID: 20260613_0008
Revises: 20260613_0007
Create Date: 2026-06-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260613_0008"
down_revision: str | None = "20260613_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SYSTEM_CATEGORY_NAMES = {
    "uncategorized": "Без категории",
    "income": "Доход",
    "expense": "Расход",
    "transfer": "Перевод",
    "adjustment": "Корректировка",
    "refund": "Возврат",
    "duplicate": "Дубль",
    "ignore": "Не учитывать",
    "bank_fee": "Комиссия банка",
    "rent": "Аренда",
    "utilities": "Коммунальные услуги",
    "repair": "Ремонт",
    "other": "Другое",
}

ENGLISH_SYSTEM_CATEGORY_NAMES = {
    "uncategorized": "Uncategorized",
    "income": "Income",
    "expense": "Expense",
    "transfer": "Transfer",
    "adjustment": "Adjustment",
    "refund": "Refund",
    "duplicate": "Duplicate",
    "ignore": "Ignore / Do not count",
    "bank_fee": "Bank fee",
    "rent": "Rent",
    "utilities": "Utilities",
    "repair": "Repair",
    "other": "Other",
}


def upgrade() -> None:
    connection = op.get_bind()
    statement = sa.text(
        "update categories set name = :name where is_system = true and system_key = :key"
    )
    for system_key, name in SYSTEM_CATEGORY_NAMES.items():
        connection.execute(statement, {"name": name, "key": system_key})


def downgrade() -> None:
    connection = op.get_bind()
    statement = sa.text(
        "update categories set name = :name where is_system = true and system_key = :key"
    )
    for system_key, name in ENGLISH_SYSTEM_CATEGORY_NAMES.items():
        connection.execute(statement, {"name": name, "key": system_key})
