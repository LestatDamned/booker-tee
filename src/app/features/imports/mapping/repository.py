from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import (
    ImportMappingExecution,
    ImportMappingTemplate,
)


class MappingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_mapping_template(
        self,
        template: ImportMappingTemplate,
    ) -> ImportMappingTemplate:
        self.session.add(template)
        await self.session.flush()
        return template

    async def create_mapping_execution(
        self,
        execution: ImportMappingExecution,
    ) -> ImportMappingExecution:
        self.session.add(execution)
        await self.session.flush()
        return execution

    async def get_mapping_execution(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        idempotency_key: UUID,
    ) -> ImportMappingExecution | None:
        result = await self.session.execute(
            select(ImportMappingExecution).where(
                ImportMappingExecution.workspace_id == workspace_id,
                ImportMappingExecution.uploaded_document_id == document_id,
                ImportMappingExecution.idempotency_key == str(idempotency_key),
            )
        )
        return result.scalar_one_or_none()

    async def list_mapping_templates(
        self,
        *,
        workspace_id: UUID,
        bank_name: str | None = None,
        statement_type: str | None = None,
    ) -> list[ImportMappingTemplate]:
        query = select(ImportMappingTemplate).where(
            ImportMappingTemplate.workspace_id == workspace_id
        )
        if bank_name:
            query = query.where(ImportMappingTemplate.bank_name == bank_name)
        if statement_type:
            query = query.where(ImportMappingTemplate.statement_type == statement_type)
        query = query.order_by(ImportMappingTemplate.updated_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())
