"""Export the prize-winner source list and the selected shortlist to Excel.

Runs entirely from `cache/wikidata_laureates.json` -- no OpenAlex calls, so it
works even when the daily budget is spent.  What it cannot fill in is the
bibliometric half (h-index, career age, self-citation); those columns come from
OpenAlex when `run_extraction.py --laureates` runs.

    python export_laureate_shortlist.py
"""

import json
import os

import pandas as pd

import config
import quotas as quota_lib
from collect_laureates import LAUREATE_CACHE

OUTPUT = os.path.join(config.OUTPUT_DIR, "laureate_shortlist.xlsx")


def main():
    with open(LAUREATE_CACHE, encoding="utf-8") as handle:
        lists = json.load(handle)

    quotas = quota_lib.even_split(config.TARGET_LAUREATE_AUTHORS, list(lists))

    candidates, chosen_ids = [], set()
    for prize, people in lists.items():
        # Same order the collector uses: ORCID first (exact OpenAlex match),
        # then most recent award. Everyone is listed; the first `quota` of them
        # that are not already taken by an earlier prize are the shortlist.
        picked = 0
        for rank, person in enumerate(people, start=1):
            already = person["wikidata_id"] in chosen_ids
            shortlisted = (not already and picked < quotas[prize])
            if shortlisted:
                chosen_ids.add(person["wikidata_id"])
                picked += 1
            candidates.append({
                "prize": prize,
                "shortlisted": shortlisted,
                "rank_within_prize": rank,
                "name": person["name"],
                "wikidata_id": person["wikidata_id"],
                "orcid": person.get("orcid"),
                "award_year": person.get("award_year"),
                "awards": "; ".join(person.get("awards") or []),
                "held_by_earlier_prize": already,
            })

    frame = pd.DataFrame(candidates)
    shortlist = frame[frame["shortlisted"]].reset_index(drop=True)

    summary = (frame.groupby("prize")
               .agg(laureates=("name", "size"),
                    with_orcid=("orcid", lambda s: int(s.notna().sum())),
                    quota=("prize", lambda s: quotas[s.iloc[0]]),
                    shortlisted=("shortlisted", "sum"))
               .reset_index()
               .sort_values("laureates", ascending=False))

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with pd.ExcelWriter(OUTPUT, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="prize_summary", index=False)
        shortlist.drop(columns=["shortlisted"]).to_excel(
            writer, sheet_name="shortlist_50", index=False)
        frame.to_excel(writer, sheet_name="all_candidates", index=False)

    print(summary.to_string(index=False))
    print(f"\nshortlisted: {len(shortlist)} / {config.TARGET_LAUREATE_AUTHORS}")
    print(f"with ORCID : {int(shortlist['orcid'].notna().sum())} of {len(shortlist)}")
    print(f"pool       : {len(frame)} laureates across {len(lists)} prizes")
    print(f"written    : {OUTPUT}")


if __name__ == "__main__":
    main()
