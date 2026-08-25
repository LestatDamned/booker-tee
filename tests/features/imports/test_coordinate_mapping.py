from decimal import Decimal

from app.features.imports.mapping.coordinate_dto import (
    CoordinateControlRegion,
    CoordinateControlTotalKind,
    CoordinateFieldRole,
    CoordinateMappingSpec,
    CoordinatePageLayout,
    NormalizedRect,
)
from app.features.imports.mapping.coordinate_engine import CoordinateMappingEngine, CoordinateWord
from app.features.imports.mapping.coordinate_validation import CoordinateMappingValidator
from app.features.imports.mapping.dto import UnsignedAmountDirection


def test_coordinate_spec_validation_covers_geometry_layouts_and_amount_modes() -> None:
    spec = _spec()
    assert CoordinateMappingValidator.validate(spec, page_aspect_ratios=[0.75]) == []

    invalid = spec.model_copy(
        update={
            "layouts": {
                "first": spec.layouts["first"].model_copy(
                    update={
                        "fields": {
                            CoordinateFieldRole.OPERATION_DATE: NormalizedRect(
                                x0=0.1, y0=0.2, x1=0.4, y1=0.3
                            ),
                            CoordinateFieldRole.DESCRIPTION: NormalizedRect(
                                x0=0.3, y0=0.2, x1=0.6, y1=0.3
                            ),
                            CoordinateFieldRole.DEBIT: NormalizedRect(
                                x0=0.65, y0=0.2, x1=0.75, y1=0.3
                            ),
                        }
                    }
                )
            }
        }
    )
    issues = CoordinateMappingValidator.validate(invalid, page_aspect_ratios=[0.75, 0.75])
    assert {issue.field for issue in issues} >= {
        "layouts.last",
        "layouts.first.fields",
    }


def test_coordinate_engine_extracts_rows_multiline_description_and_signed_amount() -> None:
    result = CoordinateMappingEngine.apply(
        [
            (
                1000,
                1000,
                [
                    _word("header", 300, 50),
                    _word("01.08.2026", 100, 220),
                    _word("Coffee", 300, 220),
                    _word("shop", 300, 245),
                    _word("-250,50", 800, 220),
                    _word("02.08.2026", 100, 420),
                    _word("Salary", 300, 420),
                    _word("+1000", 800, 420),
                    _word("footer", 300, 970),
                ],
            )
        ],
        _spec(),
    )

    assert len(result.rows) == 2
    assert result.rows[0].description == "Coffee shop"
    assert result.rows[0].amount == Decimal("-250.50")
    assert result.rows[1].amount == Decimal("1000")
    assert result.layouts == ["first", "first"]


def test_coordinate_engine_resolves_and_reconciles_visual_control_totals() -> None:
    page = (
        1000,
        1000,
        [
            _word("1 000,00 ₽", 100, 50),
            _word("850,00 ₽", 300, 50),
            _word("0,00 ₽", 500, 50),
            _word("150,00 ₽", 700, 50),
            _word("01.08.2026", 100, 220),
            _word("Purchase", 300, 220),
            _word("-150,00", 800, 220),
        ],
    )
    regions = tuple(
        CoordinateControlRegion(
            kind=kind,
            page_number=1,
            rect=NormalizedRect(x0=x0, y0=0.02, x1=x1, y1=0.08),
        )
        for kind, x0, x1 in (
            (CoordinateControlTotalKind.OPENING_BALANCE, 0.05, 0.2),
            (CoordinateControlTotalKind.CLOSING_BALANCE, 0.25, 0.4),
            (CoordinateControlTotalKind.TOTAL_INFLOW, 0.45, 0.6),
            (CoordinateControlTotalKind.TOTAL_OUTFLOW, 0.65, 0.8),
        )
    )

    extraction = CoordinateMappingEngine.apply([page], _spec())
    controls = CoordinateMappingEngine.resolve_control_totals([page], regions)
    checks = CoordinateMappingEngine.reconcile(extraction.rows, controls)

    assert [control.amount for control in controls] == ["1000.00", "850.00", "0.00", "150.00"]
    assert {check.kind for check in checks} == {"balance", "total_inflow", "total_outflow"}
    assert all(check.matches for check in checks)


def test_coordinate_engine_warns_when_page_has_no_date_anchor() -> None:
    result = CoordinateMappingEngine.apply([(1000, 1000, [_word("not-a-date", 100, 220)])], _spec())
    assert result.rows == []
    assert {warning.code for warning in result.warnings} >= {
        "coordinate_date_anchors_missing",
        "no_valid_rows",
    }


def test_coordinate_engine_counts_page_without_anchor_when_amount_creates_candidate() -> None:
    result = CoordinateMappingEngine.apply(
        [
            (
                1000,
                1000,
                [
                    _word("not-a-date", 100, 220),
                    _word("Candidate", 300, 220),
                    _word("-10", 800, 224),
                ],
            )
        ],
        _spec(),
    )

    assert len(result.rows) == 1
    warning = next(
        warning for warning in result.warnings if warning.code == "coordinate_date_anchors_missing"
    )
    assert warning.affected_row_count == 1


def test_coordinate_engine_associates_realistic_amount_baseline_offset() -> None:
    result = CoordinateMappingEngine.apply(
        [
            (
                1000,
                1000,
                [
                    _word("01.08.2026", 100, 220),
                    _word("Aligned operation", 300, 222),
                    _word("-10", 800, 225),
                ],
            )
        ],
        _spec(),
    )

    assert len(result.rows) == 1
    assert result.rows[0].status == "valid"
    assert result.rows[0].amount == Decimal("-10")


def test_coordinate_engine_preserves_invalid_structural_date_row() -> None:
    result = CoordinateMappingEngine.apply(
        [
            (
                1000,
                1000,
                [
                    _word("01.08.2026", 100, 220),
                    _word("Valid", 300, 220),
                    _word("100", 800, 220),
                    _word("31.02.2026", 100, 320),
                    _word("Bad", 300, 320),
                    _word("not-money", 800, 320),
                    _word("03.08.2026", 100, 420),
                    _word("Valid again", 300, 420),
                    _word("-20", 800, 420),
                ],
            )
        ],
        _spec(),
    )

    assert len(result.rows) == 3
    assert [row.source_row_number for row in result.rows] == [0, 1, 2]
    assert result.rows[1].operation_date_raw == "31.02.2026"
    assert result.rows[1].amount_raw == "not-money"
    assert result.rows[1].status == "error"


def test_coordinate_engine_warns_for_unanchored_candidate_inside_partial_page() -> None:
    result = CoordinateMappingEngine.apply(
        [
            (
                1000,
                1000,
                [
                    _word("01.08.2026", 100, 220),
                    _word("First", 300, 220),
                    _word("-10", 800, 220),
                    _word("not-a-date", 100, 320),
                    _word("Unanchored", 300, 320),
                    _word("-20", 800, 320),
                    _word("03.08.2026", 100, 420),
                    _word("Last", 300, 420),
                    _word("-30", 800, 420),
                ],
            )
        ],
        _spec(),
    )

    warning = next(
        warning
        for warning in result.warnings
        if warning.code == "coordinate_date_candidates_unanchored"
    )
    assert warning.affected_row_count == 1
    assert warning.severity == "warning"
    assert len(result.rows) == 3
    assert result.rows[1].operation_date_raw == "not-a-date"
    assert result.rows[1].status == "error"


def test_coordinate_engine_preserves_blank_date_amount_row_without_splitting_multiline() -> None:
    result = CoordinateMappingEngine.apply(
        [
            (
                1000,
                1000,
                [
                    _word("01.08.2026", 100, 220),
                    _word("First", 300, 220),
                    _word("continued", 300, 245),
                    _word("-10", 800, 220),
                    _word("Blank date row", 300, 320),
                    _word("-20", 800, 320),
                    _word("03.08.2026", 100, 420),
                    _word("Last", 300, 420),
                    _word("-30", 800, 420),
                ],
            )
        ],
        _spec(),
    )

    assert len(result.rows) == 3
    assert result.rows[0].description == "First continued"
    assert result.rows[1].operation_date_raw == ""
    assert result.rows[1].description == "Blank date row"
    assert result.rows[1].status == "error"
    warning = next(
        warning
        for warning in result.warnings
        if warning.code == "coordinate_date_candidates_unanchored"
    )
    assert warning.affected_row_count == 1


def test_coordinate_engine_selects_first_middle_last_layouts() -> None:
    first = _spec().layouts["first"]
    spec = _spec().model_copy(update={"layouts": {"first": first, "middle": first, "last": first}})
    page = (
        1000,
        1000,
        [
            _word("01.08.2026", 100, 220),
            _word("Row", 300, 220),
            _word("-10", 800, 220),
        ],
    )

    result = CoordinateMappingEngine.apply([page, page, page], spec)

    assert result.layouts == ["first", "middle", "last"]


def test_coordinate_engine_maps_debit_credit_and_warns_unsigned_amount() -> None:
    layout = _spec().layouts["first"]
    split = layout.model_copy(
        update={
            "fields": {
                CoordinateFieldRole.OPERATION_DATE: layout.fields[
                    CoordinateFieldRole.OPERATION_DATE
                ],
                CoordinateFieldRole.DESCRIPTION: layout.fields[CoordinateFieldRole.DESCRIPTION],
                CoordinateFieldRole.DEBIT: NormalizedRect(x0=0.7, y0=0.2, x1=0.8, y1=0.3),
                CoordinateFieldRole.CREDIT: NormalizedRect(x0=0.85, y0=0.2, x1=0.95, y1=0.3),
            }
        }
    )
    split_result = CoordinateMappingEngine.apply(
        [
            (
                1000,
                1000,
                [
                    _word("01.08.2026", 100, 220),
                    _word("Debit", 300, 220),
                    _word("100", 700, 220),
                    _word("02.08.2026", 100, 420),
                    _word("Credit", 300, 420),
                    _word("200", 850, 420),
                ],
            )
        ],
        _spec().model_copy(update={"layouts": {"first": split}}),
    )
    assert [row.amount for row in split_result.rows] == [Decimal("-100"), Decimal("200")]

    unsigned_result = CoordinateMappingEngine.apply(
        [
            (
                1000,
                1000,
                [
                    _word("01.08.2026", 100, 220),
                    _word("Unsigned", 300, 220),
                    _word("100", 800, 220),
                ],
            )
        ],
        _spec(),
    )
    warning = next(
        warning
        for warning in unsigned_result.warnings
        if warning.code == "unsigned_amount_direction_required"
    )
    assert warning.affected_row_count == 1


def test_coordinate_validation_reports_bounds_and_aspect_ratio() -> None:
    layout = (
        _spec()
        .layouts["first"]
        .model_copy(
            update={
                "transaction_top": 0.8,
                "transaction_bottom": 0.2,
                "sample_row": NormalizedRect(x0=-0.1, y0=0.1, x1=0.5, y1=0.3),
            }
        )
    )
    spec = _spec().model_copy(update={"layouts": {"first": layout}})

    fields = {
        issue.field
        for issue in CoordinateMappingValidator.validate(spec, page_aspect_ratios=[1.25])
    }

    assert "layouts.first" in fields
    assert "layouts.first.sampleRow" in fields
    assert "layouts.first.pageAspectRatio" in fields

    outside_layout = (
        _spec()
        .layouts["first"]
        .model_copy(update={"sample_row": NormalizedRect(x0=0.1, y0=0.05, x1=0.5, y1=0.1)})
    )
    outside_issues = CoordinateMappingValidator.validate(
        _spec().model_copy(update={"layouts": {"first": outside_layout}}),
        page_aspect_ratios=[0.75],
    )
    assert any(
        issue.field == "layouts.first.sampleRow"
        and issue.message == "Rectangle must be inside transaction bounds."
        for issue in outside_issues
    )


def test_coordinate_validation_rejects_x_overlap_even_when_y_is_disjoint() -> None:
    layout = _spec().layouts["first"]
    fields = {
        **layout.fields,
        CoordinateFieldRole.DESCRIPTION: NormalizedRect(x0=0.1, y0=0.35, x1=0.4, y1=0.45),
    }
    issues = CoordinateMappingValidator.validate(
        _spec().model_copy(
            update={"layouts": {"first": layout.model_copy(update={"fields": fields})}}
        ),
        page_aspect_ratios=[0.75],
    )

    assert any(
        issue.field == "layouts.first.fields"
        and "operation_date overlaps description" in issue.message
        for issue in issues
    )


def test_coordinate_spec_normalizes_three_letter_currency() -> None:
    assert (
        CoordinateMappingSpec.model_validate(
            {**_spec().model_dump(), "default_currency": " usd "}
        ).default_currency
        == "USD"
    )


def _spec() -> CoordinateMappingSpec:
    return CoordinateMappingSpec(
        default_currency="RUB",
        unsigned_amount_direction=UnsignedAmountDirection.REQUIRE_SIGN,
        layouts={
            "first": CoordinatePageLayout(
                page_aspect_ratio=0.75,
                transaction_top=0.15,
                transaction_bottom=0.9,
                sample_row=NormalizedRect(x0=0.05, y0=0.2, x1=0.95, y1=0.3),
                fields={
                    CoordinateFieldRole.OPERATION_DATE: NormalizedRect(
                        x0=0.05, y0=0.2, x1=0.2, y1=0.3
                    ),
                    CoordinateFieldRole.DESCRIPTION: NormalizedRect(
                        x0=0.25, y0=0.2, x1=0.65, y1=0.3
                    ),
                    CoordinateFieldRole.AMOUNT: NormalizedRect(x0=0.75, y0=0.2, x1=0.95, y1=0.3),
                },
            )
        },
    )


def _word(text: str, x0: float, top: float) -> CoordinateWord:
    return CoordinateWord(text=text, x0=x0, x1=x0 + 80, top=top, bottom=top + 15)
