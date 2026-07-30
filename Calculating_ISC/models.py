from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class CitationPair:
    """
    One citation relationship:

    citing_pub_id cites cited_pub_id.
    """

    cited_pub_id: str
    citing_pub_id: str


@dataclass(frozen=True)
class AuthorWeight:
    """
    Overall normalized author contribution
    for one publication.
    """

    author_id: str
    weight: Decimal


@dataclass(frozen=True)
class FieldData:
    """
    Field name and field weight of a publication.
    """

    field_name: str
    field_weight: Decimal


@dataclass(frozen=True)
class ISCResult:
    """
    Stores Equation 7 and Equation 8 results
    for one:

        cited paper
        citing paper
        target author
        field
    """

    cited_pub_id: str
    citing_pub_id: str
    target_author_id: str

    field_name: str
    field_weight: Decimal

    target_author_overall_weight: Decimal

    self_author_ids: list[str]
    core_author_ids: list[str]
    non_overlap_author_ids: list[str]

    self_influence_sum: Decimal
    core_influence_sum: Decimal
    non_overlap_influence_sum: Decimal

    core_author_count: int

    epsilon_zero: Decimal
    epsilon_value: Decimal

    isc_numerator: Decimal
    isc_denominator: Decimal

    # Equation 7
    isc_value: Decimal

    # Equation 8
    raw_citation: Decimal
    adjusted_citation: Decimal


@dataclass(frozen=True)
class PaperAdjustedCitationResult:
    """
    Equation 9 result for one cited paper
    and one target author.
    """

    cited_pub_id: str
    target_author_id: str

    citing_paper_count: int
    field_row_count: int

    total_raw_citation: Decimal
    total_adjusted_citation: Decimal