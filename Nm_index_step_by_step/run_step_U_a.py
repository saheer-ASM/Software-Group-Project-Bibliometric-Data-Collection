"""
Demo / verification run: Step 1 (build the author dataset) + Steps 2-5
(process U_a only). Read-only -- connects to the DB to load data, does
not write anything back anywhere.

    python -m Nm_index_step_by_step.run_step_U_a
"""

import pandas as pd

from .build_dataset import build_author_metric_dataset
from .database import get_connection
from .step_U_a import process_U_a


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
    print("STEPS 2-5 -- process U_a")
    print("=" * 70)

    result = process_U_a(dataset)

    n_available = int(result["N_U"].iloc[0])
    print(f"N_U (authors with non-null U_a): {n_available}")
    print()

    scored = result[result["U_a"].notna()]
    preview = scored[
        ["author_id", "U_a", "L_U", "rank_U", "P_U", "Nor_U", "Per_U"]
    ]

    print("Lowest U_a (ties at rank 1, near the 0th percentile):")
    print(
        preview.sort_values("U_a").head(5).to_string(index=False)
    )
    print()
    print("Highest U_a (near the 100th percentile):")
    print(
        preview.sort_values("U_a", ascending=False).head(5).to_string(index=False)
    )

    print()
    print("Sanity check -- Per_U should equal 100 * P_U (Phi(Phi^-1(P)) = P):")
    max_diff = (scored["Per_U"] - 100.0 * scored["P_U"]).abs().max()
    print(f"  max |Per_U - 100*P_U| = {max_diff:.2e}")

    print()
    print("Per_U distribution:")
    print(scored["Per_U"].describe().to_string())


if __name__ == "__main__":
    main()
