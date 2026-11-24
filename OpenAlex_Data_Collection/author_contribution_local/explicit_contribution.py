"""Explicit author contribution (paper Eq 4-6) and multiple first/last authors (Eq 2).

Input table  author_contribution_statement  (one row per paper and author position):
    pub_id, position (1-based), aci_share (0-1 or %), credit_roles (JSON list of
    CRediT role names), equal_contrib (1 = marked as equal/co-first/co-last), source

Eq 6 picks one model per paper (alpha / beta / gamma*delta / gamma*phi):
    ACI    if every author has aci_share        W = V_p^f * B_p^i                (Eq 4)
    CRediT if every author has >= 1 role        W = V_p^f * sum_j h_j e_j^i /
                                                    sum_i sum_j h_j e_j^i      (Eq 5)
    otherwise the ordering models (A/R or RC); for RC, equal-contribution flags at
    the start / end of the author list give the core-first / core-last sets (Eq 2).

h_j: equal weights 1/14 (author decision 2026-11-24) until AHP weights are
supplied in a table credit_role_weight(field_name, role, weight).
"""

import json

CREDIT_ROLES = (
    'conceptualization', 'data curation', 'formal analysis', 'funding acquisition',
    'investigation', 'methodology', 'project administration', 'resources', 'software',
    'supervision', 'validation', 'visualization', 'writing - original draft',
    'writing - review & editing',
)
EQUAL_ROLE_WEIGHT = 1 / len(CREDIT_ROLES)

STATEMENT_SQL = """
CREATE TABLE IF NOT EXISTS author_contribution_statement (
    pub_id        TEXT NOT NULL,
    position      INTEGER NOT NULL,
    aci_share     REAL,
    credit_roles  TEXT,
    equal_contrib INTEGER NOT NULL DEFAULT 0,
    source        TEXT,
    PRIMARY KEY (pub_id, position)
) WITHOUT ROWID
"""


def normalise_role(name):
    text = ' '.join(str(name).lower().replace('&amp;', '&').replace('–', '-').split())
    text = text.replace('writing – ', 'writing - ').replace('writing-', 'writing - ')
    if text.startswith('writing') and 'review' in text:
        return 'writing - review & editing'
    if text.startswith('writing') and 'original' in text:
        return 'writing - original draft'
    if text in ('conceptualisation',):
        return 'conceptualization'
    if text in ('visualisation',):
        return 'visualization'
    return text if text in CREDIT_ROLES else None


def aci_shares(rows, n_authors):
    """Per-position shares (sum 1) if every author has an ACI share, else None."""
    values = [rows.get(i, {}).get('aci_share') for i in range(1, n_authors + 1)]
    if any(v is None or v < 0 for v in values) or sum(values) <= 0:
        return None
    total = sum(values)
    return [v / total for v in values]


def credit_shares(rows, n_authors, role_weight=None):
    """Eq 5 shares if every author lists at least one known CRediT role, else None."""
    weight = role_weight or (lambda role: EQUAL_ROLE_WEIGHT)
    scores = []
    for i in range(1, n_authors + 1):
        raw = rows.get(i, {}).get('credit_roles')
        roles = {normalise_role(r) for r in (json.loads(raw) if raw else [])} - {None}
        if not roles:
            return None
        scores.append(sum(weight(role) for role in roles))
    total = sum(scores)
    return [s / total for s in scores] if total > 0 else None


def core_positions(rows, n_authors):
    """Leading / trailing runs of equal-contribution flags -> (first set, last set)."""
    flagged = [bool(rows.get(i, {}).get('equal_contrib')) for i in range(1, n_authors + 1)]
    first = []
    for i, f in enumerate(flagged, start=1):
        if not f:
            break
        first.append(i)
    last = []
    for i in range(n_authors, 0, -1):
        if not flagged[i - 1] or i in first:
            break
        last.append(i)
    first = first if len(first) > 1 else []
    last = sorted(last) if len(last) > 1 else []
    return first or None, last or None


def fetch_statements(conn, pub_ids, chunk=500):
    """{pub_id: {position: {aci_share, credit_roles, equal_contrib}}}"""
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE name = "
                          "'author_contribution_statement'").fetchone()
    if not exists:
        return {}
    out = {}
    pub_ids = list(pub_ids)
    for start in range(0, len(pub_ids), chunk):
        part = pub_ids[start:start + chunk]
        marks = ",".join("?" * len(part))
        for pub, pos, aci, roles, eq in conn.execute(
                "SELECT pub_id, position, aci_share, credit_roles, equal_contrib "
                f"FROM author_contribution_statement WHERE pub_id IN ({marks})", part):
            out.setdefault(pub, {})[pos] = dict(aci_share=aci, credit_roles=roles,
                                                equal_contrib=eq)
    return out
