from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import RawTransaction
from app.features.imports.repository import ImportRepository
from app.features.transaction_rules.domain.matching import (
    can_suggest_raw_transaction,
    rule_matches_raw_transaction,
)
from app.features.transaction_rules.domain.suggestions import (
    apply_rule_suggestion,
    clear_rule_suggestion,
)
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.transaction_rules.repository import TransactionRuleRepository


@dataclass(frozen=True)
class RuleApplicationSummary:
    checked_count: int
    suggested_count: int


class TransactionRuleApplicationUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.imports = ImportRepository(session)
        self.rules = TransactionRuleRepository(session)

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
