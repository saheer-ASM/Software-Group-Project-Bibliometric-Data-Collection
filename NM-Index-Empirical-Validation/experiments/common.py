"""Shared experiment result helpers."""

import pandas as pd


def pending(issue, status='METHODOLOGY_PENDING'):
    return {'status': pd.DataFrame([dict(status=status, issue=issue)])}
