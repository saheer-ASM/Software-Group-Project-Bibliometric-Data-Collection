"""Collect explicit author contributions (CRediT roles, equal-contribution flags)
from open publisher JATS XML into  author_contribution_statement  (Eq 2, 4-6).

For each own publication (update_status != 'no need to update') not yet checked:
    OpenAlex  ids.pmcid            (100 works per request)
    Europe PMC fullTextXML         (open-access PMC papers: PLOS, eLife, BMC, ...)
    <contrib contrib-type="author">, in order:
        <role ...>  -> CRediT roles     equal-contrib="yes" -> equal_contrib = 1
    one row per author position; a paper with no PMC XML gets no rows and keeps
    the ordering models (A/R or RC).

Progress is kept in publication.contribution_checked ('done' / NULL), so the
script is resumable. Run author_contribution_local afterwards with --recompute.

Usage:
    python collect_contributions.py --limit 50 --dry-run
    python collect_contributions.py
"""

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "database"))
sys.path.insert(0, os.path.join(HERE, "author_contribution_local"))

from db import DB_PATH, get_conn                        # noqa: E402
from fill_publications import (                         # noqa: E402
    BudgetExhausted, OPENALEX_API_KEY, OPENALEX_MAILTO, OPENALEX_WORKS_URL,
    REQUEST_DELAY_SECONDS, _get, short_id,
)
from explicit_contribution import STATEMENT_SQL, normalise_role   # noqa: E402

EPMC_XML = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
IDS_PER_REQUEST = 100


def fetch_pmcids(pub_ids):
    params = {"filter": "openalex_id:" + "|".join(pub_ids), "per_page": IDS_PER_REQUEST,
              "select": "id,ids"}
    if OPENALEX_API_KEY:
        params["api_key"] = OPENALEX_API_KEY
    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO
    out = {}
    for work in _get(OPENALEX_WORKS_URL, params).get("results", []):
        pmcid = ((work.get("ids") or {}).get("pmcid") or "").rstrip("/").split("/")[-1]
        if pmcid:
            out[short_id(work.get("id"))] = pmcid if pmcid.upper().startswith("PMC") else "PMC" + pmcid
    return out


def _text(node):
    return " ".join("".join(node.itertext()).split())


def parse_contributions(xml_text):
    """[(position, [roles], equal_contrib)] for the article's authors, in order.

    Authors: <contrib contrib-type="author"> or a <contrib> inside
    <contrib-group content-type="author">. Roles: one or more <role> elements,
    each possibly a comma-separated list. Equal contribution: equal-contrib="yes",
    or an <xref> to a footnote with fn-type="equal".
    """
    root = ET.fromstring(xml_text)
    meta = root.find(".//front/article-meta")
    if meta is None:
        return []
    equal_fn = {fn.get("id") for fn in root.iter("fn") if fn.get("fn-type") in ("equal", "con")
                and "equal" in _text(fn).lower()}
    equal_fn |= {fn.get("id") for fn in root.iter("fn") if fn.get("fn-type") == "equal"}
    rows = []
    for group in meta.iter("contrib-group"):
        group_is_author = group.get("content-type") in (None, "author", "authors")
        for contrib in group.findall("contrib"):
            kind = contrib.get("contrib-type")
            if (kind and kind != "author") or (not kind and not group_is_author):
                continue
            if contrib.find("collab") is not None:
                continue
            roles = []
            for r in contrib.findall("role"):
                roles += [normalise_role(part) for part in _text(r).split(",")]
            roles = sorted({r for r in roles if r})
            equal = (contrib.get("equal-contrib", "").lower() == "yes"
                     or any(x.get("rid") in equal_fn for x in contrib.findall("xref")))
            rows.append((len(rows) + 1, roles, int(equal)))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not os.path.exists(DB_PATH):
        sys.exit(f"{DB_PATH} not found")
    conn = get_conn()
    if not args.dry_run:
        conn.execute(STATEMENT_SQL)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(publication)")]
        if "contribution_checked" not in cols:
            conn.execute("ALTER TABLE publication ADD COLUMN contribution_checked TEXT")
        conn.commit()
    has_flag = "contribution_checked" in [r[1] for r in conn.execute("PRAGMA table_info(publication)")]
    todo = [r[0] for r in conn.execute(
        "SELECT pub_id FROM publication WHERE update_status != 'no need to update'"
        + (" AND contribution_checked IS NULL" if has_flag else "") + " ORDER BY rowid")]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo):,} publication(s) to check")
    found = with_roles = with_equal = 0
    session = requests.Session()
    try:
        for start in range(0, len(todo), IDS_PER_REQUEST):
            chunk = todo[start:start + IDS_PER_REQUEST]
            try:
                pmcids = fetch_pmcids(chunk)
            except BudgetExhausted as exc:
                print(f"!! {exc}; re-run later"); break
            except Exception as exc:
                print(f"OpenAlex request failed ({exc}); continuing"); continue
            rows = []
            for pub_id, pmcid in pmcids.items():
                try:
                    resp = session.get(EPMC_XML.format(pmcid=pmcid), timeout=30)
                    if resp.status_code != 200 or not resp.text.strip().startswith("<"):
                        continue
                    parsed = parse_contributions(resp.text)
                except Exception:
                    continue
                if not parsed:
                    continue
                found += 1
                with_roles += any(r for _, r, _ in parsed)
                with_equal += any(e for _, _, e in parsed)
                rows += [(pub_id, pos, json.dumps(roles) if roles else None, eq, f"europepmc:{pmcid}")
                         for pos, roles, eq in parsed]
                time.sleep(REQUEST_DELAY_SECONDS)
            if args.dry_run:
                for r in rows[:6]:
                    print("  ", r)
            else:
                with conn:
                    conn.executemany(
                        "INSERT OR REPLACE INTO author_contribution_statement "
                        "(pub_id, position, credit_roles, equal_contrib, source) VALUES (?,?,?,?,?)", rows)
                    conn.executemany("UPDATE publication SET contribution_checked = 'done' "
                                     "WHERE pub_id = ?", [(p,) for p in chunk])
            print(f"[{start + len(chunk):,}/{len(todo):,}] XML found {found:,} "
                  f"(CRediT {with_roles:,}, equal-contribution {with_equal:,})", flush=True)
    except KeyboardInterrupt:
        print("interrupted; finished chunks are saved")
    finally:
        conn.close()
    if args.dry_run:
        print("[dry run] nothing written")


if __name__ == "__main__":
    main()
