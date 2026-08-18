from pydantic import Field

from app.shared.schemas import ApplicationModel


class StatementExtractionLimits(ApplicationModel):
    pdf_max_pages: int = Field(default=200, ge=1)
    xlsx_max_sheets: int = Field(default=20, ge=1)
    xlsx_max_rows_per_sheet: int = Field(default=50_000, ge=1)
    xlsx_max_columns_per_sheet: int = Field(default=100, ge=1)
    xlsx_max_cells: int = Field(default=1_000_000, ge=1)
    xlsx_max_uncompressed_bytes: int = Field(default=100 * 1024 * 1024, ge=1)


class StatementResourceLimitError(ValueError):
    pass
