"""Step 1b: merge the department's permanent-staff PDF list into the scraped list.

Adds name-with-initials + email to staff that appear in both, and appends staff
that are only in the PDF (missing from the website) -> output/staff_merged.csv.
"""

import csv
import re
from pathlib import Path

OUT_DIR = Path(__file__).parent / "output"

# (index, name with initials, email, status note, name to search in OpenAlex)
PDF = [
    (1, "Dr. C.K.W. Seneviratne (Head)", "chatura@eie.ruh.ac.lk", ""),
    (2, "Dr. P.D.C. Perera", "chandana@eie.ruh.ac.lk", ""),
    (3, "Dr. S.H.K.K. Gunawickrama", "keerthi@eie.ruh.ac.lk", ""),
    (4, "Dr. M.R. Udawalpola", "rajitha@eie.ruh.ac.lk", ""),
    (5, "Dr. S.H. Gunawardena", "subodha@eie.ruh.ac.lk", ""),
    (6, "Mr. E.H. Jayathunga (Study Leave)", "eranda@eie.ruh.ac.lk", ""),
    (7, "Mr. D. S. De Silva", "saman@eie.ruh.ac.lk", ""),
    (8, "Dr. T.N. Weerasinghe", "thilina@eie.ruh.ac.lk", ""),
    (9, "Dr. K.M.S.Y. Konara", "konara@eie.ruh.ac.lk", ""),
    (10, "Dr. W.N.B.A.G. Priyankara", "geeth@eie.ruh.ac.lk", ""),
    (11, "Dr. Mrs. K.M.I.U. Ranaweera", "iromi@eie.ruh.ac.lk", ""),
    (12, "Dr. K.L. Kushan Sudheera", "kushan@eie.ruh.ac.lk", ""),
    (13, "Dr. G.G.N. Sandamali", "nadeesha@eie.ruh.ac.lk", ""),
    (14, "Dr. W.P. Prabath Kumara", "weera@eie.ruh.ac.lk", ""),
    (15, "Dr. T.D. Gamage", "tharindu@eie.ruh.ac.lk", ""),
    (16, "Dr. L.K.G. Liyanage", "kaveen.l@eie.ruh.ac.lk", "Kaveen Liyanage"),
    (17, "Mr. P.A.D.S.N. Wijesekara", "nilmantha@eie.ruh.ac.lk", ""),
    (18, "Mr. G.W.G.K.N. Udayanga", "udayangakn@eie.ruh.ac.lk", ""),
    (19, "Mr. A.S. Mudalige", "anuradha.mudalige@eie.ruh.ac.lk", ""),
    (20, "Ms. S.M.T. M. Silva", "tashmas@eie.ruh.ac.lk", ""),
    (21, "Mr. I.G.P.N. Karunasena", "neelk@eie.ruh.ac.lk", ""),
    (22, "Ms. G.C.W. Thilakarathne (Study Leave)", "gayathrit@eie.ruh.ac.lk", ""),
    (23, "Ms. O.G.Y.N. Gamlath", "yugani@eie.ruh.ac.lk", ""),
    (24, "Mr. R. Saahith Ahamed", "saahith@eie.ruh.ac.lk", ""),
    (25, "Mr. G.H.H. Witharana", "gevin.h@eie.ruh.ac.lk", ""),
    (26, "Ms. M.S. Madhubhashini", "sithara.m@eie.ruh.ac.lk", ""),
    (27, "Ms. N.H. Gamage", "nishanthi@eie.ruh.ac.lk", ""),
    (28, "Ms. Nuha", "nuha.f@eie.ruh.ac.lk", ""),
    (29, "Mr. H.L.Y. Ruhunage", "heshan.r@eie.ruh.ac.lk", ""),
    (30, "Mr. P. Sathyamoorthi", "pavithran.s@eie.ruh.ac.lk", "Pavithran Sathyamoorthi"),
    (31, "Mr. D.T.B.C.S.B. Dissanayake", "chamod.d@eie.ruh.ac.lk", ""),
    (32, "Mr. W.G. Rangana", "rangana.w@eie.ruh.ac.lk", "Rangana W G"),
    (33, "Ms. I.A.S. Ilangaweera", "ayesha.s@eie.ruh.ac.lk", "Ayesha Ilangaweera"),
    (34, "Ms. S.M.M.J. Subasinghe", "", "Subasinghe S M M J"),
    (35, "Ms. P.R.U. Kawmadie", "usha.k@eie.ruh.ac.lk", "Usha Kawmadie"),
]
FIELDS = ["name", "search_name", "rank", "qualifications", "profile_url", "pdf_index",
          "name_with_initials", "email", "source", "raw_name"]


def same_person(name, email):
    local = re.sub(r"[^a-z]", "", email.split("@")[0].lower())
    for tok in re.sub(r"[^a-z ]", "", name.lower()).split():
        if len(tok) >= 4 and (local.startswith(tok) or tok.startswith(local[:5])):
            return True
    return False


def main():
    staff = list(csv.DictReader(open(OUT_DIR / "staff.csv", encoding="utf-8")))
    rows = [dict(r, search_name=r["name"], pdf_index="", name_with_initials="", email="",
                 source="website") for r in staff]
    for idx, initials, email, search in PDF:
        hit = next((r for r in rows if r["source"] != "pdf only" and email
                    and not r["pdf_index"] and same_person(r["name"], email)), None)
        if hit:
            hit.update(pdf_index=idx, name_with_initials=initials, email=email, source="website + pdf")
        else:
            rows.append({"name": search or initials, "search_name": search or initials, "rank": "",
                         "qualifications": "", "profile_url": "", "pdf_index": idx,
                         "name_with_initials": initials, "email": email, "source": "pdf only",
                         "raw_name": initials})
    for r in rows:
        if r["source"] == "website + pdf":
            print(f"{r['pdf_index']:>2} {r['name_with_initials']:<38} <-> {r['name']}")
    with open(OUT_DIR / "staff_merged.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nPDF-only: {[r['name_with_initials'] for r in rows if r['source']=='pdf only']}")
    print(f"Website-only: {[r['name'] for r in rows if r['source']=='website']}")


if __name__ == "__main__":
    main()
