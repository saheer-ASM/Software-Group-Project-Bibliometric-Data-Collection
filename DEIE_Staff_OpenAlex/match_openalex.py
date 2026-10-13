"""Step 2: match each staff member to an OpenAlex author -> output/deie_staff_openalex.csv.

Set OPENALEX_EMAIL (env var) to use the polite pool.  Matches are ranked by name
similarity plus whether the author is affiliated with the University of Ruhuna.
Anything not clearly a match is flagged for manual review, never guessed.
"""

import csv
import os
import time
from difflib import SequenceMatcher
from pathlib import Path

import requests

API = "https://api.openalex.org"
HERE = Path(__file__).parent
IN = HERE / "output" / "staff_merged.csv"
OUT = HERE / "output" / "deie_staff_openalex.csv"
MAILTO = os.getenv("OPENALEX_EMAIL", "")


class BudgetExhausted(RuntimeError):
    pass


def get(path, **params):
    if MAILTO:
        params["mailto"] = MAILTO
    for attempt in range(6):
        r = requests.get(f"{API}/{path}", params=params, timeout=30)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 0))
            if wait > 120:  # daily free budget is gone; retrying is pointless
                raise BudgetExhausted(f"OpenAlex daily budget used up; resets in ~{wait // 3600}h")
            time.sleep(5 * 2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("OpenAlex rate limit")


def ruhuna_id():
    if os.getenv("RUHUNA_ID"):
        return os.environ["RUHUNA_ID"], "University of Ruhuna"
    res = get("institutions", search="University of Ruhuna", per_page=3)["results"]
    return res[0]["id"].rsplit("/", 1)[-1], res[0]["display_name"]


def norm(s):
    return " ".join(s.lower().replace(".", " ").split())


def name_score(staff, cand):
    a, b = norm(staff), norm(cand)
    full = SequenceMatcher(None, a, b).ratio()
    # order-insensitive (OpenAlex sometimes has "Perera C." style names)
    ta, tb = set(a.split()), set(b.split())
    overlap = len(ta & tb) / max(len(ta), 1)
    initials = {t[0] for t in tb if t}
    surname_hit = any(t in tb for t in ta)
    init_hit = all(t in tb or (len(t) > 0 and t[0] in initials) for t in ta)
    return max(full, overlap, 0.85 if surname_hit and init_hit else 0)


def best_match(name, inst_id, extra=""):
    cands = get("authors", search=name, per_page=15)["results"]
    if extra and extra != name:  # second try with the PDF "initials" spelling
        seen = {c["id"] for c in cands}
        cands += [c for c in get("authors", search=extra, per_page=15)["results"] if c["id"] not in seen]
    scored = []
    for c in cands:
        insts = {a["institution"]["id"].rsplit("/", 1)[-1] for a in c.get("affiliations", [])}
        insts |= {i["id"].rsplit("/", 1)[-1] for i in c.get("last_known_institutions") or []}
        at_ruhuna = inst_id in insts
        ns = max(name_score(name, c["display_name"]), name_score(extra, c["display_name"]) if extra else 0)
        scored.append((ns + (0.5 if at_ruhuna else 0), ns, at_ruhuna, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def classify(top, runner_up):
    total, ns, at_ruhuna, _ = top
    if at_ruhuna and ns >= 0.85:
        return "high"
    if at_ruhuna and ns >= 0.7:
        return "medium"
    if ns >= 0.95 and (not runner_up or runner_up[0] < total - 0.2):
        return "low (name only, not at Ruhuna)"
    return "none"


def match_one(r, inst_id):
    initials = r["name_with_initials"].split("(")[0]
    initials = " ".join(t for t in initials.split() if t.rstrip(".").lower() not in ("dr", "mr", "ms", "mrs"))
    scored = best_match(r["search_name"], inst_id, initials)
    top = scored[0] if scored else None
    conf = classify(top, scored[1] if len(scored) > 1 else None) if top else "none"
    rec = dict(r, openalex_id="", openalex_name="", confidence=conf, works_count="",
               cited_by_count="", orcid="", alternatives="")
    if top and conf != "none":
        c = top[3]
        rec.update(openalex_id=c["id"].rsplit("/", 1)[-1], openalex_name=c["display_name"],
                   works_count=c.get("works_count", ""), cited_by_count=c.get("cited_by_count", ""),
                   orcid=c.get("orcid") or "")
    rec["alternatives"] = "; ".join(
        f"{x[3]['id'].rsplit('/', 1)[-1]}:{x[3]['display_name']}" for x in scored[1:4])
    rec["status"] = "ok" if conf in ("high", "medium") else "needs manual review"
    return rec


def main():
    inst_id, inst_name = ("I128559575", "University of Ruhuna")  # looked up once; avoids a request
    print(f"Institution: {inst_name} ({inst_id})")
    rows = list(csv.DictReader(open(IN, encoding="utf-8")))
    done = {}
    if OUT.exists():  # resume: keep rows that were already matched in an earlier run
        done = {d["name"]: d for d in csv.DictReader(open(OUT, encoding="utf-8"))
                if d.get("status") not in ("", "not yet matched", None)}
    out, stopped = [], False
    for r in rows:
        if r["name"] in done:
            out.append(dict(done[r["name"]], **r))  # refresh website/PDF columns, keep match
            continue
        rec = dict(r, openalex_id="", openalex_name="", confidence="", works_count="",
                   cited_by_count="", orcid="", alternatives="", status="not yet matched")
        if not stopped:
            try:
                rec = match_one(r, inst_id)
            except BudgetExhausted as e:
                print(f"\nSTOPPED: {e}. Re-run later to finish; matched rows are kept.")
                stopped = True
        out.append(rec)
        print(f"{r['name']:<28} -> {rec['openalex_id'] or '-':<14} {rec['confidence'] or rec['status']}")
        time.sleep(0.6)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"\nWrote {len(out)} rows -> {OUT}")


if __name__ == "__main__":
    main()
