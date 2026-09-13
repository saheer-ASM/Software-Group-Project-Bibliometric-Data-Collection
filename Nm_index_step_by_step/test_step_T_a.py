"""
Pure in-memory tests for step_T_a.py -- no database required.

Every expected value is either given directly in the walkthrough this
module implements, or is a direct plug-in of the stated formula
(computed once by hand / calculator and shown in the comment above the
assertion).

Run:  pytest Nm_index_step_by_step/test_step_T_a.py -v
"""

import math

import pandas as pd
import pytest
from scipy.stats import norm

from Nm_index_step_by_step.step_T_a import process_T_a


def _frame(author_ids, t_values):
    return pd.DataFrame({"author_id": author_ids, "T_a": t_values})


# =================================================================
# Step 2: L_T = log10(T_a + 1)
# =================================================================

def test_log_transform_matches_worked_example():
    # T_a = 10 -> L_T = log10(11) = 1.0414 (rounded to 4dp in the example)
    df = _frame(["a"], [10.0])
    out = process_T_a(df)
    assert out.loc[0, "L_T"] == pytest.approx(math.log10(11), rel=1e-9)
    assert round(out.loc[0, "L_T"], 4) == 1.0414


# =================================================================
# Step 3: rank(L_T), method="min" ("normal"/competition ranking)
# =================================================================

def test_ranking_matches_worked_example_table():
    # Author  T_a  L_T      Rank
    # A001    0    0        1
    # A002    0    0        1
    # A003    2    0.477    3
    # A004    5    0.778    4
    # A005    10   1.041    5
    df = _frame(
        ["A001", "A002", "A003", "A004", "A005"],
        [0.0, 0.0, 2.0, 5.0, 10.0],
    )
    out = process_T_a(df).set_index("author_id")

    assert out.loc["A001", "L_T"] == pytest.approx(0.0)
    assert out.loc["A002", "L_T"] == pytest.approx(0.0)
    assert out.loc["A003", "L_T"] == pytest.approx(0.4771, abs=1e-4)
    assert out.loc["A004", "L_T"] == pytest.approx(0.7782, abs=1e-4)
    assert out.loc["A005", "L_T"] == pytest.approx(1.0414, abs=1e-4)

    assert out.loc["A001", "rank_T"] == 1
    assert out.loc["A002", "rank_T"] == 1
    assert out.loc["A003", "rank_T"] == 3
    assert out.loc["A004", "rank_T"] == 4
    assert out.loc["A005", "rank_T"] == 5


# =================================================================
# Step 4: Blom plotting position, P_T = (r - 0.375) / (N + 0.25)
# =================================================================

def test_blom_plotting_position_matches_worked_example():
    # N_T = 2507, r_T = 1000
    # P_T = (1000 - 0.375) / (2507 + 0.25) = 999.625 / 2507.25
    #     = 0.3986937880147572   (computed once, exact division)
    n_authors = 2507
    target_rank = 1000

    # Build N_T authors with distinct T_a so ranks 1..N_T are unambiguous,
    # then read off the author sitting at rank 1000.
    t_values = list(range(n_authors))  # 0, 1, 2, ..., N_T-1 -> ranks 1..N_T
    df = _frame([f"auth{i}" for i in range(n_authors)], t_values)

    out = process_T_a(df)
    row = out[out["rank_T"] == target_rank].iloc[0]

    expected_p = (target_rank - 0.375) / (n_authors + 0.25)
    assert expected_p == pytest.approx(0.3986937880147572)
    assert row["P_T"] == pytest.approx(expected_p)
    assert int(out["N_T"].iloc[0]) == n_authors


# =================================================================
# Step 5: Nor_T = Phi^-1(P_T);  Per_T = 100 * Phi(Nor_T)
# =================================================================

def test_percentile_round_trip_matches_worked_example():
    # Same N_T=2507, r_T=1000 case as above.
    # P_T    = 0.3986937880147572
    # Nor_T  = norm.ppf(P_T) = -0.25672952704061175
    # Per_T  = 100 * norm.cdf(Nor_T) = 39.86937880147572
    n_authors = 2507
    target_rank = 1000
    t_values = list(range(n_authors))
    df = _frame([f"auth{i}" for i in range(n_authors)], t_values)

    out = process_T_a(df)
    row = out[out["rank_T"] == target_rank].iloc[0]

    assert row["Nor_T"] == pytest.approx(-0.25672952704061175)
    assert row["Per_T"] == pytest.approx(39.86937880147572)

    # The algebraic shortcut Eq. 25/26 reduce to: Per_T == 100 * P_T,
    # because Phi(Phi^-1(P_T)) == P_T identically.
    assert row["Per_T"] == pytest.approx(100.0 * row["P_T"])


def test_per_t_equals_100_times_p_t_for_every_author():
    df = _frame(
        ["a", "b", "c", "d", "e"],
        [0.0, 0.0, 2.0, 5.0, 10.0],
    )
    out = process_T_a(df)
    scored = out[out["T_a"].notna()]
    diffs = (scored["Per_T"] - 100.0 * scored["P_T"]).abs()
    assert (diffs < 1e-9).all()


# =================================================================
# Missing data: NULL T_a is dropped, never treated as zero
# =================================================================

def test_null_t_a_is_excluded_not_zeroed():
    df = _frame(["a", "b", "c"], [None, 5.0, 10.0])
    out = process_T_a(df)

    row_a = out.set_index("author_id").loc["a"]
    assert pd.isna(row_a["L_T"])
    assert pd.isna(row_a["rank_T"])
    assert pd.isna(row_a["P_T"])
    assert pd.isna(row_a["Nor_T"])
    assert pd.isna(row_a["Per_T"])

    # N_T only counts the 2 authors who actually have a T_a value.
    assert int(out["N_T"].iloc[0]) == 2


def test_all_null_raises():
    df = _frame(["a", "b"], [None, None])
    with pytest.raises(ValueError):
        process_T_a(df)


def test_missing_column_raises():
    with pytest.raises(ValueError):
        process_T_a(pd.DataFrame({"author_id": ["a"]}))


# =================================================================
# Rank method override
# =================================================================

def test_average_ranking_alternative():
    # Same tie (two zeros) but with fractional ("average") ranking
    # instead of the default "min": the tied pair averages ranks 1,2 -> 1.5
    df = _frame(["a", "b", "c"], [0.0, 0.0, 5.0])
    out = process_T_a(df, rank_method="average")
    out = out.set_index("author_id")
    assert out.loc["a", "rank_T"] == pytest.approx(1.5)
    assert out.loc["b", "rank_T"] == pytest.approx(1.5)
    assert out.loc["c", "rank_T"] == 3
