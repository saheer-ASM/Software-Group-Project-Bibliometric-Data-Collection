"""Offline adapter for labelled synthetic test data; it never imports database access."""

from tests.fixtures.synthetic import LABEL, make_fixture


def load_all():
    return make_fixture()
