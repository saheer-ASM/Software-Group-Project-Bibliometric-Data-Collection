"""
Demo / verification run: Step 1 (build the author dataset) + Steps 2-5
(process S_a only). Read-only -- connects to the DB to load data, does
not write anything back anywhere.

    python -m Nm_index_step_by_step.run_step_S_a
"""

import pandas as pd

from .build_dataset import build_author_metric_dataset
from .database import get_connection
from .step_S_a import process_S_a


def main() -> None:
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)

    print("=" * 70)
    print("STEP 1 -- build author_id, T_a, S_a, U_a, Hf_a, Hm_a, G_a")
    print("=" * 70)

    connection = get_connection()
    try:
        dataset = build_author_metric_dataset(connection)
    finally:
        connection.close()

    print(f"Authors loaded: {len(dataset)}")
    for column in ("T_a", "S_a", "U_a", "Hf_a", "Hm_a", "G_a"):
        print(f"  {column:<6} non-null: {dataset[column].notna().sum()}")
    print()
    print(dataset.head(5).to_string(index=False))

    print()
    print("=" * 70)
    print("STEPS 2-5 -- process S_a")
    print("=" * 70)

    result = process_S_a(dataset)

    n_available = int(result["N_S"].iloc[0])
    print(f"N_S (authors with non-null S_a): {n_available}")
    print()

    scored = result[result["S_a"].notna()]
    preview = scored[
        ["author_id", "S_a", "L_S", "rank_S", "P_S", "Nor_S", "Per_S"]
    ]

    print("Lowest S_a (ties at rank 1, near the 0th percentile):")
    print(
        preview.sort_values("S_a").head(5).to_string(index=False)
    )
    print()
    print("Highest S_a (near the 100th percentile):")
    print(
        preview.sort_values("S_a", ascending=False).head(5).to_string(index=False)
    )

    print()
    print("Sanity check -- Per_S should equal 100 * P_S (Phi(Phi^-1(P)) = P):")
    max_diff = (scored["Per_S"] - 100.0 * scored["P_S"]).abs().max()
    print(f"  max |Per_S - 100*P_S| = {max_diff:.2e}")

    print()
    print("Per_S distribution:")
    print(scored["Per_S"].describe().to_string())


if __name__ == "__main__":
    main()
