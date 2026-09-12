"""Wikidata SPARQL access for the prize-winner ("special case") cohort.

Wikidata is the practical open-source register of prize winners: every award in
the sheet is modelled as `award received` (P166), and most laureates carry an
ORCID (P496), which is the reliable bridge into OpenAlex.  Nobelprize.org's own
API only covers the Nobels, so it cannot serve the other eleven prizes.
"""

import time

import requests

import config

# Walking P279* (subclass of) and P361* (part of) from a root prize picks up its
# per-discipline sub-prizes -- laureates are attached to those, not to the root.
LAUREATE_QUERY = """
SELECT DISTINCT ?person ?personLabel ?orcid ?awardLabel ?year WHERE {
  VALUES ?root { %s }
  ?award (wdt:P279*|wdt:P361*) ?root .
  ?person p:P166 ?statement .
  ?statement ps:P166 ?award .
  ?person wdt:P31 wd:Q5 .
  OPTIONAL { ?person wdt:P496 ?orcid }
  OPTIONAL { ?statement pq:P585 ?date . BIND(YEAR(?date) AS ?year) }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""


class WikidataError(RuntimeError):
    pass


class WikidataClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})
        self.request_count = 0

    def sparql(self, query):
        delay = 2.0
        for attempt in range(config.MAX_RETRIES):
            self.request_count += 1
            response = self.session.get(
                config.WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
                headers={"Accept": "application/sparql-results+json"},
                timeout=180,
            )
            if response.status_code == 200:
                return response.json()["results"]["bindings"]
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay)
                delay *= 2
                continue
            raise WikidataError(
                f"{response.status_code} :: {response.text[:300]}")
        raise WikidataError("SPARQL endpoint kept failing")

    def laureates(self, prize_qids):
        """Every human holder of the given prize(s), newest award first."""
        values = " ".join(f"wd:{qid}" for qid in prize_qids)
        rows = self.sparql(LAUREATE_QUERY % values)

        people = {}
        for row in rows:
            qid = row["person"]["value"].rsplit("/", 1)[-1]
            year = row.get("year", {}).get("value")
            record = people.setdefault(qid, {
                "wikidata_id": qid,
                "name": row.get("personLabel", {}).get("value"),
                "orcid": None,
                "awards": set(),
                "award_year": None,
            })
            if row.get("orcid"):
                record["orcid"] = row["orcid"]["value"].strip()
            if row.get("awardLabel"):
                record["awards"].add(row["awardLabel"]["value"])
            if year:
                year = int(year)
                if record["award_year"] is None or year > record["award_year"]:
                    record["award_year"] = year

        result = []
        for record in people.values():
            record["awards"] = sorted(record["awards"])
            result.append(record)
        # ORCID first (they match into OpenAlex without name guesswork), then
        # most recent award -- recent laureates have far better OpenAlex coverage.
        result.sort(key=lambda r: (r["orcid"] is None, -(r["award_year"] or 0)))
        return result

    def resolve_prize_label(self, label):
        """Utility for adding a new prize to config.PRIZES: label -> Q-id."""
        response = self.session.get(config.WIKIDATA_API, params={
            "action": "wbsearchentities", "search": label, "language": "en",
            "format": "json", "limit": 5, "type": "item"},
            timeout=config.REQUEST_TIMEOUT)
        return [(hit["id"], hit.get("label"), hit.get("description"))
                for hit in response.json().get("search", [])]
