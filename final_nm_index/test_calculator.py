"""
Pure in-memory tests for NmIndexCalculator -- no database required.

Every expected value is derived by hand in the comments above the
assertion. The only library "special function" leaned on is the
standard-normal CDF (scipy.stats.norm.cdf), which stands in for the
paper's phi() exactly as Eq. 25/26 intend.

Run:  pytest "final_nm_index/test_calculator.py" -v
      (from the repo root, or:  python -m pytest test_calculator.py -v
       from inside this folder if it is importable as a package)
"""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from final_nm_index.calculator import NmIndexCalculator

ALL_METRICS = [
    "total_cites",
    "citations_per_paper",
    "citation_rate",
    "modified_hf_index",
    "modified_hm_index",
    "modified_g_index",
]


def _frame(rows):
    return pd.DataFrame(rows)


LOGNORMAL_ALL = {
    "total_cites": "lognormal",
    "citations_per_paper": "lognormal",
    "citation_rate": "lognormal",
}


# =================================================================
# RANK metric: Blom plotting position on fractional ranks (Eq. 24/26)
# =================================================================

def test_rank_metric_plotting_position():
    # 4 authors, modified_hm_index = [0, 0, 5, 10]
    # N = 4, a = 0.375, denominator = N + 1 - 2a = 4.25
    # fractional ranks (ties -> average): 0->1.5, 0->1.5, 5->3, 10->4
    # P = (r - 0.375) / 4.25
    #   0  -> 1.125 / 4.25 = 0.2647058824
    #   5  -> 2.625 / 4.25 = 0.6176470588
    #   10 -> 3.625 / 4.25 = 0.8529411765
    # Per = 100 * P   (RANK metrics: Per(x) = 100 * P(x))
    df = _frame({
        "author_id": ["a", "b", "c", "d"],
        "modified_hm_index": [0.0, 0.0, 5.0, 10.0],
    })

    calc = NmIndexCalculator(require_all_metrics=False)
    out = calc.calculate(df).set_index("author_id")

    assert out.loc["a", "per_modified_hm_index"] == pytest.approx(26.4705882353)
    assert out.loc["b", "per_modified_hm_index"] == pytest.approx(26.4705882353)
    assert out.loc["c", "per_modified_hm_index"] == pytest.approx(61.7647058824)
    assert out.loc["d", "per_modified_hm_index"] == pytest.approx(85.2941176471)


# =================================================================
# LOG metric, lognormal assumption: Z-score of log10(x+1) (Eq. 24/25/26)
# =================================================================

def test_log_metric_lognormal_zscore():
    # 3 authors, total_cites = [0, 9, 99]
    # L = log10(x + 1) = [0, 1, 2]
    # mean(L) = 1 ; std(L, ddof=0) = sqrt((1 + 0 + 1) / 3) = 0.8164965809
    # z = (L - 1) / 0.8164965809 = [-1.2247448714, 0, 1.2247448714]
    # Per = 100 * phi(z)
    df = _frame({
        "author_id": ["a", "b", "c"],
        "total_cites": [0.0, 9.0, 99.0],
    })

    calc = NmIndexCalculator(
        require_all_metrics=False, distribution=LOGNORMAL_ALL
    )
    out = calc.calculate(df).set_index("author_id")

    expected = 100.0 * norm.cdf([-1.2247448714, 0.0, 1.2247448714])
    assert out.loc["a", "per_total_cites"] == pytest.approx(expected[0])
    assert out.loc["b", "per_total_cites"] == pytest.approx(50.0)
    assert out.loc["c", "per_total_cites"] == pytest.approx(expected[2])


def test_log_metric_constant_column_is_median_percentile():
    # All identical -> std = 0 -> z = 0 -> Per = 50 for everyone.
    df = _frame({
        "author_id": ["a", "b", "c"],
        "citation_rate": [4.0, 4.0, 4.0],
    })
    out = NmIndexCalculator(
        require_all_metrics=False, distribution=LOGNORMAL_ALL
    ).calculate(df)
    assert out["per_citation_rate"].tolist() == pytest.approx([50.0, 50.0, 50.0])


# =================================================================
# LOG metric, hooked assumption: Per = 100 * P(log10(x+1))
# =================================================================

def test_log_metric_hooked_assumption():
    # total_cites = [0, 9, 99] -> L = [0, 1, 2], all distinct
    # ranks = [1, 2, 3], N = 3, denom = 3 + 1 - 0.75 = 3.25
    # P = (r - 0.375) / 3.25 = [0.1923076923, 0.5, 0.8076923077]
    # Per = 100 * P
    df = _frame({
        "author_id": ["a", "b", "c"],
        "total_cites": [0.0, 9.0, 99.0],
    })
    calc = NmIndexCalculator(
        require_all_metrics=False,
        distribution={
            "total_cites": "hooked",
            "citations_per_paper": "lognormal",
            "citation_rate": "lognormal",
        },
    )
    out = calc.calculate(df).set_index("author_id")
    assert out.loc["a", "per_total_cites"] == pytest.approx(19.2307692308)
    assert out.loc["b", "per_total_cites"] == pytest.approx(50.0)
    assert out.loc["c", "per_total_cites"] == pytest.approx(80.7692307692)


# =================================================================
# Eq. 27: weighted average with renormalisation over available metrics
# =================================================================

def test_weighted_average_renormalises_over_available_metrics():
    # One author, equal 1/6 weights, only 3 of 6 metrics present.
    # With 2+ authors so percentiles are well defined; check author "a".
    #
    # total_cites:        a=0,  b=9,  c=99  (lognormal, as above)
    #   -> per_a = 100 * phi(-1.2247448714)
    # citations_per_paper: a=0,  b=0,  c=0   -> all 50
    # citation_rate:       a=10, b=1,  c=100
    #   L = log10([11, 2, 101]) = [1.0413926852, 0.3010299957, 2.0043213738]
    #   mean = 1.1155813516 ; std(ddof=0):
    #     devs = [-0.0741886664, -0.8145513559, 0.8887400222]
    #     var = (0.005503957 + 0.663493887 + 0.789858810) / 3 = 0.486285551
    #     std = 0.697341774
    #   z_a = -0.0741886664 / 0.697341774 = -0.1063854247
    #   per_a = 100 * phi(-0.1063854247)
    #
    # modified_hf_index / modified_hm_index / modified_g_index: all NaN for a
    #
    # metrics_available = 3, each weight 1/6, renormalised sum = 0.5
    # nm_a = mean(per_total_cites_a, per_citations_per_paper_a, per_citation_rate_a)
    df = _frame({
        "author_id": ["a", "b", "c"],
        "total_cites": [0.0, 9.0, 99.0],
        "citations_per_paper": [0.0, 0.0, 0.0],
        "citation_rate": [10.0, 1.0, 100.0],
    })

    out = NmIndexCalculator(
        require_all_metrics=False, distribution=LOGNORMAL_ALL
    ).calculate(df)
    row = out.set_index("author_id").loc["a"]

    per_tc = 100.0 * norm.cdf(-1.2247448714)
    per_cpp = 50.0
    per_cr = 100.0 * norm.cdf(-0.1063854247)
    expected_nm = (per_tc + per_cpp + per_cr) / 3.0

    assert row["metrics_available"] == 3
    assert row["per_total_cites"] == pytest.approx(per_tc, rel=1e-6)
    assert row["per_citation_rate"] == pytest.approx(per_cr, rel=1e-4)
    assert row["nm_index"] == pytest.approx(expected_nm, rel=1e-4)


def test_require_all_metrics_blanks_incomplete_authors():
    df = _frame({
        "author_id": ["a", "b"],
        "total_cites": [1.0, 2.0],
        "citations_per_paper": [1.0, 2.0],
        "citation_rate": [1.0, 2.0],
        "modified_hf_index": [1.0, 2.0],
        "modified_hm_index": [1.0, 2.0],
        # modified_g_index missing entirely
    })
    out = NmIndexCalculator(require_all_metrics=True).calculate(df)
    assert out["nm_index"].isna().all()
    assert (out["metrics_available"] == 5).all()


def test_missing_metric_column_is_tolerated():
    # modified_g_index is not even a column (its table is empty in prod).
    df = _frame({
        "author_id": ["a", "b", "c"],
        "total_cites": [0.0, 5.0, 50.0],
        "citations_per_paper": [0.0, 1.0, 2.0],
        "citation_rate": [0.0, 1.0, 2.0],
        "modified_hf_index": [0.0, 1.0, 3.0],
        "modified_hm_index": [0.0, 1.0, 3.0],
    })
    out = NmIndexCalculator(require_all_metrics=False).calculate(df)
    assert "per_modified_g_index" in out.columns
    assert out["per_modified_g_index"].isna().all()
    assert (out["metrics_available"] == 5).all()
    assert out["nm_index"].notna().all()
    # every component percentile is in [0, 100] -> so is their mean
    assert ((out["nm_index"] >= 0) & (out["nm_index"] <= 100)).all()


def test_author_with_no_metrics_gets_null_nm():
    df = _frame({
        "author_id": ["a", "b"],
        "total_cites": [np.nan, 5.0],
        "citations_per_paper": [np.nan, 5.0],
        "citation_rate": [np.nan, 5.0],
    })
    out = NmIndexCalculator(require_all_metrics=False).calculate(df)
    row_a = out.set_index("author_id").loc["a"]
    assert row_a["metrics_available"] == 0
    assert pd.isna(row_a["nm_index"])


# =================================================================
# Guards
# =================================================================

def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        NmIndexCalculator(weights={m: 0.1 for m in ALL_METRICS})


def test_missing_author_id_column_raises():
    with pytest.raises(ValueError):
        NmIndexCalculator().calculate(pd.DataFrame({"total_cites": [1.0]}))


def test_matches_paper_section_333_mechanism():
    # Section 3.3.3 "Final Nm-Index Calculation" fixes the mechanism:
    #   * T_a, S_a, U_a  -> hooked power law:
    #         L(x) = log10(x+1); P(x) = (r-0.375)/(N+0.25);
    #         Nor = phi^-1(P(L(x)));  Per = 100 * phi(Nor) = 100 * P(L(x))
    #   * Hf', Hm', G'   -> fractional ranking; Per = 100 * P(x)
    #   * Nm_a = (1/6) * sum(Per_i)
    #
    # 5 authors so ranks are unambiguous. author "e" is the top of
    # every metric.
    #   citation metrics: values 0,1,3,7,15 -> L strictly increasing
    #     -> ranks 1..5, N=5, denom = 5 + 1 - 0.75 = 5.25
    #     P(top) = (5 - 0.375)/5.25 = 0.880952381  -> Per = 88.0952381
    #   index metrics: values 0,0,2,4,9
    #     modified_hm_index top -> rank 5 -> same P -> Per = 88.0952381
    # Nm_e = (1/6)*(6 * 88.0952381) = 88.0952381
    df = _frame({
        "author_id": ["a", "b", "c", "d", "e"],
        "total_cites": [0.0, 1.0, 3.0, 7.0, 15.0],
        "citations_per_paper": [0.0, 1.0, 3.0, 7.0, 15.0],
        "citation_rate": [0.0, 1.0, 3.0, 7.0, 15.0],
        "modified_hf_index": [0.0, 0.0, 2.0, 4.0, 9.0],
        "modified_hm_index": [0.0, 0.0, 2.0, 4.0, 9.0],
        "modified_g_index": [0.0, 0.0, 2.0, 4.0, 9.0],
    })

    # default distribution is now "hooked" for all three citation metrics
    out = NmIndexCalculator(require_all_metrics=False).calculate(df)
    row = out.set_index("author_id").loc["e"]

    per_top = 100.0 * (5 - 0.375) / 5.25  # 88.0952380952
    assert row["metrics_available"] == 6
    for col in [
        "per_total_cites",
        "per_citations_per_paper",
        "per_citation_rate",
        "per_modified_hf_index",
        "per_modified_hm_index",
        "per_modified_g_index",
    ]:
        assert row[col] == pytest.approx(per_top)
    assert row["nm_index"] == pytest.approx(per_top)


def test_reference_n_override(monkeypatch):
    # With NM_REFERENCE_N set, N in P(x) = (r - 0.375)/(N + 0.25) is
    # the fixed value, not the cohort size.
    from final_nm_index import config

    monkeypatch.setattr(config, "NM_REFERENCE_N", 100000)

    # 3 authors, modified_hm_index distinct -> ranks 1,2,3
    # top: P = (3 - 0.375)/(100000 + 0.25) = 2.625/100000.25
    df = _frame({
        "author_id": ["a", "b", "c"],
        "modified_hm_index": [1.0, 2.0, 3.0],
    })
    out = NmIndexCalculator(require_all_metrics=False).calculate(df)
    top = out.set_index("author_id").loc["c", "per_modified_hm_index"]
    assert top == pytest.approx(100.0 * 2.625 / 100000.25)


def test_custom_weights_emphasis():
    # 2 authors; put ALL weight on modified_hm_index -> nm == per_modified_hm_index
    weights = {m: 0.0 for m in ALL_METRICS}
    weights["modified_hm_index"] = 1.0
    df = _frame({
        "author_id": ["a", "b", "c"],
        "total_cites": [100.0, 0.0, 0.0],
        "modified_hm_index": [1.0, 2.0, 3.0],
    })
    out = NmIndexCalculator(weights=weights, require_all_metrics=False).calculate(df)
    assert out["nm_index"].tolist() == pytest.approx(
        out["per_modified_hm_index"].tolist()
    )
