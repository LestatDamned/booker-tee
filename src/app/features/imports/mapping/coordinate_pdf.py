import asyncio
import math
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import TypeVar

import pdfplumber
from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException
from pypdfium2 import PdfiumError

from app.features.imports.documents.storage import resolve_storage_path
from app.features.imports.mapping.coordinate_dto import CoordinatePageMetadata
from app.features.imports.mapping.coordinate_engine import CoordinateWord

MAX_COORDINATE_IMAGE_WIDTH = 1800
MAX_COORDINATE_IMAGE_HEIGHT = 1800
MAX_COORDINATE_IMAGE_PIXELS = 3_000_000
T = TypeVar("T")


class CoordinatePdfError(ValueError):
    pass


class CoordinatePdfReader:
    def __init__(self, storage_root: Path) -> None:
        self._storage_root = storage_root

    def source_path(self, storage_key: str | None) -> Path:
        if not storage_key:
            raise CoordinatePdfError("Source PDF is unavailable.")
        try:
            _, path = resolve_storage_path(self._storage_root, storage_key)
        except ValueError as exc:
            raise CoordinatePdfError("Source PDF is unavailable.") from exc
        if not path.is_file():
            raise CoordinatePdfError("Source PDF is unavailable.")
        return path

    async def inspect(self, storage_key: str | None) -> list[CoordinatePageMetadata]:
        return await self._run(self._inspect, storage_key)

    async def extract_words(
        self, storage_key: str | None
    ) -> list[tuple[float, float, list[CoordinateWord]]]:
        return await self._run(self._extract_words, storage_key)

    async def render_page(self, storage_key: str | None, page_number: int) -> bytes:
        return await self._run(self._render_page, storage_key, page_number)

    async def _run(
        self,
        operation: Callable[..., T],
        storage_key: str | None,
        *args: object,
    ) -> T:
        try:
            return await asyncio.to_thread(operation, self.source_path(storage_key), *args)
        except CoordinatePdfError:
            raise
        except (
            OSError,
            TypeError,
            ValueError,
            MalformedPDFException,
            PdfminerException,
            PdfiumError,
        ) as exc:
            raise CoordinatePdfError("Source PDF could not be read.") from exc

    @staticmethod
    def _inspect(path: Path) -> list[CoordinatePageMetadata]:
        with pdfplumber.open(path) as pdf:
            pages = []
            for index, page in enumerate(pdf.pages, start=1):
                width, height = _page_dimensions(page.width, page.height)
                pages.append(
                    CoordinatePageMetadata(
                        page_number=index,
                        width=width,
                        height=height,
                        aspect_ratio=width / height,
                        has_text_layer=bool(page.extract_words()),
                    )
                )
            return pages

    @staticmethod
    def _extract_words(path: Path) -> list[tuple[float, float, list[CoordinateWord]]]:
        with pdfplumber.open(path) as pdf:
            return [
                (
                    float(page.width),
                    float(page.height),
                    [
                        CoordinateWord(
                            text=str(word["text"]),
                            x0=float(word["x0"]),
                            x1=float(word["x1"]),
                            top=float(word["top"]),
                            bottom=float(word["bottom"]),
                        )
                        for word in page.extract_words()
                    ],
                )
                for page in pdf.pages
            ]

    @staticmethod
    def _render_page(path: Path, page_number: int) -> bytes:
        with pdfplumber.open(path) as pdf:
            if page_number < 1 or page_number > len(pdf.pages):
                raise CoordinatePdfError("PDF page was not found.")
            page = pdf.pages[page_number - 1]
            resolution = _render_resolution(page.width, page.height)
            image = page.to_image(resolution=resolution).original
            output = BytesIO()
            image.save(output, format="PNG", optimize=True)
            return output.getvalue()


def _page_dimensions(width: float, height: float) -> tuple[float, float]:
    dimensions = (float(width), float(height))
    if any(not math.isfinite(value) or value <= 0 for value in dimensions):
        raise CoordinatePdfError("PDF page dimensions are invalid.")
    return dimensions


def _render_resolution(width: float, height: float) -> int:
    width_value, height_value = _page_dimensions(width, height)
    scale = min(
        2.0,
        MAX_COORDINATE_IMAGE_WIDTH / width_value,
        MAX_COORDINATE_IMAGE_HEIGHT / height_value,
        math.sqrt(MAX_COORDINATE_IMAGE_PIXELS / (width_value * height_value)),
    )
    resolution = math.floor(72 * scale)
    if resolution < 1:
        raise CoordinatePdfError("PDF page dimensions exceed render limits.")
    return resolution
