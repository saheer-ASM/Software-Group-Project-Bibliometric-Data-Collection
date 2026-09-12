"""Quota arithmetic for the stratified sample.

Three strata have to be satisfied at once:
  1. field       -- authors spread evenly over all 333 ASJC fields
  2. career age  -- a mix of young / moderately matured / matured
  3. behaviour   -- some high self-citers, some not

Field is the hard constraint (every field must be represented); career and
self-citation are targets balanced globally by rotating the demand across
fields, which is why the per-field plan is generated up front.
"""

import random

import config


def even_split(total, buckets):
    """Spread `total` over `len(buckets)` slots as evenly as possible."""
    count = len(buckets)
    base, remainder = divmod(total, count)
    return {bucket: base + (1 if index < remainder else 0)
            for index, bucket in enumerate(buckets)}


def field_quotas(total, fields, seed=config.RANDOM_SEED):
    """{field_name: n}. The remainder goes to a seeded-random set of fields so
    it is not always the alphabetically-first ones that get the extra author."""
    base, remainder = divmod(total, len(fields))
    quotas = {field: base for field in fields}
    rng = random.Random(seed)
    for field in rng.sample(list(fields), remainder):
        quotas[field] += 1
    return quotas


def career_plan(quotas, seed=config.RANDOM_SEED):
    """{field_name: [career_bucket, ...]} -- one entry per author slot.

    A single cursor walks the bucket order across all fields, so the buckets
    come out near-equal globally even though most fields only hold 3 authors.
    """
    order = config.CAREER_BUCKET_ORDER
    fields = list(quotas)
    random.Random(seed + 1).shuffle(fields)

    plan = {}
    cursor = 0
    for field in fields:
        slots = []
        for _ in range(quotas[field]):
            slots.append(order[cursor % len(order)])
            cursor += 1
        plan[field] = slots
    return {field: plan[field] for field in quotas}


class SelfCitationBalancer:
    """Decides, slot by slot, whether we currently want a high self-citer."""

    def __init__(self, target_share=config.TARGET_HIGH_SELF_CITATION_SHARE):
        self.target_share = target_share
        self.high = 0
        self.total = 0
        self.unknown = 0

    def wants_high(self):
        if self.total == 0:
            return self.target_share > 0
        return (self.high / self.total) < self.target_share

    def record(self, is_high):
        """`is_high` of None means OpenAlex holds no references for this author,
        so their behaviour is unmeasurable -- it must not dilute the target."""
        if is_high is None:
            self.unknown += 1
            return
        self.total += 1
        if is_high:
            self.high += 1

    @property
    def share(self):
        return 0.0 if self.total == 0 else self.high / self.total

    def high_search_tries(self):
        """How hard to hunt for a high self-citer on the next slot.

        Heavy self-citers are genuinely rare, so a fixed effort would spend six
        extra profiled candidates on nearly every one of a thousand slots and
        still come up empty.  Once enough of the cohort is in to show the true
        hit rate, back the search off instead of paying for it forever.
        """
        full = config.MAX_HIGH_SELF_CITER_TRIES
        if self.total < 30:
            return full
        if self.high == 0:
            return 2
        if self.share < self.target_share / 3:
            return max(2, full // 2)
        return full

