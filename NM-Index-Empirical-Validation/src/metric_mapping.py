"""Source contracts, not metric formulas. Modified metrics are not baselines."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    label: str
    table: str
    column: str
    output: str
    id_column: str = 'author_id'
    status: str = ''
    grain: str = 'author'


SOURCES = (
    Source('NM-index', 'author_nm_index', 'nm_index', 'nm_index'),
    Source('Total Cites Score (NM component)', 'author_total_cites', 'total_cites_score', 'total_cites_score', status='calculation_complete'),
    Source('Citations per paper (NM component)', 'author_citations_per_paper', 'citations_per_paper_score', 'citations_per_paper_score', status='calculation_complete'),
    Source('Citation rate (NM component)', 'author_citation_rate', 'citation_rate_score', 'citation_rate_score', status='calculation_complete'),
    Source('Modified hf (NM component)', 'author_modified_hindex', 'modified_hindex_final', 'modified_hf_index', status='calculation_status'),
    Source('Modified hm (NM component)', 'author', 'modified_hm_index', 'modified_hm_index'),
    Source('Modified g (NM component)', 'modified_g_index_results', 'modified_g_index', 'modified_g_index', status='calculation_complete'),
    Source('Modified g (author mirror)', 'author', 'modified_g_index', 'author_modified_g_index'),
    Source('NM-index (author mirror)', 'author', 'nm_index', 'author_nm_index_mirror'),
    Source('Adjusted citations (paper-author records)', 'author_paper_adjusted_citations', 'total_adjusted_citation', 'paper_adjusted_citations', id_column='target_author_id', grain='paper-author'),
    Source('Raw citations (paper-author records)', 'author_paper_adjusted_citations', 'total_raw_citation', 'paper_raw_citations', id_column='target_author_id', grain='paper-author'),
    Source('h-index (legacy candidate)', 'author_metrics', 'h_index', 'legacy_h_index'),
    Source('Total cites (legacy candidate)', 'author_metrics', 'total_citations', 'legacy_total_citations'),
    Source('C-score (legacy candidate; different definition)', 'author_metrics', 'c_index', 'legacy_c_index'),
)

REQUIRED = (
    ('NM-index', 'author_nm_index', 'nm_index', 'Stored final six-component percentile result. Inspect metrics_available; do not use the author mirror or backend H-squared/publication helper.'),
    ('Total cites', 'publication; author_contribution_weight; author_metrics (legacy candidate)', 'total_citation; pub_id; author1id..author10id; author_metrics.total_citations', 'Raw author-level total is not author_total_cites.total_cites_score, which is weighted/normalized. Paper totals require aggregation; legacy totals require ID/provenance verification.'),
    ('C-score raw', '', '', 'No verified stored experiment-design C-score. Backend c_index is total minus self citations; the UI C Score is total_cites_score. Neither is assumed equivalent.'),
    ('C-score SC adjusted', 'author_paper_adjusted_citations', 'target_author_id; cited_pub_id; total_adjusted_citation', 'Adjusted paper-author citations are inputs, not a stored C-score. Exact baseline definition is required.'),
    ('h-index', 'author_metrics (legacy candidate); publication; author_contribution_weight', 'h_index; total_citation; pub_id; author1id..author10id', 'Legacy h_index belongs to the plural authors schema. The research dashboard computes h-index at query time. No calculation or cross-schema identity inference here.'),
    ('hm-index', 'author (modified metric only)', 'modified_hm_index', 'Modified hm is an NM component, not automatically the conventional hm baseline.'),
    ('hf-index', 'author_modified_hindex (modified metric only)', 'modified_hindex_final', 'Modified hf is an NM component, not automatically the conventional hf baseline.'),
    ('g-index', 'modified_g_index_results; author (modified metrics only)', 'modified_g_index', 'Modified g is not automatically conventional g. Both stored modified-g locations are inspected separately.'),
    ('m-index', '', '', 'No verified stored baseline. Requires exact design definition and suitable citation/career data.'),
    ('Fi-score', '', '', 'No verified stored baseline. Exact experiment-design definition is required.'),
    ('s-index', '', '', 'No verified stored baseline. Exact experiment-design definition is required.'),
    ('AR-index', '', '', 'No verified stored baseline. Exact experiment-design definition and paper age/citation data are required.'),
)


def required_mapping(coverage):
    """Availability means a verified required metric with usable cohort values."""
    rows = []
    for metric, table, columns, notes in REQUIRED:
        available = metric == 'NM-index' and coverage.get(metric, 0) > 0
        rows.append(dict(metric=metric, available='YES' if available else 'NO',
                         source_table=table, source_columns=columns,
                         requires_calculation=('NO' if metric == 'NM-index' else 'YES'),
                         notes=notes + ('' if metric == 'NM-index' else ' No verified stored conventional baseline result is available in this Phase 3 inspection. See the current baseline specification before any later calculation; this phase does not calculate it.')))
    return rows
