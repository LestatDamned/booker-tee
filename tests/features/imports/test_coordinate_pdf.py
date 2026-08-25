import math
from pathlib import Path
from types import SimpleNamespace

import pytest
from pdfplumber.utils.exceptions import MalformedPDFException
from pypdfium2 import PdfiumError

from app.features.imports.mapping import coordinate_pdf
from app.features.imports.mapping.coordinate_pdf import (
    MAX_COORDINATE_IMAGE_HEIGHT,
    MAX_COORDINATE_IMAGE_PIXELS,
    MAX_COORDINATE_IMAGE_WIDTH,
    CoordinatePdfError,
    CoordinatePdfReader,
    _render_resolution,
)


@pytest.mark.parametrize("dimensions", [(4000, 200), (200, 5000), (1700, 1700)])
def test_render_resolution_bounds_both_sides_and_pixel_budget(dimensions) -> None:
    width, height = dimensions
    resolution = _render_resolution(width, height)
    rendered_width = width * resolution / 72
    rendered_height = height * resolution / 72

    assert rendered_width <= MAX_COORDINATE_IMAGE_WIDTH
    assert rendered_height <= MAX_COORDINATE_IMAGE_HEIGHT
    assert rendered_width * rendered_height <= MAX_COORDINATE_IMAGE_PIXELS


@pytest.mark.parametrize("dimensions", [(0, 100), (-1, 100), (math.inf, 100), (100, math.nan)])
def test_invalid_pdf_dimensions_are_controlled(dimensions) -> None:
    with pytest.raises(CoordinatePdfError, match="dimensions"):
        _render_resolution(*dimensions)


def test_source_path_rejects_traversal(tmp_path: Path) -> None:
    reader = CoordinatePdfReader(tmp_path)
    with pytest.raises(CoordinatePdfError, match="unavailable"):
        reader.source_path("../statement.pdf")


def test_renderer_receives_bounded_resolution(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "statement.pdf"
    path.touch()
    resolutions: list[int] = []

    class Image:
        original = SimpleNamespace(save=lambda *_args, **_kwargs: None)

    page = SimpleNamespace(
        width=4000,
        height=200,
        to_image=lambda *, resolution: resolutions.append(resolution) or Image(),
    )

    class Pdf:
        pages = [page]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(coordinate_pdf.pdfplumber, "open", lambda _path: Pdf())
    CoordinatePdfReader._render_page(path, 1)

    assert resolutions == [_render_resolution(4000, 200)]


@pytest.mark.asyncio
@pytest.mark.parametrize("renderer_error", [MalformedPDFException, PdfiumError])
async def test_renderer_failure_is_normalized_without_path_leak(
    monkeypatch, tmp_path: Path, renderer_error
) -> None:
    path = tmp_path / "statement.pdf"
    path.touch()
    sensitive_path = "/private/statements/customer.pdf"
    page = SimpleNamespace(
        width=600,
        height=800,
        to_image=lambda **_kwargs: (_ for _ in ()).throw(renderer_error(sensitive_path)),
    )

    class Pdf:
        pages = [page]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    async def run_sync(operation, *args):
        return operation(*args)

    monkeypatch.setattr(coordinate_pdf.asyncio, "to_thread", run_sync)
    monkeypatch.setattr(coordinate_pdf.pdfplumber, "open", lambda _path: Pdf())

    with pytest.raises(CoordinatePdfError, match="could not be read") as error:
        await CoordinatePdfReader(tmp_path).render_page("statement.pdf", 1)

    assert sensitive_path not in str(error.value)


def test_pdf_inspection_reports_dimensions_and_text_layer(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "statement.pdf"
    path.touch()
    pages = [
        SimpleNamespace(width=600, height=800, extract_words=lambda: [{"text": "row"}]),
        SimpleNamespace(width=800, height=600, extract_words=lambda: []),
    ]

    class Pdf:
        def __enter__(self):
            return SimpleNamespace(pages=pages)

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(coordinate_pdf.pdfplumber, "open", lambda _path: Pdf())

    metadata = CoordinatePdfReader._inspect(path)

    assert [page.aspect_ratio for page in metadata] == [0.75, 800 / 600]
    assert [page.has_text_layer for page in metadata] == [True, False]
