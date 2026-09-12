"""
Pure in-memory tests for step_Hm_a.py -- no database required.

Same shape as test_step_Hf_a.py; no log-transform step here, and the
default ranking is fractional ("average"), per Eq. 24's wording for
the hf/hm/g indices. Every expected value is either given directly in
the walkthrough this module implements, or a direct plug-in of the
stated formula (computed once by calculator, shown in the comment
above the assertion).

Run:  pytest Nm_index_step_by_step/test_step_Hm_a.py -v
"""

import pandas as pd
import pytest

from Nm_index_step_by_step.step_Hm_a import process_Hm_a


def _frame(author_ids, hm_values):
    return pd.DataFrame({"author_id": author_ids, "Hm_a": hm_values})


# =================================================================
# Step 3: rank(Hm_a) directly, method="average" (fractional ranking,
# no log transform)
# =================================================================

def test_no_log_column_is_produced():
    df = _frame(["a"], [5.0])
    out = process_Hm_a(df)
    assert "L_Hm" not in out.columns


def test_ranking_is_fractional_by_default():
    # Hm value  rank (fractional -- tied pair splits ranks 1-2 -> 1.5)
    # 0         1.5
    # 0         1.5
    # 1         3
    # 2         4
    # 5         5
    df = _frame(["A001", "A002", "A003", "A004", "A005"], [0.0, 0.0, 1.0, 2.0, 5.0])
    out = process_Hm_a(df).set_index("author_id")

    assert out.loc["A001", "rank_Hm"] == pytest.approx(1.5)
    assert out.loc["A002", "rank_Hm"] == pytest.approx(1.5)
    assert out.loc["A003", "rank_Hm"] == 3
    assert out.loc["A004", "rank_Hm"] == 4
    assert out.loc["A005", "rank_Hm"] == 5


# =================================================================
# Step 4/5/6: Blom plotting position + inverse-normal round trip
# =================================================================

def test_blom_lowest_rank():
    # N_Hm = 2254, lowest rank = 1
    # P_Hm = (1 - 0.375) / (2254 + 0.25) = 0.00027725407563491185
    n_authors = 2254
    hm_values = list(range(n_authors))  # distinct -> ranks 1..N_Hm unambiguous
    df = _frame([f"auth{i}" for i in range(n_authors)], hm_values)

    out = process_Hm_a(df)
    row = out[out["rank_Hm"] == 1].iloc[0]

    expected_p = (1 - 0.375) / (n_authors + 0.25)
    assert expected_p == pytest.approx(0.00027725407563491185)
    assert row["P_Hm"] == pytest.approx(expected_p)
    assert int(out["N_Hm"].iloc[0]) == n_authors


def test_blom_and_percentile_round_trip():
    # N_Hm = 2254, rank_Hm = 1500
    # P_Hm   = (1500 - 0.375) / (2254 + 0.25) = 0.6652434290784075
    # Nor_Hm = norm.ppf(P_Hm)               = 0.42681628814421546
    # Per_Hm = 100 * norm.cdf(Nor_Hm)       = 66.52434290784075
    n_authors = 2254
    target_rank = 1500
    hm_values = list(range(n_authors))
    df = _frame([f"auth{i}" for i in range(n_authors)], hm_values)

    out = process_Hm_a(df)
    row = out[out["rank_Hm"] == target_rank].iloc[0]

    assert row["P_Hm"] == pytest.approx(0.6652434290784075)
    assert row["Nor_Hm"] == pytest.approx(0.42681628814421546)
    assert row["Per_Hm"] == pytest.approx(66.52434290784075)

    # Algebraic shortcut check: Per_Hm == 100 * P_Hm for every author,
    # since Phi(Phi^-1(P)) == P identically.
    scored = out[out["Hm_a"].notna()]
    diffs = (scored["Per_Hm"] - 100.0 * scored["P_Hm"]).abs()
    assert (diffs < 1e-9).all()


# =================================================================
# Missing data: NULL Hm_a is dropped, never treated as zero
# =================================================================

def test_null_hm_a_is_excluded_not_zeroed():
    df = _frame(["a", "b", "c"], [None, 1.0, 5.0])
    out = process_Hm_a(df)

    row_a = out.set_index("author_id").loc["a"]
    assert pd.isna(row_a["rank_Hm"])
    assert pd.isna(row_a["P_Hm"])
    assert pd.isna(row_a["Nor_Hm"])
    assert pd.isna(row_a["Per_Hm"])

    assert int(out["N_Hm"].iloc[0]) == 2


def test_all_null_raises():
    df = _frame(["a", "b"], [None, None])
    with pytest.raises(ValueError):
        process_Hm_a(df)


def test_missing_column_raises():
    with pytest.raises(ValueError):
        process_Hm_a(pd.DataFrame({"author_id": ["a"]}))


# =================================================================
# Rank method override -- "min" is the alternative, not the default
# =================================================================

def test_min_ranking_override():
    df = _frame(["a", "b", "c"], [0.0, 0.0, 5.0])
    out = process_Hm_a(df, rank_method="min").set_index("author_id")
    assert out.loc["a", "rank_Hm"] == 1
    assert out.loc["b", "rank_Hm"] == 1
    assert out.loc["c", "rank_Hm"] == 3
