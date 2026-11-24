"""Check our C-score against the published Ioannidis/Elsevier top-2% values.

Input: a CSV exported from the published database with columns
author_id (OpenAlex ID, matched beforehand) and c_published; and our
validation_dataset.csv (author_id, c_score_raw). Prints n, Pearson and Spearman r.

Usage: python -m src.compare_published_cscore --published pub.csv --ours results/.../validation_dataset.csv
"""
import argparse

import pandas as pd


def compare(published, ours):
    m = published.merge(ours, on='author_id').dropna(subset=['c_published', 'c_score_raw'])
    return dict(n=len(m), pearson=m.c_published.corr(m.c_score_raw),
                spearman=m.c_published.corr(m.c_score_raw, method='spearman'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--published', required=True)
    p.add_argument('--ours', required=True)
    a = p.parse_args()
    print(compare(pd.read_csv(a.published), pd.read_csv(a.ours)))


if __name__ == '__main__':
    main()
