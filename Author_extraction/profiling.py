"""Turn a raw OpenAlex author record into the profile the sheet asks for:
career age `t`, career bucket, and self-citation behaviour.

Profiling is split in two so the collector does not pay for both halves on
candidates it is going to reject:

    career_probe()          1 API call  -- cheap, decides the career bucket
    add_self_citation()     0-1 calls   -- only for candidates still in the running

For an author with no more works than SELF_CITATION_WORKS_CAP -- the large
majority -- the probe pulls their complete works list oldest-first, which yields
the exact first publication year *and* everything the self-citation measurement
needs.  That makes the second half free, halving the cost of the whole run,
which matters because OpenAlex's free tier is metered per day.
"""

import datetime

import config
from openalex import short_id

CURRENT_YEAR = datetime.date.today().year


def classify_high_self_citer(ratio):
    """None (unmeasurable) propagates; never collapse it to False."""
    if ratio is None:
        return None
    return ratio >= config.HIGH_SELF_CITATION_MIN


def career_factor(years_since_first_publication):
    """The sheet's CF_com = C * (t + 1) ** -lambda.

    Not used for sampling -- the buckets do that.  It is carried on every output
    row so the value can be reconciled against the `career_factor` the upstream
    job writes into `author_paper_field_effective_citation`.
    """
    if years_since_first_publication is None:
        return None
    return config.CAREER_FACTOR_C * (
        (years_since_first_publication + 1) ** -config.CAREER_FACTOR_LAMBDA)


def career_bucket(years_since_first_publication):
    if years_since_first_publication is None:
        return None
    for name in config.CAREER_BUCKET_ORDER:
        low, high = config.CAREER_BUCKETS[name]
        if low <= years_since_first_publication <= high:
            return name
    return config.CAREER_BUCKET_ORDER[-1]


def self_citation_ratio(works, author_work_ids):
    """Share of this author's outgoing references that point at their own work.

    Citing-side measure: of everything the author cited, how much was themself.
    Returns (ratio, self_reference_count, total_reference_count).
    """
    self_refs = 0
    total_refs = 0
    for work in works:
        for reference in work.get("referenced_works") or []:
            total_refs += 1
            if short_id(reference) in author_work_ids:
                self_refs += 1
    if total_refs == 0:
        return None, 0, 0
    return self_refs / total_refs, self_refs, total_refs


def primary_field(author):
    """Top-ranked OpenAlex topic of an author, flattened to names."""
    topics = author.get("topics") or []
    if not topics:
        return None, None, None
    top = topics[0]
    return (top.get("display_name"),
            (top.get("subfield") or {}).get("display_name"),
            (top.get("field") or {}).get("display_name"))


def career_probe(client, author, assigned_field=None):
    """Cheap half: identity, headline metrics and career bucket. 1 API call."""
    author_id = short_id(author["id"])
    works_count = author.get("works_count") or 0

    if works_count <= config.SELF_CITATION_WORKS_CAP:
        # Complete record in one call -- keep it for add_self_citation().
        works = client.author_works(author_id, config.SELF_CITATION_WORKS_CAP,
                                    oldest_first=True)
        years = [w.get("publication_year") for w in works
                 if w.get("publication_year")]
        first_year = min(years) if years else None
    else:
        works = None
        first_year = client.first_publication_year(author_id)

    t = None if first_year is None else max(0, CURRENT_YEAR - int(first_year))

    stats = author.get("summary_stats") or {}
    institutions = author.get("last_known_institutions") or []
    topic_name, subfield_name, domain_field = primary_field(author)

    return {
        "openalex_id": author_id,
        "display_name": author.get("display_name"),
        "orcid": (author.get("orcid") or "").replace("https://orcid.org/", "") or None,
        "assigned_field": assigned_field,
        "openalex_top_topic": topic_name,
        "openalex_subfield": subfield_name,
        "openalex_field": domain_field,
        "works_count": author.get("works_count"),
        "cited_by_count": author.get("cited_by_count"),
        "h_index": stats.get("h_index"),
        "i10_index": stats.get("i10_index"),
        "mean_citedness_2yr": stats.get("2yr_mean_citedness"),
        "first_publication_year": first_year,
        "years_since_first_publication": t,
        "career_bucket": career_bucket(t),
        "career_factor_cf_com": (None if career_factor(t) is None
                                 else round(career_factor(t), 6)),
        "last_known_institution": (institutions[0].get("display_name")
                                   if institutions else None),
        "country_code": (institutions[0].get("country_code")
                         if institutions else None),
        "self_citation_ratio": None,
        "self_references": 0,
        "total_references": 0,
        "works_inspected": 0,
        "high_self_citer": None,
        # Private, stripped by add_self_citation before anything is serialised.
        "_works": works,
    }


def add_self_citation(client, profile):
    """Expensive half: fetch the author's works and measure self-citation.

    Idempotent -- a profile that already carries a ratio is returned untouched.
    """
    if profile.get("works_inspected"):
        profile.pop("_works", None)
        return profile

    works = profile.pop("_works", None)
    if works is None:
        works = client.author_works(profile["openalex_id"],
                                    config.SELF_CITATION_WORKS_CAP)
    own_ids = {short_id(w["id"]) for w in works}
    ratio, self_refs, total_refs = self_citation_ratio(works, own_ids)

    profile["self_citation_ratio"] = None if ratio is None else round(ratio, 4)
    profile["self_references"] = self_refs
    profile["total_references"] = total_refs
    profile["works_inspected"] = len(works)
    profile["high_self_citer"] = classify_high_self_citer(profile["self_citation_ratio"])
    return profile


def build_profile(client, author, assigned_field=None):
    """Both halves at once -- used by the laureate cohort, which keeps everyone."""
    return add_self_citation(client, career_probe(client, author, assigned_field))
