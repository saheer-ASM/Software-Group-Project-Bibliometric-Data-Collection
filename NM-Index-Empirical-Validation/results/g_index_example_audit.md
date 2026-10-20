# Manual audit of the latest manuscript's five-paper g-index example

The [latest manuscript](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf), PDF p. 19 Table 4, lists five paper citation counts `50, 20, 30, 40, 25`. PDF p. 2 defines the conventional g-index as the largest `g` for which the author's top `g` papers have at least `g²` citations in total. PDF pp. 23 and 25 report **g = 12** for this profile. The [experiment design](../source_documents/Pasted%20markdown%287%29.md), line 37, gives the same top-`g`-papers definition.

Manual check, using only the displayed five papers:

| g | g-th largest paper citations | Cumulative top-g citations | g² | Condition met? |
|---:|---:|---:|---:|---|
| 1 | 50 | 50 | 1 | Yes |
| 2 | 40 | 90 | 4 | Yes |
| 3 | 30 | 120 | 9 | Yes |
| 4 | 25 | 145 | 16 | Yes |
| 5 | 20 | 165 | 25 | Yes |

With **five observed papers**, the largest valid `g` under the stated top-`g`-papers rule is **5**; there is no sixth paper to include. The displayed 165 citations exceed `12² = 144`, and `13² = 169`. Thus **12 can be reproduced only if the five-paper list is extended with seven hypothetical zero-citation papers** (or under another unstated convention). Neither source says to pad the paper list with zeros. The sample therefore does not establish whether the authors intended zero-padding, omitted seven or more papers from Table 4, used citation values differently, or made an arithmetic/description error. The manuscript's explicit five-paper statement and repeated g=12 claim are internally inconsistent under its written definition.

**Decision required:** confirm whether conventional g is capped by the observed number of publications or may be extended with zero-citation papers, and whether the Table 4 profile is complete. Do not use g=12 as an implementation test fixture and do not silently change either source. This is the sole manual metric example authorized in Phase 4.5; no database g-index or other metric was calculated.
