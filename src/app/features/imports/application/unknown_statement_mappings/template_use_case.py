from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.mapping.repository import MappingRepository
from app.features.imports.models import ImportMappingTemplate


class UnknownStatementMappingTemplateUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.mappings = MappingRepository(session)

    async def list_matching_templates(
        self,
        *,
        workspace_id: UUID,
        bank_name: str | None,
        statement_type: str | None,
    ) -> list[ImportMappingTemplate]:
        if not bank_name and not statement_type:
            return []
        return await self.mappings.list_mapping_templates(
            workspace_id=workspace_id,
            bank_name=bank_name,
            statement_type=statement_type,
        )
