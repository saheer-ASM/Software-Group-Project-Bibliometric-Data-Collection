"""Step 1: scrape the DEIE (University of Ruhuna) staff page -> output/staff.csv."""

import csv
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://www.eng.ruh.ac.lk/deie/staff/"
OUT = Path(__file__).parent / "output" / "staff.csv"
TITLES = re.compile(r"^(prof\.?|professor|dr\.?|eng\.?|ch\.?|mr\.?|ms\.?|mrs\.?|miss)\s+", re.I)
RANKS = {"head": "Head", "senior-lecturer": "Senior Lecturer", "lecturer": "Lecturer",
         "visiting-lecturer": "Visiting Lecturer"}


def clean_name(name):
    name = re.sub(r"\s+", " ", name).strip()
    while TITLES.match(name):
        name = TITLES.sub("", name)
    return name


def main():
    html = requests.get(URL, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")
    rows, seen = [], set()
    for card in soup.select("div.team-container"):
        desc = card.select_one(".team-desc")
        link = card.select_one("a[href*='/team/']")
        if not desc or not link:
            continue
        paras = [p.get_text(" ", strip=True) for p in desc.find_all("p")]
        rank_text = paras[0] if paras else ""
        qualifications = paras[1] if len(paras) > 1 else ""
        full = desc.get_text(" ", strip=True)
        raw_name = full.split(rank_text)[0] if rank_text and rank_text in full else full
        raw_name = raw_name.replace("View details", "")
        cats = [c.replace("dt_team_category-", "") for c in card.get("class", [])
                if c.startswith("dt_team_category-") and not c[-1].isdigit()]
        rank = next((RANKS[c] for c in cats if c in RANKS), rank_text)
        if link["href"] in seen:
            continue
        seen.add(link["href"])
        rows.append({"name": clean_name(raw_name), "raw_name": raw_name.strip(), "rank": rank,
                     "qualifications": qualifications, "profile_url": link["href"]})
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} staff -> {OUT}")


if __name__ == "__main__":
    main()
