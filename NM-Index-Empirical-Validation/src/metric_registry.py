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
    entry('c_score_raw', 'READY', 'STANDARD_DEFINITION', RAW + ('author positions',),
          'metrics.standard', 'Schreiber 2008; Hirsch 2005; Jin 2007; Kacem 2020; Ioannidis 2016/2019', 'Ioannidis 2016 six indicators, log(1+x)/cohort max, summed.'),
    entry('c_score_sc_adjusted', 'READY', 'STANDARD_DEFINITION',
          RAW + ('influential_self_citations',), 'metrics.standard', 'Schreiber 2008; Hirsch 2005; Jin 2007; Kacem 2020; Ioannidis 2016/2019',
          'Ioannidis 2019: same six indicators after removing citations from papers sharing any author.'),
    entry('h_index', 'READY', 'EXPLICIT', RAW, 'metrics.h_index', DESIGN + '; ' + MANUSCRIPT + ' p. 2'),
    entry('hm_index', 'READY', 'STANDARD_DEFINITION', RAW + ('author count (10-slot cap)',),
          'metrics.standard', 'Schreiber 2008; Hirsch 2005; Jin 2007; Kacem 2020; Ioannidis 2016/2019', 'Schreiber 2008 effective rank sum 1/N.'),
    entry('hf_index', 'READY_INPUT_GATED', 'EXPLICIT', RAW + ('verified complete coauthor counts',),
          'metrics.hf_index', MANUSCRIPT + ' pp. 2, 22-25',
          'Conventional fractional citations use c_p/N_p, then an h threshold; not NM modified hf. Real coauthor completeness unverified.'),
    entry('g_index', 'READY', 'EXPLICIT_WITH_EXAMPLE_CONFLICT', RAW, 'metrics.g_index',
          DESIGN + '; ' + MANUSCRIPT + ' pp. 2, 23, 25', 'Uses written top-g-papers rule, capped by observed paper count; example g=12 is disputed.'),
    entry('m_index', 'READY', 'STANDARD_DEFINITION', RAW + ('publication.year', 'as-of date'),
          'metrics.standard', 'Schreiber 2008; Hirsch 2005; Jin 2007; Kacem 2020; Ioannidis 2016/2019', 'h / (as_of - first_year + 1), as_of 2026.'),
    entry('fi_score', 'READY', 'STANDARD_DEFINITION', RAW,
          'metrics.standard', 'Fiorillo 2024, Publ. Res. Q. 40:70-79',
          'Fi = h^2 / total citations x 100; > 32 flags self-distortion.'),
    entry('s_index', 'READY', 'STANDARD_DEFINITION', ('influential_self_citations',),
          'metrics.standard', 'Schreiber 2008; Hirsch 2005; Jin 2007; Kacem 2020; Ioannidis 2016/2019', 'Kacem 2020: h-index of per-paper self-citation counts.'),
    entry('ar_index', 'READY', 'STANDARD_DEFINITION', RAW + ('publication.year', 'as-of date'),
          'metrics.standard', 'Schreiber 2008; Hirsch 2005; Jin 2007; Kacem 2020; Ioannidis 2016/2019', 'Jin 2007: sqrt(sum h-core c/age), age = as_of - year + 1.'),
)


def registry_records():
    return [asdict(metric) for metric in REGISTRY]


BY_NAME = {metric.metric_name: metric for metric in REGISTRY}
