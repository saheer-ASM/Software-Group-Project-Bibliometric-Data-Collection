"""Collect the field-distributed general cohort (1,000 authors by default).

Per ASJC field: draw a candidate pool from OpenAlex, probe candidates cheaply
for their career bucket, and only pay for the self-citation measurement on
candidates that are still in the running for a slot.

Two pools are drawn per field.  The base pool is a uniform random sample of the
field's authors; the prolific pool is the same field restricted to authors with
many works.  Slots that need a high self-citer are served from the prolific pool
first, because a uniform random author almost never self-cites heavily.

Progress is appended to a JSONL checkpoint after every field, so an interrupted
run resumes instead of restarting.
"""

import json
import os
import zlib
from collections import deque

import config
import quotas as quota_lib
from field_mapping import author_filter_for_field, build_field_map
from openalex import BudgetExhausted, short_id
from profiling import add_self_citation, career_probe

CHECKPOINT = os.path.join(config.CACHE_DIR, "general_checkpoint.jsonl")


def _load_checkpoint():
    """Replay the checkpoint, de-duplicated by author.

    The file is append-only JSON Lines that teammates merge through git, so the
    documented conflict fix is "keep both sides" -- which means the same author
    can legitimately appear twice.  De-duplicate here so that stays harmless.
    """
    if not os.path.exists(CHECKPOINT):
        return {}
    done, seen, damaged = {}, set(), 0
    with open(CHECKPOINT, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                damaged += 1        # e.g. a git conflict marker left behind
                continue
            if record.get("openalex_id") in seen:
                continue
            seen.add(record.get("openalex_id"))
            done.setdefault(record["assigned_field"], []).append(record)
    if damaged:
        print(f"!! {CHECKPOINT}: skipped {damaged} unparseable line(s) -- "
              f"check for leftover git conflict markers")
    return done


def _append_checkpoint(rows):
    os.makedirs(config.CACHE_DIR, exist_ok=True)
    with open(CHECKPOINT, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class FieldPool:
    """Candidate supply for one field: two raw queues plus probed leftovers."""

    def __init__(self, client, field_name, entry, slot_count, seed, taken):
        self.client = client
        self.field_name = field_name
        self.taken = taken
        self.leftovers = []

        pool_size = max(config.MIN_CANDIDATE_POOL,
                        slot_count * config.CANDIDATE_POOL_MULTIPLIER)
        prolific_size = max(config.MIN_CANDIDATE_POOL // 2, pool_size // 3)

        base_filter = author_filter_for_field(entry)
        prolific_filter = author_filter_for_field(
            entry, min_works=config.PROLIFIC_MIN_WORKS)

        self.queues = {
            "base": deque(client.sample_authors(base_filter, pool_size, seed)),
            "prolific": deque(client.sample_authors(prolific_filter,
                                                    prolific_size, seed + 1)),
        }

    def _next_probe(self, prefer_prolific):
        order = ("prolific", "base") if prefer_prolific else ("base", "prolific")
        for key in order:
            queue = self.queues[key]
            while queue:
                candidate = queue.popleft()
                author_id = short_id(candidate["id"])
                if author_id in self.taken:
                    continue
                self.taken.add(author_id)
                return career_probe(self.client, candidate, self.field_name)
        return None

    def stream(self, bucket, prefer_prolific, limit):
        """Up to `limit` candidates in `bucket`. Others are parked as leftovers."""
        yielded = 0
        for index, profile in enumerate(self.leftovers):
            if profile["career_bucket"] == bucket:
                self.leftovers.pop(index)
                yield profile
                yielded += 1
                break

        while yielded < limit:
            profile = self._next_probe(prefer_prolific)
            if profile is None:
                return
            if profile["career_bucket"] == bucket:
                yield profile
                yielded += 1
            else:
                self.leftovers.append(profile)

    def any_leftover(self):
        return self.leftovers.pop(0) if self.leftovers else None


def collect_field(client, field_name, entry, wanted_buckets, balancer, taken):
    """Fill one field's slots. Returns (rows, status)."""
    if author_filter_for_field(entry) is None:
        return [], "unresolved_field"

    # crc32, not hash(): str hashing is salted per process, which would make
    # the sample non-reproducible between runs.
    seed = (config.RANDOM_SEED
            + zlib.crc32(field_name.encode("utf-8"))) % 100000
    pool = FieldPool(client, field_name, entry, len(wanted_buckets), seed, taken)

    kept, unfilled = [], 0
    for bucket in wanted_buckets:
        want_high = balancer.wants_high()
        limit = balancer.high_search_tries() if want_high else 2

        chosen, settled = None, None
        for profile in pool.stream(bucket, prefer_prolific=want_high, limit=limit):
            add_self_citation(client, profile)
            if profile["high_self_citer"] is want_high:
                chosen = profile
                break
            # Prefer a fallback whose behaviour is at least measurable; an
            # author with no references in OpenAlex tells us nothing either way.
            if settled is None or (settled["high_self_citer"] is None
                                   and profile["high_self_citer"] is not None):
                settled = profile

        chosen = chosen or settled
        if chosen is None:
            # Field too thin for this bucket -- take any probed candidate rather
            # than leave the field short, and record the mismatch.
            chosen = pool.any_leftover()
            if chosen is None:
                unfilled += 1
                continue
            add_self_citation(client, chosen)

        chosen["slot_bucket"] = bucket
        chosen["bucket_matched"] = chosen["career_bucket"] == bucket
        kept.append(chosen)
        balancer.record(chosen["high_self_citer"])

    status = "complete" if not unfilled else f"short_by_{unfilled}"
    return kept, status


def collect(client, target=None, resume=True, verbose=True):
    target = target or config.TARGET_GENERAL_AUTHORS
    field_map = build_field_map(client, verbose=verbose)

    quotas = quota_lib.field_quotas(target, config.FIELDS)
    plan = quota_lib.career_plan(quotas)

    done = _load_checkpoint() if resume else {}
    balancer = quota_lib.SelfCitationBalancer()
    rows, taken = [], set()
    for field_rows in done.values():
        for row in field_rows:
            rows.append(row)
            taken.add(row["openalex_id"])
            balancer.record(row.get("high_self_citer"))

    report = []
    for index, field_name in enumerate(config.FIELDS, start=1):
        if field_name in done:
            report.append({"field_name": field_name, "quota": quotas[field_name],
                           "collected": len(done[field_name]), "status": "cached"})
            continue
        if field_name not in field_map:
            report.append({"field_name": field_name, "quota": quotas[field_name],
                           "collected": 0, "status": "not_mapped"})
            continue

        try:
            kept, status = collect_field(client, field_name,
                                         field_map[field_name],
                                         plan[field_name], balancer, taken)
        except BudgetExhausted as exc:
            # Whole fields are checkpointed, so the partial field in flight is
            # simply redone tomorrow; nothing already banked is lost.
            print(f"\n!! {exc}")
            print(f"   resumes at {exc.reset_text}; re-run the same "
                  f"command to continue from the checkpoint")
            report.append({"field_name": field_name,
                           "quota": quotas[field_name], "collected": 0,
                           "status": "budget_exhausted"})
            break
        rows.extend(kept)
        _append_checkpoint(kept)
        report.append({"field_name": field_name, "quota": quotas[field_name],
                       "collected": len(kept), "status": status})

        if verbose:
            print(f"[{index}/{len(config.FIELDS)}] {field_name[:44]:44s} "
                  f"{len(kept)}/{quotas[field_name]} {status:12s} "
                  f"total={len(rows)} high-self-cite={balancer.share:.0%} "
                  f"calls={client.request_count}")

    return rows, report
