from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import ImportMappingTemplate
from app.features.imports.repository import ImportRepository


class UnknownStatementMappingTemplateUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.imports = ImportRepository(session)

    async def list_matching_templates(
        self,
        *,
        workspace_id: UUID,
        bank_name: str | None,
        statement_type: str | None,
    ) -> list[ImportMappingTemplate]:
        if not bank_name and not statement_type:
            return []
        return await self.imports.list_mapping_templates(
            workspace_id=workspace_id,
            bank_name=bank_name,
            statement_type=statement_type,
        )
