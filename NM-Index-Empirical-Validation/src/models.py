"""Stable-ID, database-independent records for validation adapters and fixtures."""

from dataclasses import dataclass
from math import isfinite


def _id(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty stable ID')


@dataclass(frozen=True)
class Author:
    author_id: str
    name: str | None = None

    def __post_init__(self):
        _id(self.author_id, 'author_id')


@dataclass(frozen=True)
class Publication:
    pub_id: str
    year: int | None
    total_citation: int | None

    def __post_init__(self):
        _id(self.pub_id, 'pub_id')
        if self.year is not None and (type(self.year) is not int or not 1000 <= self.year <= 9999):
            raise ValueError('year must be a four-digit integer or None')
        if self.total_citation is not None and (type(self.total_citation) is not int or self.total_citation < 0):
            raise ValueError('total_citation must be nonnegative integer or None')


@dataclass(frozen=True)
class Citation:
    cited_pub_id: str
    citing_pub_id: str

    def __post_init__(self):
        _id(self.cited_pub_id, 'cited_pub_id')
        _id(self.citing_pub_id, 'citing_pub_id')


@dataclass(frozen=True)
class AuthorPublication:
    author_id: str
    pub_id: str
    position: int

    def __post_init__(self):
        _id(self.author_id, 'author_id')
        _id(self.pub_id, 'pub_id')
        if type(self.position) is not int or self.position < 1:
            raise ValueError('position must be a positive integer')


@dataclass(frozen=True)
class Contribution:
    author_id: str
    pub_id: str
    weight: float | None

    def __post_init__(self):
        _id(self.author_id, 'author_id')
        _id(self.pub_id, 'pub_id')
        if self.weight is not None and (not isfinite(self.weight) or not 0 <= self.weight <= 1):
            raise ValueError('weight must be in [0,1] or None')


@dataclass(frozen=True)
class NMIndexRecord:
    author_id: str
    nm_index: float | None
    metrics_available: int | None

    def __post_init__(self):
        _id(self.author_id, 'author_id')
        if self.nm_index is not None and (not isfinite(self.nm_index) or not 0 <= self.nm_index <= 100):
            raise ValueError('NM percentile must be finite in [0,100] or None')
        if self.metrics_available is not None and (type(self.metrics_available) is not int or
                                                    not 0 <= self.metrics_available <= 6):
            raise ValueError('metrics_available must be an integer in [0,6] or None')
