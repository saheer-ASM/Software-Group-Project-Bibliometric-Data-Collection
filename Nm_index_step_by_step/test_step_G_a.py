"""
Pure in-memory tests for step_G_a.py -- no database required.

Same shape as test_step_Hf_a.py / test_step_Hm_a.py; no log-transform
step here, and the default ranking is fractional ("average"), per
Eq. 24's wording for the hf/hm/g indices. Every expected value is
either given directly in the walkthrough this module implements, or a
direct plug-in of the stated formula (computed once by calculator,
shown in the comment above the assertion).

Run:  pytest Nm_index_step_by_step/test_step_G_a.py -v
"""

import pandas as pd
import pytest

from Nm_index_step_by_step.step_G_a import process_G_a


def _frame(author_ids, g_values):
    return pd.DataFrame({"author_id": author_ids, "G_a": g_values})


# =================================================================
# Step 3: rank(G_a) directly, method="average" (fractional ranking,
# no log transform)
# =================================================================

def test_no_log_column_is_produced():
    df = _frame(["a"], [5.0])
    out = process_G_a(df)
    assert "L_G" not in out.columns


def test_ranking_is_fractional_by_default():
    # G value  rank (fractional -- tied pair splits ranks 1-2 -> 1.5)
    # 0        1.5
    # 0        1.5
    # 1        3
    # 2        4
    # 5        5
    df = _frame(["A001", "A002", "A003", "A004", "A005"], [0.0, 0.0, 1.0, 2.0, 5.0])
    out = process_G_a(df).set_index("author_id")

    assert out.loc["A001", "rank_G"] == pytest.approx(1.5)
    assert out.loc["A002", "rank_G"] == pytest.approx(1.5)
    assert out.loc["A003", "rank_G"] == 3
    assert out.loc["A004", "rank_G"] == 4
    assert out.loc["A005", "rank_G"] == 5


# =================================================================
# Step 4/5/6: Blom plotting position + inverse-normal round trip
# =================================================================

def test_blom_lowest_rank():
    # N_G = 2143, lowest rank = 1
    # P_G = (1 - 0.375) / (2143 + 0.25) = 0.00029161320424588824
    n_authors = 2143
    g_values = list(range(n_authors))  # distinct -> ranks 1..N_G unambiguous
    df = _frame([f"auth{i}" for i in range(n_authors)], g_values)

    out = process_G_a(df)
    row = out[out["rank_G"] == 1].iloc[0]

    expected_p = (1 - 0.375) / (n_authors + 0.25)
    assert expected_p == pytest.approx(0.00029161320424588824)
    assert row["P_G"] == pytest.approx(expected_p)
    assert int(out["N_G"].iloc[0]) == n_authors


def test_blom_and_percentile_round_trip():
    # N_G = 2143, rank_G = 1700
    # P_G   = (1700 - 0.375) / (2143 + 0.25) = 0.7930129476262685
    # Nor_G = norm.ppf(P_G)               = 0.8169200747726574
    # Per_G = 100 * norm.cdf(Nor_G)       = 79.30129476262684
    n_authors = 2143
    target_rank = 1700
    g_values = list(range(n_authors))
    df = _frame([f"auth{i}" for i in range(n_authors)], g_values)

    out = process_G_a(df)
    row = out[out["rank_G"] == target_rank].iloc[0]

    assert row["P_G"] == pytest.approx(0.7930129476262685)
    assert row["Nor_G"] == pytest.approx(0.8169200747726574)
    assert row["Per_G"] == pytest.approx(79.30129476262684)

    # Algebraic shortcut check: Per_G == 100 * P_G for every author,
    # since Phi(Phi^-1(P)) == P identically.
    scored = out[out["G_a"].notna()]
    diffs = (scored["Per_G"] - 100.0 * scored["P_G"]).abs()
    assert (diffs < 1e-9).all()


# =================================================================
# Missing data: NULL G_a is dropped, never treated as zero
# =================================================================

def test_null_g_a_is_excluded_not_zeroed():
    df = _frame(["a", "b", "c"], [None, 1.0, 5.0])
    out = process_G_a(df)

    row_a = out.set_index("author_id").loc["a"]
    assert pd.isna(row_a["rank_G"])
    assert pd.isna(row_a["P_G"])
    assert pd.isna(row_a["Nor_G"])
    assert pd.isna(row_a["Per_G"])

    assert int(out["N_G"].iloc[0]) == 2


def test_all_null_raises():
    df = _frame(["a", "b"], [None, None])
    with pytest.raises(ValueError):
        process_G_a(df)


def test_missing_column_raises():
    with pytest.raises(ValueError):
        process_G_a(pd.DataFrame({"author_id": ["a"]}))


# =================================================================
# Rank method override -- "min" is the alternative, not the default
# =================================================================

def test_min_ranking_override():
    df = _frame(["a", "b", "c"], [0.0, 0.0, 5.0])
    out = process_G_a(df, rank_method="min").set_index("author_id")
    assert out.loc["a", "rank_G"] == 1
    assert out.loc["b", "rank_G"] == 1
    assert out.loc["c", "rank_G"] == 3
