"""Central source-grounded metric registry used by the execution pipeline."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Metric:
    metric_name: str
    metric_type: str
    source: str
    formula_status: str
    implementation_status: str
    required_inputs: tuple[str, ...]
    output_column: str
    assumptions: str
    definition_reference: str
    calculation_module: str


DESIGN = 'Pasted markdown(7).md, baseline table lines 30-41'
MANUSCRIPT = 'Nm Index novel model (1)(3).pdf'
RAW = ('author.author_id', 'publication.pub_id', 'publication.total_citation',
       'author_contribution_weight.author1id..author10id')


def entry(name, status, formula, inputs, module, reference, assumptions=''):
    return Metric(name, 'baseline', 'LOCAL_CALCULATION' if status in {'READY', 'READY_INPUT_GATED'} else 'APPROVED_STRATEGY_REQUIRED',
                  formula, status, inputs, name, assumptions, reference, module)


REGISTRY = (
    Metric('nm_index', 'target', 'STORED_PRODUCTION_RESULT', 'STORED', 'READY',
           ('author_nm_index.author_id', 'author_nm_index.nm_index'), 'nm_index',
           'Read authoritative score; never recompute.', MANUSCRIPT + ' pp. 12-13', 'nm_index.loader'),
    entry('raw_total_cites', 'READY', 'EXPLICIT', RAW, 'metrics.total_cites', DESIGN + '; ' + MANUSCRIPT + ' p. 21',
          'Stored publication counts are provisional until provenance verified.'),
    entry('c_score_raw', 'METHODOLOGY_PENDING', 'INCOMPLETE', RAW + ('author positions', 'reference distributions'),
          'metrics.c_score', MANUSCRIPT + ' pp. 3, 16-17, 24-25', 'Six indicators named; full construction, attribution and reference normalization absent.'),
    entry('c_score_sc_adjusted', 'METHODOLOGY_PENDING', 'INCOMPLETE',
          RAW + ('complete self-citation attribution', 'adjustment rule'), 'metrics.c_score',
          MANUSCRIPT + ' pp. 13, 26-29', 'Conventional C-score SC-adjustment equation absent; NM ISC is separate.'),
    entry('h_index', 'READY', 'EXPLICIT', RAW, 'metrics.h_index', DESIGN + '; ' + MANUSCRIPT + ' p. 2'),
    entry('hm_index', 'METHODOLOGY_PENDING', 'CONFLICT', RAW + ('complete coauthor counts',),
          'metrics.hm_index', MANUSCRIPT + ' pp. 2, 11, 23-25', 'Original 1/Np rank mentioned; full threshold rule and worked values internally inconsistent.'),
    entry('hf_index', 'READY_INPUT_GATED', 'EXPLICIT', RAW + ('verified complete coauthor counts',),
          'metrics.hf_index', MANUSCRIPT + ' pp. 2, 22-25',
          'Conventional fractional citations use c_p/N_p, then an h threshold; not NM modified hf. Real coauthor completeness unverified.'),
    entry('g_index', 'READY', 'EXPLICIT_WITH_EXAMPLE_CONFLICT', RAW, 'metrics.g_index',
          DESIGN + '; ' + MANUSCRIPT + ' pp. 2, 23, 25', 'Uses written top-g-papers rule, capped by observed paper count; example g=12 is disputed.'),
    entry('m_index', 'METHODOLOGY_PENDING', 'CONVENTION_REQUIRED', RAW + ('publication.year', 'as-of date'),
          'metrics.m_index', DESIGN + '; ' + MANUSCRIPT + ' pp. 2, 22', 'Explicit career-duration convention required.'),
    entry('fi_score', 'METHODOLOGY_PENDING', 'INCOMPLETE', RAW + ('threshold', 'self-citation attribution'),
          'metrics.fi_score', DESIGN + '; ' + MANUSCRIPT + ' p. 2', 'Equation and threshold absent.'),
    entry('s_index', 'METHODOLOGY_PENDING', 'AMBIGUOUS_SOURCE', ('self-citation inputs',),
          'metrics.s_index', DESIGN + '; ' + MANUSCRIPT + ' p. 2', 'Brown b-index reference conflicts with s-index label.'),
    entry('ar_index', 'METHODOLOGY_PENDING', 'INCOMPLETE', RAW + ('publication.year', 'as-of date'),
          'metrics.ar_index', DESIGN + '; ' + MANUSCRIPT + ' p. 2', 'Age-weighting formula absent.'),
)


def registry_records():
    return [asdict(metric) for metric in REGISTRY]


BY_NAME = {metric.metric_name: metric for metric in REGISTRY}
