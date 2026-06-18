from dataclasses import dataclass


@dataclass(frozen=True)
class UnknownStatementColumnCandidate:
    field: str
    column_index: int
    header: str
    confidence: float

    def as_json(self) -> dict[str, object]:
        return {
            "field": self.field,
            "column_index": self.column_index,
            "header": self.header,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class UnknownStatementColumnProfile:
    column_index: int
    header: str
    sample_count: int
    non_empty_count: int
    date_like_count: int
    money_like_count: int
    currency_like_count: int
    description_like_count: int
    header_matches: list[str]

    def as_json(self) -> dict[str, object]:
        return {
            "column_index": self.column_index,
            "header": self.header,
            "sample_count": self.sample_count,
            "non_empty_count": self.non_empty_count,
            "date_like_count": self.date_like_count,
            "money_like_count": self.money_like_count,
            "currency_like_count": self.currency_like_count,
            "description_like_count": self.description_like_count,
            "header_matches": self.header_matches,
        }
