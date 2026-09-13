"""
Pure in-memory tests for step_Hf_a.py -- no database required.

No log-transform step here (unlike T_a/S_a/U_a), so there is no
L_Hf column to test -- ranking is applied directly to the raw Hf_a
value. Every expected value is either given directly in the
walkthrough this module implements, or a direct plug-in of the stated
formula (computed once by calculator, shown in the comment above the
assertion).

Run:  pytest Nm_index_step_by_step/test_step_Hf_a.py -v
"""

import pandas as pd
import pytest

from Nm_index_step_by_step.step_Hf_a import process_Hf_a


def _frame(author_ids, hf_values):
    return pd.DataFrame({"author_id": author_ids, "Hf_a": hf_values})


# =================================================================
# Step 3: rank(Hf_a) directly, method="average" (fractional ranking,
# no log transform) -- per Eq. 24's "fractional ranking ... for the
# hm, hf, g indices (as they contain many ties)"
# =================================================================

def test_no_log_column_is_produced():
    df = _frame(["a"], [5.0])
    out = process_Hf_a(df)
    assert "L_Hf" not in out.columns


def test_ranking_is_fractional_by_default():
    # Hf value  rank (fractional -- tied pair splits ranks 1-2 -> 1.5)
    # 0         1.5
    # 0         1.5
    # 1         3
    # 2         4
    # 5         5
    df = _frame(["A001", "A002", "A003", "A004", "A005"], [0.0, 0.0, 1.0, 2.0, 5.0])
    out = process_Hf_a(df).set_index("author_id")

    assert out.loc["A001", "rank_Hf"] == pytest.approx(1.5)
    assert out.loc["A002", "rank_Hf"] == pytest.approx(1.5)
    assert out.loc["A003", "rank_Hf"] == 3
    assert out.loc["A004", "rank_Hf"] == 4
    assert out.loc["A005", "rank_Hf"] == 5


# =================================================================
# Step 4/5/6: Blom plotting position + inverse-normal round trip
# =================================================================

def test_blom_lowest_rank_matches_worked_example():
    # N_Hf = 2143, lowest rank = 1
    # P_Hf = (1 - 0.375) / (2143 + 0.25) = 0.00029161320424588824
    n_authors = 2143
    hf_values = list(range(n_authors))  # distinct -> ranks 1..N_Hf unambiguous
    df = _frame([f"auth{i}" for i in range(n_authors)], hf_values)

    out = process_Hf_a(df)
    row = out[out["rank_Hf"] == 1].iloc[0]

    expected_p = (1 - 0.375) / (n_authors + 0.25)
    assert expected_p == pytest.approx(0.00029161320424588824)
    assert row["P_Hf"] == pytest.approx(expected_p)
    assert int(out["N_Hf"].iloc[0]) == n_authors


def test_blom_and_percentile_round_trip():
    # N_Hf = 2143, rank_Hf = 1500
    # P_Hf   = (1500 - 0.375) / (2143 + 0.25) = 0.6996967222675843
    # Nor_Hf = norm.ppf(P_Hf)               = 0.5235284538316998
    # Per_Hf = 100 * norm.cdf(Nor_Hf)       = 69.96967222675843
    n_authors = 2143
    target_rank = 1500
    hf_values = list(range(n_authors))
    df = _frame([f"auth{i}" for i in range(n_authors)], hf_values)

    out = process_Hf_a(df)
    row = out[out["rank_Hf"] == target_rank].iloc[0]

    assert row["P_Hf"] == pytest.approx(0.6996967222675843)
    assert row["Nor_Hf"] == pytest.approx(0.5235284538316998)
    assert row["Per_Hf"] == pytest.approx(69.96967222675843)

    # Algebraic shortcut check: Per_Hf == 100 * P_Hf for every author,
    # since Phi(Phi^-1(P)) == P identically.
    scored = out[out["Hf_a"].notna()]
    diffs = (scored["Per_Hf"] - 100.0 * scored["P_Hf"]).abs()
    assert (diffs < 1e-9).all()


# =================================================================
# Missing data: NULL Hf_a is dropped, never treated as zero
# =================================================================

def test_null_hf_a_is_excluded_not_zeroed():
    df = _frame(["a", "b", "c"], [None, 1.0, 5.0])
    out = process_Hf_a(df)

    row_a = out.set_index("author_id").loc["a"]
    assert pd.isna(row_a["rank_Hf"])
    assert pd.isna(row_a["P_Hf"])
    assert pd.isna(row_a["Nor_Hf"])
    assert pd.isna(row_a["Per_Hf"])

    assert int(out["N_Hf"].iloc[0]) == 2


def test_all_null_raises():
    df = _frame(["a", "b"], [None, None])
    with pytest.raises(ValueError):
        process_Hf_a(df)


def test_missing_column_raises():
    with pytest.raises(ValueError):
        process_Hf_a(pd.DataFrame({"author_id": ["a"]}))


# =================================================================
# Rank method override -- "min" is the alternative, not the default
# =================================================================

def test_min_ranking_override():
    df = _frame(["a", "b", "c"], [0.0, 0.0, 5.0])
    out = process_Hf_a(df, rank_method="min").set_index("author_id")
    assert out.loc["a", "rank_Hf"] == 1
    assert out.loc["b", "rank_Hf"] == 1
    assert out.loc["c", "rank_Hf"] == 3
