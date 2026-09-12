"""Collect the prize-winner cohort (50 authors by default, "special case").

Wikidata supplies the laureate list per prize; OpenAlex supplies the
bibliometrics.  Quota is split equally over the prizes in config.PRIZES, and a
person holding several prizes is assigned to whichever still needs people most,
so one polymath does not consume two slots.
"""

import json
import os
import re

import config
import quotas as quota_lib
from openalex import BudgetExhausted
from profiling import build_profile

CHECKPOINT = os.path.join(config.CACHE_DIR, "laureate_checkpoint.jsonl")
LAUREATE_CACHE = os.path.join(config.CACHE_DIR, "wikidata_laureates.json")


def _normalise(name):
    return " ".join(re.sub(r"[^a-z ]", " ", (name or "").lower()).split())


def fetch_laureate_lists(wikidata_client, refresh=False, verbose=True):
    """{prize_name: [laureate records]} from Wikidata, cached on disk."""
    cached = {}
    if os.path.exists(LAUREATE_CACHE) and not refresh:
        with open(LAUREATE_CACHE, encoding="utf-8") as handle:
            cached = json.load(handle)

    changed = False
    for prize_name, qids in config.PRIZES.items():
        if prize_name in cached:
            continue
        cached[prize_name] = wikidata_client.laureates(qids)
        changed = True
        if verbose:
            print(f"  wikidata: {prize_name} -> {len(cached[prize_name])} laureates")

    if changed:
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        with open(LAUREATE_CACHE, "w", encoding="utf-8") as handle:
            json.dump(cached, handle, indent=2, ensure_ascii=False)

    return {prize: cached[prize] for prize in config.PRIZES}


def match_to_openalex(client, laureate):
    """Resolve a Wikidata laureate to an OpenAlex author record.

    ORCID is exact.  Without one, fall back to a name search and only accept a
    hit whose normalised name matches and that has a real publication record --
    a wrong match here would poison the special-case cohort.
    """
    if laureate.get("orcid"):
        author = client.author_by_orcid(laureate["orcid"])
        if author:
            return author, "orcid"

    target = _normalise(laureate.get("name"))
    if not target:
        return None, "no_name"

    for candidate in client.author_search(laureate["name"]):
        if _normalise(candidate.get("display_name")) != target:
            continue
        if (candidate.get("works_count") or 0) < config.MIN_WORKS_COUNT:
            continue
        return candidate, "name"
    return None, "unmatched"


def collect(client, wikidata_client, target=None, resume=True, verbose=True):
    target = target or config.TARGET_LAUREATE_AUTHORS
    laureate_lists = fetch_laureate_lists(wikidata_client, verbose=verbose)
    prize_quotas = quota_lib.even_split(target, list(config.PRIZES))

    rows, already_taken = [], set()
    if resume and os.path.exists(CHECKPOINT):
        with open(CHECKPOINT, encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue        # merged file with a conflict marker left in
                # De-duplicate: a git merge can legitimately repeat a laureate,
                # and double-counting would wrongly shrink the prize quota.
                if row["openalex_id"] in already_taken:
                    continue
                rows.append(row)
                already_taken.add(row["openalex_id"])
                prize_quotas[row["assigned_prize"]] = max(
                    0, prize_quotas.get(row["assigned_prize"], 0) - 1)

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    handle = open(CHECKPOINT, "a", encoding="utf-8")
    report = []
    try:
        for prize_name, quota in prize_quotas.items():
            collected = 0
            attempted = 0
            for laureate in laureate_lists.get(prize_name, []):
                if collected >= quota:
                    break
                attempted += 1
                author, how = match_to_openalex(client, laureate)
                if author is None:
                    continue
                author_id = author["id"].rstrip("/").split("/")[-1]
                if author_id in already_taken:
                    continue

                profile = build_profile(client, author, assigned_field=None)
                profile["assigned_prize"] = prize_name
                profile["wikidata_id"] = laureate["wikidata_id"]
                profile["wikidata_name"] = laureate["name"]
                profile["awards"] = "; ".join(laureate.get("awards") or [])
                profile["award_year"] = laureate.get("award_year")
                profile["match_method"] = how
                profile.pop("_works", None)

                rows.append(profile)
                already_taken.add(author_id)
                handle.write(json.dumps(profile, ensure_ascii=False) + "\n")
                handle.flush()
                collected += 1

            report.append({"prize": prize_name, "quota": quota,
                           "collected": collected, "candidates_tried": attempted,
                           "status": "complete" if collected >= quota
                                     else f"short_by_{quota - collected}"})
            if verbose:
                print(f"  {prize_name[:40]:40s} {collected}/{quota} "
                      f"(tried {attempted}, {client.request_count} api calls)")
    except BudgetExhausted as exc:
        # Each laureate is flushed as it is matched, so nothing banked is lost.
        print(f"\n!! {exc}")
        print(f"   resumes at {exc.reset_text}; re-run the same "
              f"command to continue from the checkpoint")
    finally:
        handle.close()

    return rows, report
