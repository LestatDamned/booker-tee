from dataclasses import dataclass
from typing import Literal

from app.features.imports.mapping.coordinate_dto import (
    CoordinateFieldRole,
    CoordinateMappingSpec,
    CoordinatePageLayout,
    NormalizedRect,
)

ASPECT_RATIO_TOLERANCE = 0.03


@dataclass(frozen=True)
class CoordinateValidationIssue:
    field: str
    message: str


class CoordinateMappingValidator:
    @staticmethod
    def validate(
        spec: CoordinateMappingSpec,
        *,
        page_aspect_ratios: list[float],
    ) -> list[CoordinateValidationIssue]:
        issues: list[CoordinateValidationIssue] = []
        required_layouts = {"first"}
        if len(page_aspect_ratios) > 1:
            required_layouts.add("last")
        if len(page_aspect_ratios) > 2:
            required_layouts.add("middle")
        for name in sorted(required_layouts - spec.layouts.keys()):
            issues.append(CoordinateValidationIssue(f"layouts.{name}", "Layout is required."))
        for name, layout in spec.layouts.items():
            issues.extend(_validate_layout(name, layout))
        for index, ratio in enumerate(page_aspect_ratios):
            name = layout_name(index, len(page_aspect_ratios))
            layout = spec.layouts.get(name)
            if layout and abs(layout.page_aspect_ratio / ratio - 1) > ASPECT_RATIO_TOLERANCE:
                issues.append(
                    CoordinateValidationIssue(
                        f"layouts.{name}.pageAspectRatio",
                        "Page aspect ratio does not match the saved layout.",
                    )
                )
        return issues


def layout_name(index: int, page_count: int) -> Literal["first", "middle", "last"]:
    if index == 0:
        return "first"
    if index == page_count - 1:
        return "last"
    return "middle"


def _validate_layout(name: str, layout: CoordinatePageLayout) -> list[CoordinateValidationIssue]:
    prefix = f"layouts.{name}"
    issues: list[CoordinateValidationIssue] = []
    if not 0 <= layout.transaction_top < layout.transaction_bottom <= 1:
        issues.append(CoordinateValidationIssue(prefix, "Transaction bounds are invalid."))
    rectangles = [
        ("sampleRow", layout.sample_row),
        *[(role.value, rect) for role, rect in layout.fields.items()],
    ]
    for field, rect in rectangles:
        if not _valid_rect(rect):
            issues.append(CoordinateValidationIssue(f"{prefix}.{field}", "Rectangle is invalid."))
        elif rect.y0 < layout.transaction_top or rect.y1 > layout.transaction_bottom:
            issues.append(
                CoordinateValidationIssue(
                    f"{prefix}.{field}", "Rectangle must be inside transaction bounds."
                )
            )
    roles = set(layout.fields)
    for role in (CoordinateFieldRole.OPERATION_DATE, CoordinateFieldRole.DESCRIPTION):
        if role not in roles:
            issues.append(
                CoordinateValidationIssue(f"{prefix}.fields", f"{role.value} is required.")
            )
    amount = CoordinateFieldRole.AMOUNT in roles
    split = CoordinateFieldRole.DEBIT in roles or CoordinateFieldRole.CREDIT in roles
    if amount == split or (
        split and not {CoordinateFieldRole.DEBIT, CoordinateFieldRole.CREDIT} <= roles
    ):
        issues.append(
            CoordinateValidationIssue(f"{prefix}.fields", "Choose amount or both debit and credit.")
        )
    fields = list(layout.fields.items())
    for index, (role, rect) in enumerate(fields):
        for other_role, other in fields[index + 1 :]:
            if _overlap(rect, other):
                issues.append(
                    CoordinateValidationIssue(
                        f"{prefix}.fields", f"{role.value} overlaps {other_role.value}."
                    )
                )
    return issues


def _valid_rect(rect: NormalizedRect) -> bool:
    return 0 <= rect.x0 < rect.x1 <= 1 and 0 <= rect.y0 < rect.y1 <= 1


def _overlap(left: NormalizedRect, right: NormalizedRect) -> bool:
    return left.x0 < right.x1 and right.x0 < left.x1
