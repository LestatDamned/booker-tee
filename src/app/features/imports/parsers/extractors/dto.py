from pydantic import Field

from app.shared.schemas import ApplicationModel


class ExtractedStatementPageTables(ApplicationModel):
    page_number: int
    tables: list[list[list[str | None]]]


class ExtractedStatement(ApplicationModel):
    text_by_page: list[str]
    tables_by_page: list[ExtractedStatementPageTables]
    metadata: dict[str, object] = Field(default_factory=dict)
