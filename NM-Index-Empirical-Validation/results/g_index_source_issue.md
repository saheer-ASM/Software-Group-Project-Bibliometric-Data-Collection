# Latest-manuscript conventional g-index source issue

**Source:** `Nm Index novel model (1)(3).pdf`, Introduction p. 2; fictitious profile Table 4 p. 19; Tables 10–11 pp. 23 and 25. The latest experiment design's baseline table repeats the written rule. No older manuscript was used.

The stated conventional rule is the largest `g` such that the author's **top `g` papers** have at least `g²` cumulative citations. The displayed profile contains five papers with counts `50,20,30,40,25`, or sorted `50,40,30,25,20`. Their cumulative counts at ranks 1–5 are `50,90,120,145,165`; each exceeds its squared rank, so the largest `g` among the **five displayed papers is 5**.

The PDF nevertheless reports conventional `g=12` in its comparison. Since `12²=144 ≤165` and `13²=169 >165`, 12 follows numerically **only if** the ranking is extended with at least seven zero-citation papers or another unstated extension. The PDF says this profile has five papers and does not prescribe zero-padding. Omitted papers, zero-padding, or a wrong example value are possible explanations; none is established.

The code in `metrics/g_index.py` implements the explicit top-observed-paper formula and returns 5 for this example. This is a **source example conflict**, not a reason to replace the clear written formula silently. Before treating g=12 as a benchmark or changing the algorithm, the project needs a documented author/lecturer decision about the profile and any extension convention. NM's `G′` component is separate and is only loaded from its stored table.
