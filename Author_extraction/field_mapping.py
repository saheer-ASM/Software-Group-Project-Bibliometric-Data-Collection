"""Map the 333 ASJC subject-area names onto OpenAlex topic ids.

Authors can only be filtered by `topics.id` in OpenAlex -- never by subfield or
field -- so each ASJC name has to resolve to a list of topic ids that gets OR-ed
into one author filter.

The vocabulary is downloaded in bulk once (see `topic_index`) and every name is
then matched locally, so building the whole map costs ~25 requests instead of
the ~700 the original per-field search approach needed.
"""

import json
import os

import config
import topic_index


def build_field_map(client, fields=None, refresh=False, verbose=True):
    """{field_name: {...topic_ids...}} for every ASJC field, cached on disk."""
    fields = fields or config.FIELDS

    if os.path.exists(config.FIELD_MAP_CACHE) and not refresh:
        with open(config.FIELD_MAP_CACHE, encoding="utf-8") as handle:
            cached = json.load(handle)
        if all(name in cached for name in fields):
            return {name: cached[name] for name in fields}

    index = topic_index.fetch_index(client, verbose=verbose)
    tables = topic_index.lookup_tables(index)
    resolved = {name: topic_index.resolve(name, index, tables) for name in fields}

    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(config.FIELD_MAP_CACHE, "w", encoding="utf-8") as handle:
        json.dump(resolved, handle, indent=2, ensure_ascii=False)

    if verbose:
        counts = {}
        for entry in resolved.values():
            counts[entry["match_type"]] = counts.get(entry["match_type"], 0) + 1
        print(f"  field map: {len(resolved)} fields -> {counts}")

    return resolved


def author_filter_for_field(entry, min_works=None):
    """OpenAlex author filter string for one field, or None if unresolvable."""
    topic_ids = entry.get("topic_ids") or []
    if not topic_ids:
        return None
    min_works = config.MIN_WORKS_COUNT if min_works is None else min_works
    capped = topic_ids[:config.MAX_TOPIC_IDS_PER_FILTER]
    return f"topics.id:{'|'.join(capped)},works_count:>{min_works - 1}"
