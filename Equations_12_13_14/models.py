from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class FieldAdjustedCitationAverage:
    """
    Field-only (all publication years combined) average of the
    Equation 9 adjusted citations for one field.

    This supplies TC_bar_f, the denominator used by Equation 13.
    """

    field_name: str
    publication_count: int
    distinct_publication_count: int
    sum_adjusted_citations: Decimal
    citation_avg_field: Optional[Decimal]
    field_weight_sum: Decimal
    weighted_sum_adjusted_citations: Decimal
    weighted_citation_avg_field: Optional[Decimal]
    data_coverage_ratio: Decimal


@dataclass(frozen=True)
class FieldCitationPercentileCap:
    """
    Equation 12 field-level cap threshold R_{k,f}^{adj}.

    Computed as the k-th percentile (continuous / linear
    interpolation) of Equation 9 adjusted citations observed
    for every (author, publication) row in field f.
    """

    field_name: str
    percentile_k: Decimal
    sample_size: int
    min_adjusted_citation: Decimal
    max_adjusted_citation: Decimal
    cap_threshold: Decimal
    outlier_count: int


@dataclass(frozen=True)
class Equation13DetailRow:
    """
    One (author, publication, field) row combining Equation 12
    (outlier capping) and Equation 13 (outlier-controlled,
    field-normalized citations per paper).
    """

    author_id: str
    pub_id: str
    field_name: str

    adjusted_citation: Optional[Decimal]
    percentile_k: Decimal
    cap_threshold: Optional[Decimal]
    capped_adjusted_citation: Optional[Decimal]
    was_capped: bool

    author_field_weight: Decimal
    publication_count: int
    field_average: Optional[Decimal]

    normalized_citation_ratio: Optional[Decimal]
    paper_field_contribution: Optional[Decimal]

    calculation_status: str


@dataclass(frozen=True)
class AuthorCitationsPerPaperResult:
    """
    Equation 13 final author-level result: S_a.
    """

    author_id: str
    career_factor: Decimal
    publication_count: int

    field_row_count: int
    included_field_row_count: int
    provisional_field_row_count: int
    skipped_field_row_count: int

    normalized_contribution_sum: Decimal
    citations_per_paper_score: Optional[Decimal]

    calculation_complete: bool


@dataclass(frozen=True)
class Equation14DetailRow:
    """
    One (author, publication, field) row combining Equation 12
    (outlier capping) and Equation 14 (outlier-controlled, field-
    and year-normalized citation rate).
    """

    author_id: str
    pub_id: str
    field_name: str
    publication_year: int

    adjusted_citation: Optional[Decimal]
    percentile_k: Decimal
    cap_threshold: Optional[Decimal]
    capped_adjusted_citation: Optional[Decimal]
    was_capped: bool

    author_field_weight: Decimal
    years_elapsed: int
    field_year_average: Optional[Decimal]

    normalized_citation_ratio: Optional[Decimal]
    paper_field_contribution: Optional[Decimal]

    calculation_status: str


@dataclass(frozen=True)
class AuthorCitationRateResult:
    """
    Equation 14 final author-level result: U_a.
    """

    author_id: str
    career_factor: Decimal
    as_of_year: int

    field_row_count: int
    included_field_row_count: int
    provisional_field_row_count: int
    skipped_field_row_count: int

    normalized_contribution_sum: Decimal
    citation_rate_score: Optional[Decimal]

    calculation_complete: bool
