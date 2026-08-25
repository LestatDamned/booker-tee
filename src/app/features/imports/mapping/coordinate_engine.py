import re
from dataclasses import dataclass

from app.features.imports.mapping.coordinate_dto import (
    CoordinateExtractionResult,
    CoordinateFieldRole,
    CoordinateMappingSpec,
    CoordinatePageLayout,
)
from app.features.imports.mapping.coordinate_validation import layout_name
from app.features.imports.mapping.dto import StatementMappingSpec, UnknownStatementMappingWarning
from app.features.imports.mapping.engine import mapping_warnings
from app.features.imports.mapping.rows import map_row

_DATE_ANCHOR = re.compile(r"^\s*\d{1,4}[./-]\d{1,2}[./-]\d{1,4}(?:\s|$)")


@dataclass(frozen=True)
class CoordinateWord:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float


class CoordinateMappingEngine:
    @staticmethod
    def apply(
        pages: list[tuple[float, float, list[CoordinateWord]]],
        spec: CoordinateMappingSpec,
    ) -> CoordinateExtractionResult:
        rows = []
        layouts = []
        missing_anchor_pages = 0
        unanchored_candidate_count = 0
        for page_index, (width, height, words) in enumerate(pages):
            name = layout_name(page_index, len(pages))
            layout = spec.layouts[name]
            page_rows, page_unanchored_count, page_has_anchors = _page_rows(
                words, width, height, layout, spec, page_index + 1
            )
            if not page_has_anchors:
                missing_anchor_pages += 1
            rows.extend(page_rows)
            layouts.extend([name] * len(page_rows))
            unanchored_candidate_count += page_unanchored_count
        warnings = mapping_warnings(rows, _normalization_spec(spec))
        if missing_anchor_pages:
            warnings.append(
                UnknownStatementMappingWarning(
                    code="coordinate_date_anchors_missing",
                    severity="warning",
                    affected_row_count=missing_anchor_pages,
                )
            )
        if unanchored_candidate_count:
            warnings.append(
                UnknownStatementMappingWarning(
                    code="coordinate_date_candidates_unanchored",
                    severity="warning",
                    affected_row_count=unanchored_candidate_count,
                )
            )
        return CoordinateExtractionResult(rows=rows, layouts=layouts, warnings=warnings)


def _page_rows(
    words: list[CoordinateWord],
    width: float,
    height: float,
    layout: CoordinatePageLayout,
    spec: CoordinateMappingSpec,
    page_number: int,
):
    words = [
        word
        for word in words
        if layout.transaction_top <= _center_y(word, height) <= layout.transaction_bottom
    ]
    date_rect = layout.fields[CoordinateFieldRole.OPERATION_DATE]
    date_words = [word for word in words if date_rect.x0 <= _center_x(word, width) <= date_rect.x1]
    lines = _group_lines(date_words)
    anchors = [line for line in lines if _DATE_ANCHOR.match(_join_words(line))]
    anchor_centers = [_line_center(line, height) for line in anchors]
    row_tolerance = max(3 / height, (layout.sample_row.y1 - layout.sample_row.y0) / 2)
    amount_words = [
        word
        for role in (
            CoordinateFieldRole.AMOUNT,
            CoordinateFieldRole.DEBIT,
            CoordinateFieldRole.CREDIT,
        )
        if (rect := layout.fields.get(role)) is not None
        for word in words
        if rect.x0 <= _center_x(word, width) <= rect.x1
    ]
    amount_centers = [_line_center(line, height) for line in _group_lines(amount_words)]
    unanchored_centers = [_line_center(line, height) for line in lines if line not in anchors]
    unanchored_amount_centers = [
        center
        for center in amount_centers
        if not any(abs(center - anchor) <= row_tolerance for anchor in anchor_centers)
    ]
    unanchored_centers.extend(unanchored_amount_centers)
    centers = sorted(
        [
            *anchor_centers,
            *_unique_centers(unanchored_amount_centers, tolerance=row_tolerance),
        ]
    )
    unanchored_candidate_count = len(_unique_centers(unanchored_centers, tolerance=row_tolerance))
    if not centers:
        return [], unanchored_candidate_count, bool(anchors)
    boundaries = [
        layout.transaction_top,
        *[(left + right) / 2 for left, right in zip(centers, centers[1:], strict=False)],
        layout.transaction_bottom,
    ]
    normalization_spec = _normalization_spec(spec, layout=layout)
    mapped = []
    roles = list(CoordinateFieldRole)
    for row_index, (top, bottom) in enumerate(zip(boundaries, boundaries[1:], strict=False)):
        cells = []
        for role in roles:
            rect = layout.fields.get(role)
            selected = [
                word
                for word in words
                if top <= _center_y(word, height) < bottom
                and rect is not None
                and rect.x0 <= _center_x(word, width) <= rect.x1
            ]
            cells.append(_join_words(selected))
        mapped.append(
            map_row(
                cells,
                page_number=page_number,
                table_index=0,
                source_row_number=row_index,
                spec=normalization_spec,
            )
        )
    return mapped, unanchored_candidate_count, bool(anchors)


def _normalization_spec(
    spec: CoordinateMappingSpec,
    *,
    layout: CoordinatePageLayout | None = None,
) -> StatementMappingSpec:
    roles = list(CoordinateFieldRole)
    index = {role: roles.index(role) for role in roles}
    fields = (layout or next(iter(spec.layouts.values()))).fields
    return StatementMappingSpec(
        operation_date_column=index[CoordinateFieldRole.OPERATION_DATE],
        posting_date_column=index[CoordinateFieldRole.POSTING_DATE]
        if CoordinateFieldRole.POSTING_DATE in fields
        else None,
        description_column=index[CoordinateFieldRole.DESCRIPTION],
        amount_column=index[CoordinateFieldRole.AMOUNT]
        if CoordinateFieldRole.AMOUNT in fields
        else None,
        debit_amount_column=index[CoordinateFieldRole.DEBIT]
        if CoordinateFieldRole.DEBIT in fields
        else None,
        credit_amount_column=index[CoordinateFieldRole.CREDIT]
        if CoordinateFieldRole.CREDIT in fields
        else None,
        currency_column=index[CoordinateFieldRole.CURRENCY]
        if CoordinateFieldRole.CURRENCY in fields
        else None,
        balance_after_column=index[CoordinateFieldRole.BALANCE]
        if CoordinateFieldRole.BALANCE in fields
        else None,
        default_currency=spec.default_currency,
        unsigned_amount_direction=spec.unsigned_amount_direction,
    )


def _group_lines(words: list[CoordinateWord]) -> list[list[CoordinateWord]]:
    lines: list[list[CoordinateWord]] = []
    for word in sorted(words, key=lambda item: (item.top, item.x0)):
        line = next(
            (candidate for candidate in reversed(lines) if abs(candidate[0].top - word.top) <= 3),
            None,
        )
        if line is None:
            lines.append([word])
        else:
            line.append(word)
    return lines


def _join_words(words: list[CoordinateWord]) -> str:
    return " ".join(
        word.text for word in sorted(words, key=lambda item: (item.top, item.x0))
    ).strip()


def _line_center(words: list[CoordinateWord], height: float) -> float:
    return sum(_center_y(word, height) for word in words) / len(words)


def _unique_centers(values: list[float], *, tolerance: float) -> list[float]:
    unique: list[float] = []
    for value in sorted(values):
        if not unique or value - unique[-1] > tolerance:
            unique.append(value)
    return unique


def _center_x(word: CoordinateWord, width: float) -> float:
    return (word.x0 + word.x1) / 2 / width


def _center_y(word: CoordinateWord, height: float) -> float:
    return (word.top + word.bottom) / 2 / height
