"""
Pure in-memory tests for step_U_a.py -- no database required.

Same shape as test_step_T_a.py / test_step_S_a.py; every expected
value is either a direct plug-in of the stated formula or a formula
computed once by calculator and shown in the comment above the
assertion.

Run:  pytest Nm_index_step_by_step/test_step_U_a.py -v
"""

import math

import pandas as pd
import pytest

from Nm_index_step_by_step.step_U_a import process_U_a


def _frame(author_ids, u_values):
    return pd.DataFrame({"author_id": author_ids, "U_a": u_values})


# =================================================================
# Step 2: L_U = log10(U_a + 1)
# =================================================================

def test_log_transform():
    # U_a = 10 -> L_U = log10(11) = 1.0414
    df = _frame(["a"], [10.0])
    out = process_U_a(df)
    assert out.loc[0, "L_U"] == pytest.approx(math.log10(11), rel=1e-9)
    assert round(out.loc[0, "L_U"], 4) == 1.0414


# =================================================================
# Step 3: rank(L_U), method="min" ("normal"/competition ranking)
# =================================================================

def test_ranking_ties_share_lower_rank():
    # Author  U_a  L_U      Rank
    # A001    0    0        1
    # A002    0    0        1
    # A003    2    0.477    3
    # A004    5    0.778    4
    # A005    10   1.041    5
    df = _frame(
        ["A001", "A002", "A003", "A004", "A005"],
        [0.0, 0.0, 2.0, 5.0, 10.0],
    )
    out = process_U_a(df).set_index("author_id")

    assert out.loc["A001", "rank_U"] == 1
    assert out.loc["A002", "rank_U"] == 1
    assert out.loc["A003", "rank_U"] == 3
    assert out.loc["A004", "rank_U"] == 4
    assert out.loc["A005", "rank_U"] == 5


# =================================================================
# Step 4/5: Blom plotting position + percentile round trip
# =================================================================

def test_blom_and_percentile_round_trip():
    # N_U = 2321, r_U = 1200
    # P_U   = (1200 - 0.375) / (2321 + 0.25) = 0.5168012924071083
    # Nor_U = norm.ppf(P_U)               = 0.04212705168061125
    # Per_U = 100 * norm.cdf(Nor_U)       = 51.680129240710826
    n_authors = 2321
    target_rank = 1200

    u_values = list(range(n_authors))  # distinct -> ranks 1..N_U unambiguous
    df = _frame([f"auth{i}" for i in range(n_authors)], u_values)

    out = process_U_a(df)
    row = out[out["rank_U"] == target_rank].iloc[0]

    expected_p = (target_rank - 0.375) / (n_authors + 0.25)
    assert expected_p == pytest.approx(0.5168012924071083)
    assert row["P_U"] == pytest.approx(expected_p)
    assert row["Nor_U"] == pytest.approx(0.04212705168061125)
    assert row["Per_U"] == pytest.approx(51.680129240710826)
    assert int(out["N_U"].iloc[0]) == n_authors

    # Algebraic shortcut check: Per_U == 100 * P_U for every author,
    # since Phi(Phi^-1(P)) == P identically.
    scored = out[out["U_a"].notna()]
    diffs = (scored["Per_U"] - 100.0 * scored["P_U"]).abs()
    assert (diffs < 1e-9).all()


# =================================================================
# Missing data: NULL U_a is dropped, never treated as zero
# =================================================================

def test_null_u_a_is_excluded_not_zeroed():
    df = _frame(["a", "b", "c"], [None, 5.0, 10.0])
    out = process_U_a(df)

    row_a = out.set_index("author_id").loc["a"]
    assert pd.isna(row_a["L_U"])
    assert pd.isna(row_a["rank_U"])
    assert pd.isna(row_a["P_U"])
    assert pd.isna(row_a["Nor_U"])
    assert pd.isna(row_a["Per_U"])

    assert int(out["N_U"].iloc[0]) == 2


def test_all_null_raises():
    df = _frame(["a", "b"], [None, None])
    with pytest.raises(ValueError):
        process_U_a(df)


def test_missing_column_raises():
    with pytest.raises(ValueError):
        process_U_a(pd.DataFrame({"author_id": ["a"]}))


# =================================================================
# Rank method override
# =================================================================

def test_average_ranking_alternative():
    df = _frame(["a", "b", "c"], [0.0, 0.0, 5.0])
    out = process_U_a(df, rank_method="average").set_index("author_id")
    assert out.loc["a", "rank_U"] == pytest.approx(1.5)
    assert out.loc["b", "rank_U"] == pytest.approx(1.5)
    assert out.loc["c", "rank_U"] == 3
