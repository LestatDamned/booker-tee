from pathlib import Path
from typing import Protocol

from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.parsers.extractors.pdf import PdfPlumberStatementExtractor
from app.features.imports.parsers.extractors.xlsx import OpenPyxlStatementExtractor

SUPPORTED_STATEMENT_EXTENSIONS = frozenset({".pdf", ".xlsx"})


class StatementExtractor(Protocol):
    def extract(self, file_path: Path) -> ExtractedStatement: ...


class StatementExtractorResolver:
    def __init__(
        self,
        *,
        pdf_extractor: StatementExtractor | None = None,
        xlsx_extractor: StatementExtractor | None = None,
    ) -> None:
        self.pdf_extractor = pdf_extractor or PdfPlumberStatementExtractor()
        self.xlsx_extractor = xlsx_extractor or OpenPyxlStatementExtractor()

    def extractor_for_path(self, file_path: Path) -> StatementExtractor:
        extension = file_path.suffix.casefold()
        if extension == ".pdf":
            return self.pdf_extractor
        if extension == ".xlsx":
            return self.xlsx_extractor
        raise UnsupportedStatementFileError(
            f"Unsupported statement file extension: {extension or '<none>'}"
        )

    def extract(self, file_path: Path) -> ExtractedStatement:
        return self.extractor_for_path(file_path).extract(file_path)


class UnsupportedStatementFileError(ValueError):
    pass
