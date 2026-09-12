# -*- coding: utf-8 -*-
"""Build the final_nm_index implementation-summary PDF."""

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)

OUT = (
    r"C:\Users\shait\OneDrive\Desktop\software_project"
    r"\Software-Group-Project-Bibliometric-Data-Collection"
    r"\final_nm_index\Nm_index_implementation_summary.pdf"
)


styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=15, spaceBefore=14,
                    spaceAfter=6, textColor=colors.HexColor("#1a3c5e"))
H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=10,
                    spaceAfter=4, textColor=colors.HexColor("#22506f"))
BODY = ParagraphStyle("BODY", parent=styles["BodyText"], fontSize=9.5, leading=13.5,
                      alignment=TA_LEFT, spaceAfter=5)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8.5, leading=11.5)
CODE = ParagraphStyle("CODE", parent=styles["Code"], fontSize=8, leading=10,
                      backColor=colors.HexColor("#f4f4f4"))
TITLE = ParagraphStyle("TITLE", parent=styles["Title"], fontSize=19, leading=23,
                       textColor=colors.HexColor("#12324c"))
NOTE = ParagraphStyle("NOTE", parent=BODY, fontSize=9, leading=12.5,
                      leftIndent=6, borderColor=colors.HexColor("#c9a23a"),
                      borderWidth=0, backColor=colors.HexColor("#fbf6e7"),
                      spaceBefore=4, spaceAfter=6)

story = []
P = lambda t, s=BODY: story.append(Paragraph(t, s))
GAP = lambda h=4: story.append(Spacer(1, h))


def bullets(items, style=BODY):
    bstyle = ParagraphStyle("b", parent=style, leftIndent=14, bulletIndent=2,
                            spaceAfter=4)
    return [Paragraph(i, bstyle, bulletText="\u2013") for i in items]


def tbl(data, widths, header=True, font=8.5):
    cell = ParagraphStyle("cell", parent=BODY, fontSize=font, leading=font + 2.5,
                          spaceAfter=0)
    hcell = ParagraphStyle("hcell", parent=cell, textColor=colors.white,
                           fontName="Helvetica-Bold")
    wrapped = []
    for r, row in enumerate(data):
        wrapped.append([
            Paragraph(str(c), hcell if (header and r == 0) else cell)
            for c in row
        ])
    t = Table(wrapped, colWidths=widths, repeatRows=1 if header else 0)
    ts = [
        ("FONTSIZE", (0, 0), (-1, -1), font),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4cc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        ts += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(ts))
    return t


# ============================================================ TITLE
P("Final Nm-index (Nilmantha's index)", TITLE)
P("Implementation summary &amp; assumptions for supervisor review", H2)
P("Module: <b>final_nm_index/</b> &nbsp;|&nbsp; Repo: Software-Group-Project-"
  "Bibliometric-Data-Collection &nbsp;|&nbsp; Date: 2026-09-04", SMALL)
GAP(6)
P("This module implements <b>only the last stage</b> of the Nm-index model "
  "&mdash; Equations 24&ndash;27 of the full paper (&sect;2.5 &ldquo;Final "
  "score&rdquo;; Eq. 23&ndash;25 in the extended abstract). Everything before "
  "Eq.&nbsp;24 (author-contribution weights, influential self-citation, career "
  "factor, and the six component metrics themselves) is produced by other "
  "pipelines in the repo and stored in PostgreSQL. This module reads those "
  "stored values and does <b>not</b> recompute them.")

# ============================================================ 1
P("1.&nbsp; What the code does", H1)
P("For every author it turns six raw impact numbers into one comparable "
  "percentile score:")
GAP(2)
story.append(tbl([
    ["#", "Symbol", "Meaning", "Paper Eq.", "Read from (DB)"],
    ["x1", "T_a", "Outlier-uncontrolled field- &amp; year-normalised total cites", "Eq. 11", "author_total_cites.total_cites_score"],
    ["x2", "S_a", "Outlier-controlled field-normalised cites per paper", "Eq. 13", "author_citations_per_paper.citations_per_paper_score"],
    ["x3", "U_a", "Outlier-controlled field- &amp; year-normalised citation rate", "Eq. 14", "author_citation_rate.citation_rate_score"],
    ["x4", "Hf'_a", "Modified hf-index", "Eq. 17", "author_modified_hindex.modified_hindex_final"],
    ["x5", "Hm'_a", "Modified hm-index", "Eq. 20", "author.modified_hm_index"],
    ["x6", "G'_a", "Modified g-index", "Eq. 23", "author.modified_g_index"],
], widths=[14*mm, 16*mm, 52*mm, 16*mm, 66*mm]))
GAP(3)
P("Processing chain:", H2)
story.extend(bullets([
    "<b>Load</b> (run_calculation.py) &mdash; one <b>LEFT JOIN</b> of the six "
    "one-row-per-author tables onto the full author list, keyed on author_id. "
    "Only rows with a non-NULL value are taken for each metric.",
    "<b>Calculate</b> (calculator.py) &mdash; Eq. 24 transform then Eq. 25 "
    "normalise then Eq. 26 percentile, per metric; then Eq. 27 weighted "
    "average. Pure pandas / numpy / scipy, no DB access.",
    "<b>Write</b> (run_calculation.py) &mdash; UPSERT one row per author into "
    "<b>author_nm_index</b> (the six percentile columns, metrics_available, "
    "nm_index, calculated_at). Optionally mirror nm_index onto the author "
    "table. Re-running is idempotent.",
]))

# ============================================================ 2
P("2.&nbsp; How it implements Equations 24&ndash;27", H1)
P("The six metrics split into two families that the paper treats differently.")

P("2.1&nbsp; Citation metrics &mdash; T_a, S_a, U_a", H2)
story.extend(bullets([
    "<b>Eq. 24 (transform):</b> L(x) = log<sub>10</sub>(x + 1). "
    "The +1 keeps log(0) defined; the log compresses the heavy right tail.",
    "<b>Eq. 25 (normalise), default &lsquo;hooked power law&rsquo;:</b> "
    "Nor(x) = Phi<sup>-1</sup>( P(L(x)) ), where "
    "P(v) = (r(v) &minus; 0.375) / (N + 0.25) is the Blom plotting position "
    "on the rank r, and Phi<sup>-1</sup> is the inverse standard-normal CDF.",
    "<b>Eq. 25 alternative &lsquo;log-normal&rsquo;:</b> "
    "Nor(x) = ( L(x) &minus; mean L(x) ) / sd L(x)  (population sd).",
    "<b>Eq. 26 (percentile):</b> Per(x) = 100 &middot; Phi( Nor(x) ).",
]))
P("<b>Exact simplification used in code:</b> for the hooked branch, "
  "100&middot;Phi(Phi<sup>-1</sup>(P)) = 100&middot;P identically, so the "
  "code computes Per(x) = 100 &middot; P(L(x)) directly and never forms the "
  "intermediate Nor. Eq. 27 only needs Per, so nothing is lost.", SMALL)

P("2.2&nbsp; Index metrics &mdash; Hf'_a, Hm'_a, G'_a", H2)
story.extend(bullets([
    "<b>Eq. 24 (transform):</b> P(x) = (r(x) &minus; 0.375) / (N + 0.25) "
    "directly on the raw index, with <b>fractional ranking</b> (tied values "
    "share the mean rank &mdash; essential because many authors have "
    "Hm' = Hf' = G' = 0).",
    "<b>Eq. 25:</b> Nor(x) = Phi<sup>-1</sup>( P(x) ).",
    "<b>Eq. 26:</b> Per(x) = 100 &middot; P(x).",
]))

P("2.3&nbsp; Ranking method (per Eq. 24 wording)", H2)
story.append(tbl([
    ["Family", "Paper wording", "Code setting", "pandas method"],
    ["Hf', Hm', G'", "\u201cfractional ranking \u2026 (many ties)\u201d", "RANK_METHOD_RANK", "\"average\""],
    ["T, S, U", "\u201cnormal ranking for the raw citations\u201d", "RANK_METHOD_LOG", "\"min\"  (competition)"],
], widths=[24*mm, 60*mm, 40*mm, 40*mm]))

P("2.4&nbsp; Eq. 27 &mdash; final score", H2)
P("Nm<sub>a</sub> = (i=1..6)  w<sub>i</sub> &middot; "
  "Per<sub>a</sub>(x<sub>i</sub>), with sum w<sub>i</sub> = 1. "
  "Default w<sub>i</sub> = 1/6 (equal weighting, the paper's suggestion) "
  "then a plain average of the six percentiles.")

story.append(PageBreak())

# ============================================================ 3
P("3.&nbsp; Alignment with the paper's worked example (&sect;3.3.3)", H1)
P("&sect;3.3.3 &ldquo;Final Nm-Index Calculation&rdquo; is the paper's only "
  "end-to-end numerical example. It states the exact recipe the code follows:")
P("&ldquo;citation metrics (T_a, S_a, U_a) follow a hooked power law, so "
  "Nor_a(x) = Phi<sup>-1</sup>(P(L(x))) &hellip; normal ranking. Indices "
  "(Hf', Hm', G') use fractional ranking for ties, with "
  "Nor_a(x) = Phi<sup>-1</sup>(P(x)).&rdquo;  Then Nm_a = (1/6) sum Per.",
  SMALL)
GAP(2)
story.append(tbl([
    ["Example metric", "Raw", "L(x)=log10(x+1)", "P (from rank)", "Per(x)=100\u00b7P"],
    ["T_a", "1.683", "0.4286", "0.5500", "55.00"],
    ["S_a", "0.374", "0.1380", "0.3000", "30.00"],
    ["U_a", "0.629", "0.2119", "0.4500", "45.00"],
    ["Hf'_a", "0.415", "\u2014 (rank raw)", "0.4000", "40.00"],
    ["Hm'_a", "0.113", "\u2014 (rank raw)", "0.2500", "25.00"],
    ["G'_a", "0.365", "\u2014 (rank raw)", "0.3500", "35.00"],
], widths=[28*mm, 18*mm, 34*mm, 30*mm, 30*mm]))
GAP(2)
P("Nm_a = (55 + 30 + 45 + 40 + 25 + 35) / 6 ~ <b>38.33</b> "
  "(~ 38th percentile globally).")
P("<b>Not reproducible exactly, and this is expected:</b> the P values above "
  "come from ranks the paper asserts by hand (&ldquo;r ~ 55000 "
  "(mid-range)&rdquo; inside a hypothetical N = 100,000 sample), not from a "
  "real dataset. The code reproduces the <b>formula path</b> that generates "
  "them; the specific figures are illustrative only. A unit test "
  "(test_matches_paper_section_333_mechanism) verifies the mechanism on a "
  "controlled input.", SMALL)

# ============================================================ 4
P("4.&nbsp; Assumptions &amp; choices requiring your sign-off", H1)
P("Each of these is a point where the paper is silent, ambiguous, or assumes "
  "ideal data. All are isolated in <b>config.py</b> and switchable without "
  "touching the maths. Current defaults are stated; please confirm or "
  "redirect.")

P("A.&nbsp; Distribution assumption for T_a, S_a, U_a &mdash; NM_DISTRIBUTION", H2)
P("Eq. 25 branches on whether a metric &ldquo;follows log normal&rdquo; "
  "(Z-score) or &ldquo;follows hooked power law&rdquo; (rank-based inverse "
  "normal). &sect;2.5 says this varies by research stream (humanities / social "
  "science ~ log-normal; medical / natural science ~ hooked).",
  SMALL)
P("<b>Assumed:</b> &ldquo;hooked&rdquo; for all three metrics &mdash; matches "
  "the &sect;3.3.3 worked example, and by the time these metrics reach this "
  "module they are already cross-field per-author aggregates, so there is no "
  "single field left to branch on. Switch any metric to &ldquo;lognormal&rdquo; "
  "if that stream is genuinely log-normal.", NOTE)

P("B.&nbsp; Reference population N in P(x) = (r &minus; 0.375)/(N + 0.25) "
  "&mdash; NM_REFERENCE_N", H2)
P("&sect;3.3.3 uses N = 100,000 because it ranks one profile inside a global "
  "100k-profile sample.", SMALL)
P("<b>Assumed:</b> N = number of authors actually scored for that metric "
  "(currently ~2,300), i.e. NM_REFERENCE_N = None. Percentiles are therefore "
  "<b>relative to the loaded cohort</b>, not a global figure. A fixed N = "
  "100,000 on a 2,300-author cohort would push every percentile toward 0, so "
  "cohort-N is the correct choice at this data scale &mdash; but the output "
  "should be read as &ldquo;percentile within this dataset&rdquo;.", NOTE)

P("C.&nbsp; Missing / NULL component metric &mdash; NM_REQUIRE_ALL_METRICS", H2)
P("The paper assumes all six metrics exist for every author. In the real DB "
  "some are NULL (notably total_cites: only 1561 / 2507 authors).", SMALL)
P("<b>Assumed:</b> NM_REQUIRE_ALL_METRICS = False. An author missing k of the "
  "six is scored on the remaining 6&minus;k, with the weights renormalised to "
  "sum to 1 over the available subset (so with equal weights, nm_index is the "
  "plain mean of the percentiles the author has). A NULL is <b>never</b> "
  "treated as a zero &mdash; it is dropped from both the ranking population "
  "and the average. The metrics_available column (0&ndash;6) records how many "
  "were used. Set to True to instead output NULL for any author without all "
  "six.", NOTE)

P("D.&nbsp; Rank tie method for T_a, S_a, U_a &mdash; RANK_METHOD_LOG", H2)
P("Eq. 24 says &ldquo;normal ranking for the raw citations&rdquo;. Assumed = "
  "&ldquo;min&rdquo; (competition ranking). <b>Consequence on real data:</b> "
  "the citation metrics also contain a large block of exact 0.0; under "
  "&ldquo;min&rdquo; that whole block shares rank 1 and lands near the 0th "
  "percentile. Switch to &ldquo;average&rdquo; to spread the zero-block to "
  "mid-scale instead.", NOTE)

P("E.&nbsp; Other minor, low-risk choices", H2)
story.extend(bullets([
    "Population standard deviation (ddof = 0) in the log-normal branch &mdash; "
    "the natural reading of &ldquo;standard deviation&rdquo;.",
    "total_cites is read from author_total_cites (identical twin of "
    "equation_11_total_cites); switch in config.METRIC_SOURCES if desired.",
    "The unreliable calculation_complete / calculation_status flags on the "
    "source tables are ignored by default (filter on value IS NOT NULL only); "
    "NM_FILTER_STATUS = True re-enables them.",
    "G'_a is read from author.modified_g_index (the modified_g_index_results "
    "table exists but is empty).",
], SMALL))

story.append(PageBreak())

# ============================================================ 5
P("5.&nbsp; Current data state (DB checked 2026-09-04, read-only)", H1)
story.append(tbl([
    ["Component metric", "Authors with a value", "Note"],
    ["total_cites (T_a)", "1561 / 2507", "rest still NULL upstream"],
    ["citations_per_paper (S_a)", "2321 / 2507", ""],
    ["citation_rate (U_a)", "2321 / 2507", ""],
    ["modified_hf_index (Hf'_a)", "2143 / 2507", "197 authors NO_ELIGIBLE_FIELDS"],
    ["modified_hm_index (Hm'_a)", "2254 / 2507", ""],
    ["modified_g_index (G'_a)", "2143 / 2507", "on author.modified_g_index"],
], widths=[50*mm, 40*mm, 60*mm]))
GAP(3)
P("Dry-run result (calculation only, nothing written):", H2)
story.append(tbl([
    ["metrics_available", "6", "5", "4", "3", "2", "0"],
    ["authors", "1537", "606", "24", "87", "67", "186"],
], widths=[38*mm] + [17*mm]*6, header=False))
GAP(2)
P("Scored: 2321 / 2507 authors. nm_index &mdash; median ~ 24.6, mean "
  "~ 27.1, max ~ 99.95. The low median is a direct symptom of the "
  "<b>upstream component metrics being ~96% exact zero</b>: most authors tie "
  "at the bottom of each ranking, with a thin tail of genuine achievers near "
  "100. This is mathematically consistent with the model, not a code defect, "
  "but the distribution shape is worth discussing.", SMALL)

# ============================================================ 6
P("6.&nbsp; Output", H1)
P("Table <b>author_nm_index</b> (created by schema.sql), one row per author:")
story.append(tbl([
    ["Column", "Meaning"],
    ["author_id", "PK, FK -> author"],
    ["per_total_cites \u2026 per_modified_g_index", "the six Per_a(x_i) values, 0\u2013100, NULL if that component is unavailable"],
    ["metrics_available", "SMALLINT 0\u20136 \u2014 how many components fed nm_index"],
    ["nm_index", "final Eq. 27 score; NULL if 0 components (or &lt;6 when NM_REQUIRE_ALL_METRICS)"],
    ["calculated_at", "run timestamp"],
], widths=[54*mm, 96*mm]))
GAP(3)
P("Optionally (NM_UPDATE_AUTHOR_TABLE = True) the final score is also mirrored "
  "onto author.nm_index, the same way author.modified_hm_index is populated.",
  SMALL)

# ============================================================ 7
P("7.&nbsp; Verification status", H1)
story.extend(bullets([
    "<b>13 unit tests pass</b> (test_calculator.py, pure in-memory, no DB). "
    "Every expected value is hand-derived in the test comments; Phi is taken "
    "from scipy.stats.norm exactly as Eq. 25/26 intend.",
    "Tests cover: Blom plotting position on fractional ranks; log + Z-score "
    "branch; log + hooked branch; the &sect;3.3.3 mechanism on a controlled "
    "5-author input; weight renormalisation over missing metrics; "
    "NM_REQUIRE_ALL_METRICS; all-NULL author -> NULL; custom weights; and the "
    "NM_REFERENCE_N override.",
    "<b>DB-to-calculator path</b> validated by read-only dry runs against the "
    "live database. No automated test exercises run_calculation.py / "
    "database.py (same known gap as the modified_hm_index module).",
    "The maths of Eq. 24&ndash;27 is implemented faithfully. The three items "
    "in section 4 (A&ndash;C) are modelling choices, not bugs; they are "
    "documented, defaulted sensibly, and configurable.",
]))

# ============================================================ appendix
P("Appendix &mdash; config.py knobs", H1)
story.append(tbl([
    ["Setting", "Default", "Effect"],
    ["NM_WEIGHTS", "1/6 each", "Eq. 27 weights w_i (must sum to 1)"],
    ["NM_DISTRIBUTION", "\"hooked\" x3", "per-citation-metric: \"hooked\" or \"lognormal\""],
    ["NM_REFERENCE_N", "None", "None = cohort size; int = fixed N in P(x)"],
    ["RANK_METHOD_LOG", "\"min\"", "tie handling for T/S/U ranking"],
    ["RANK_METHOD_RANK", "\"average\"", "tie handling for Hf'/Hm'/G' ranking (fractional)"],
    ["NM_REQUIRE_ALL_METRICS", "False", "False = score on available subset; True = NULL unless all 6"],
    ["NM_FILTER_STATUS", "False", "also require calculation_complete / status = READY"],
    ["NM_UPDATE_AUTHOR_TABLE", "False", "also write author.nm_index"],
    ["BLOM_A", "0.375", "Blom constant a in (r - a)/(N + 1 - 2a)"],
], widths=[46*mm, 24*mm, 80*mm]))

doc = SimpleDocTemplate(
    OUT, pagesize=A4,
    leftMargin=16*mm, rightMargin=16*mm, topMargin=14*mm, bottomMargin=14*mm,
    title="Final Nm-index - implementation summary",
    author="final_nm_index module",
)
doc.build(story)
print("wrote", OUT)
