"""Bulk OpenAlex topic/subfield index, fetched once and matched locally.

The first design resolved each of the 333 ASJC names with its own API calls
(a subfield search, then that subfield's topics).  That cost ~2.1 requests per
field and burned an entire daily budget on 243 fields without collecting a
single author -- and the `/subfields?search=` endpoint it relied on returned
confidently wrong answers, mapping "Colloid and Surface Chemistry" to
Biomedical Engineering.

OpenAlex only has 26 fields, 252 subfields and ~4.5k topics in total, so the
whole vocabulary fits in ~25 requests.  Download it once, then match all 333
names against it in memory: no per-field API cost, exact matches preferred over
fuzzy ones, and every mapping inspectable before a single author is collected.
"""

import difflib
import json
import os
import re

import config
from openalex import short_id

INDEX_CACHE = os.path.join(config.CACHE_DIR, "openalex_topic_index.json")
PARTIAL_CACHE = os.path.join(config.CACHE_DIR, "openalex_topic_index.partial.json")
FUZZY_CUTOFF = 0.86


def normalise(name):
    """Lowercase, strip punctuation and the noise words that differ between the
    ASJC vocabulary and OpenAlex's ("General X", "X (miscellaneous)")."""
    text = (name or "").lower()
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(general|and|of|the|miscellaneous)\b", " ", text)
    return " ".join(text.split())


def _load_partial():
    if os.path.exists(PARTIAL_CACHE):
        with open(PARTIAL_CACHE, encoding="utf-8") as handle:
            return json.load(handle)
    return {"subfields": {}, "fields": {}, "topics": [], "cursor": "*"}


def _save_partial(state):
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(PARTIAL_CACHE, "w", encoding="utf-8") as handle:
        json.dump(state, handle)


def fetch_index(client, refresh=False, verbose=True):
    """The whole OpenAlex topic vocabulary, cached on disk after one download.

    Saves progress as it pages, because the daily budget can run out mid-way and
    losing a partial download costs another whole day.  Re-running continues
    from the stored cursor.
    """
    if os.path.exists(INDEX_CACHE) and not refresh:
        with open(INDEX_CACHE, encoding="utf-8") as handle:
            return json.load(handle)

    state = {"subfields": {}, "fields": {}, "topics": [], "cursor": "*"}         if refresh else _load_partial()

    if not state["subfields"]:
        state["subfields"] = {short_id(i["id"]): i["display_name"]
                              for i in client.paged("/subfields", per_page=200,
                                                    select="id,display_name")}
        _save_partial(state)
    if not state["fields"]:
        state["fields"] = {short_id(i["id"]): i["display_name"]
                           for i in client.paged("/fields", per_page=200,
                                                 select="id,display_name")}
        _save_partial(state)
    if verbose:
        print(f"  topic index: {len(state['subfields'])} subfields, "
              f"{len(state['fields'])} fields")

    while state["cursor"]:
        page = client.get("/topics", per_page=200, cursor=state["cursor"],
                          select="id,display_name,subfield,field")
        for item in page.get("results", []):
            state["topics"].append({
                "id": short_id(item["id"]),
                "name": item["display_name"],
                "subfield": short_id((item.get("subfield") or {}).get("id")),
                "field": short_id((item.get("field") or {}).get("id")),
            })
        state["cursor"] = page.get("meta", {}).get("next_cursor")
        _save_partial(state)
        if verbose:
            print(f"  topic index: {len(state['topics'])} topics "
                  f"({client.request_count} requests)")

    topics_by_subfield, subfields_by_field, topic_names = {}, {}, {}
    for topic in state["topics"]:
        topic_names[topic["name"]] = topic["subfield"]
        if not topic["subfield"]:
            continue
        topics_by_subfield.setdefault(topic["subfield"], []).append(topic["id"])
        if topic["field"]:
            bucket = subfields_by_field.setdefault(topic["field"], [])
            if topic["subfield"] not in bucket:
                bucket.append(topic["subfield"])

    index = {"subfields": state["subfields"], "fields": state["fields"],
             "topics_by_subfield": topics_by_subfield,
             "subfields_by_field": subfields_by_field,
             "topic_names": topic_names}
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(INDEX_CACHE, "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=2, ensure_ascii=False)
    if os.path.exists(PARTIAL_CACHE):
        os.remove(PARTIAL_CACHE)
    return index


def lookup_tables(index):
    return (
        {normalise(n): i for i, n in index["subfields"].items()},
        {normalise(n): i for i, n in index.get("fields", {}).items()},
        {normalise(n): s for n, s in index["topic_names"].items() if s},
    )


def topics_for_field(index, field_id, limit):
    """Topics spanning a whole OpenAlex field, spread evenly over its subfields.

    A field holds far more topics than the OR-list cap allows, so take them
    round-robin across its subfields rather than the first N -- otherwise one
    corner of a broad umbrella category would stand in for the whole thing.
    """
    buckets = [list(index["topics_by_subfield"].get(sid, []))
               for sid in index.get("subfields_by_field", {}).get(field_id, [])]
    picked, depth = [], 0
    while len(picked) < limit and any(len(b) > depth for b in buckets):
        for bucket in buckets:
            if depth < len(bucket):
                picked.append(bucket[depth])
                if len(picked) >= limit:
                    break
        depth += 1
    return picked


def _subfield_entry(field_name, index, subfield_id, how):
    return {"field_name": field_name, "match_type": how,
            "subfield_id": subfield_id,
            "subfield_name": index["subfields"].get(subfield_id),
            "topic_ids": index["topics_by_subfield"].get(subfield_id, [])}


def resolve(field_name, index, tables=None, topic_limit=None):
    """Map one ASJC name to OpenAlex topic ids, with no API call.

    Exact matches are tried before any fuzzy one, deliberately: the search
    endpoint this replaced was wrong precisely because it always fuzzy-matched.
    """
    topic_limit = topic_limit or config.MAX_TOPIC_IDS_PER_FILTER
    by_subfield, by_field, by_topic = tables or lookup_tables(index)
    key = normalise(field_name)

    if key in by_subfield:
        return _subfield_entry(field_name, index, by_subfield[key],
                               "subfield_exact")

    # ASJC umbrella categories ("General Chemistry", "Chemistry (miscellaneous)")
    # have no subfield equivalent -- OpenAlex's 252 subfields are ASJC with the
    # umbrella and miscellaneous entries stripped out.  Use the field level.
    if key in by_field:
        field_id = by_field[key]
        return {"field_name": field_name, "match_type": "field_exact",
                "subfield_id": None,
                "subfield_name": index["fields"].get(field_id),
                "topic_ids": topics_for_field(index, field_id, topic_limit)}

    if key in by_topic:
        return _subfield_entry(field_name, index, by_topic[key], "topic_exact")

    match = difflib.get_close_matches(key, by_subfield, 1, FUZZY_CUTOFF)
    if match:
        return _subfield_entry(field_name, index, by_subfield[match[0]],
                               "subfield_fuzzy")

    match = difflib.get_close_matches(key, by_topic, 1, FUZZY_CUTOFF)
    if match:
        return _subfield_entry(field_name, index, by_topic[match[0]],
                               "topic_fuzzy")

    return {"field_name": field_name, "match_type": "unresolved",
            "subfield_id": None, "subfield_name": None, "topic_ids": []}
