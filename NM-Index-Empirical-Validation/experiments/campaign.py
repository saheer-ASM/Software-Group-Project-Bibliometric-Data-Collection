"""Test campaigns (smoke / full / sensitivity analysis) with a status watchdog.

Every --watchdog minutes (default 20) it prints and appends to <out>/campaign_status.log:
  "x tests passed, y tests running, z tests pending, k tests fixed,
   campaign <name>, ETA x hour y minutes"
A test that fails is retried once; if the retry passes it counts as "fixed".

Sensitivity analysis: each hyperparameter is swept on the synthetic benchmark
with the metric that matches it; every (value, seed) result is written with its
running mean to sensitivity_cycles.csv, and sensitivity_summary.csv gives the
mean, 95% CI over seeds and the selected (best) value.

  hyperparameter        values                     metric (direction)
  epsilon_0 (ISC)       0.50 0.75 0.90 1.00         core-author self-citation inflation (lower)
  career (C, lambda)    (1,0) (1.25,.0601)          seniority bias |rho| (lower)
                        (1.5,.10) (2,.15)
  cap percentile k      0.90 0.95 0.99 0.999        AUC with outlier papers (higher)
  sub-score weights     equal, citation-heavy,      AUC (higher)
                        h-type-heavy
Selection: best mean on the metric, among values whose AUC is within 0.02 of the
best AUC for that hyperparameter (so no value wins by losing discrimination).

Usage (from NM-Index-Empirical-Validation):
  python -m experiments.campaign --campaign sensitivity --seeds 5 --workers 4
  python -m experiments.campaign --campaign smoke --watchdog 0.1
"""

import argparse
import ctypes
import os
import math
import threading
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, t as student_t

from experiments import synthetic_benchmark as sb
from nm_index.counterfactual_calculator import NMParameters

GRID = {
    'epsilon_0': [0.50, 0.75, 0.90, 1.00],
    'career': [(1.0, 0.0), (1.25, 0.0601), (1.5, 0.10), (2.0, 0.15)],
    'cap_k': [0.90, 0.95, 0.99, 0.999],
    'weights': ['equal', 'citation_heavy', 'h_type_heavy'],
}
WEIGHTS = {'equal': (1 / 6,) * 6,
           'citation_heavy': (0.25, 0.25, 0.20, 0.10, 0.10, 0.10),
           'h_type_heavy': (0.10, 0.10, 0.10, 0.25, 0.25, 0.20)}
METRIC = {'epsilon_0': ('selfcite_inflation', 'lower'), 'career': ('seniority_bias', 'lower'),
          'cap_k': ('auc', 'higher'), 'weights': ('auc', 'higher')}


def evaluate(param, value, seed, size):
    """One sensitivity test: build a population, score it with this setting, return metrics."""
    sb.SIZE.update(size)
    kw = {}
    if param == 'epsilon_0':
        kw['epsilon_0'] = value
    elif param == 'career':
        kw['career_boost'], kw['career_decay'] = value
    elif param == 'weights':
        kw['weights'] = WEIGHTS[value]
    if param == 'cap_k':
        sb.SIZE.update(cap_q=value, outliers=0.3)
    rng = np.random.default_rng(seed)
    pop = sb.make_population(rng, size['authors'])
    q = pd.Series({a['author_id']: a['q'] for a in pop})
    years = pd.Series({a['author_id']: sb.AS_OF - a['start'] for a in pop})
    params = NMParameters(as_of_year=sb.AS_OF, **kw)
    frozen, nm = sb.frozen_reference(pop, params)
    nm = pd.Series(nm)
    out = dict(param=param, value=str(value), seed=seed,
               auc=sb.auc(nm, q >= q.quantile(0.8)),
               seniority_bias=abs(spearmanr(nm, years[nm.index]).statistic))
    if param == 'epsilon_0':
        normal = [a for a in pop if a['kind'] == 'normal'][:size['targets']]
        base = sb.baseline_scores(pop)
        inf = sb.inflation(pop, frozen, params, base, nm.values, normal, sb.add_core_citations, 0.5, rng)
        out['selfcite_inflation'] = inf['nm_index|value']   # raw value change: no percentile ceiling
    return out


def full_test(i, size):
    """Full campaign: one seed of every SOTA, gaming and ablation experiment."""
    sb.SIZE.update(size)
    return sb.one_seed(i, size['authors'], 'all').to_dict('records')


def final_test(kind, i, size):
    """Final campaign: SOTA as a full 5-point sweep (many seeds), ablation as spot tests."""
    sb.SIZE.update(size)
    return sb.one_seed(i, size['authors'], kind).to_dict('records')


def smoke_test(i, size):
    """Smoke campaign: one SOTA and one ablation seed."""
    sb.SIZE.update(size)
    which = 'sota' if i % 2 == 0 else 'ablation'
    df = sb.one_seed(i, size['authors'], which)
    return dict(param='smoke', value=which, seed=i, rows=len(df))


def low_priority():
    """Worker initializer: run at idle priority so other simulations on the shared
    machine always get the CPU first."""
    try:
        if os.name == 'nt':
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
        else:
            os.nice(19)
    except Exception:
        pass


def free_ram_gb():
    if os.name != 'nt':
        return float(os.sysconf('SC_AVPHYS_PAGES') * os.sysconf('SC_PAGE_SIZE')) / 2**30
    class MS(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    free_ram_gb.total = m.ullTotalPhys / 2**30
    return m.ullAvailPhys / 2**30


def cpu_load():
    """System CPU busy % over 0.5 s (Windows GetSystemTimes)."""
    if os.name != 'nt':
        return float('nan')
    def times():
        i, k, u = (ctypes.c_ulonglong() for _ in range(3))
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
        return i.value, k.value + u.value
    i0, t0 = times(); time.sleep(0.5); i1, t1 = times()
    return 100.0 * (1 - (i1 - i0) / max(t1 - t0, 1))


class Watchdog:
    def __init__(self, name, total, minutes, log):
        self.name, self.total, self.minutes, self.log = name, total, minutes, log
        self.passed = self.running = self.fixed = 0
        self.started = time.time()
        self.lock = threading.Lock()
        self.stop = threading.Event()

    def message(self):
        with self.lock:
            done = self.passed
            pending = self.total - done - self.running
            elapsed = time.time() - self.started
            remaining = elapsed / done * (self.total - done) if done else float('nan')
        eta = ('unknown' if math.isnan(remaining) else
               f'{int(remaining // 3600)} hour {int(remaining % 3600 // 60)} minutes')
        free = free_ram_gb()
        total = getattr(free_ram_gb, 'total', float('nan'))
        return (f'{done} tests passed, {self.running} tests running, {pending} tests pending, '
                f'{self.fixed} tests fixed, campaign {self.name}, ETA {eta} | '
                f'CPU {cpu_load():.0f}%, free RAM {free:.1f}/{total:.1f} GB')

    def emit(self):
        line = time.strftime('%H:%M:%S ') + self.message()
        print(line, flush=True)
        with open(self.log, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

    def run(self):
        while not self.stop.wait(self.minutes * 60):
            self.emit()


def ci(v):
    v = pd.Series(v).dropna()
    n = len(v)
    half = student_t.ppf(0.975, n - 1) * v.std(ddof=1) / math.sqrt(n) if n > 1 else float('nan')
    return pd.Series(dict(n=n, mean=v.mean(), ci95_low=v.mean() - half, ci95_high=v.mean() + half))


def summarise(rows):
    df = pd.DataFrame(rows)
    out = []
    for param, (metric, direction) in METRIC.items():
        d = df[df.param.eq(param)]
        if d.empty or metric not in d:
            continue
        s = d.groupby('value')[metric].apply(ci).unstack()
        s['auc_mean'] = d.groupby('value').auc.mean()
        ok = s[s.auc_mean >= s.auc_mean.max() - 0.02]
        best = ok['mean'].idxmin() if direction == 'lower' else ok['mean'].idxmax()
        s = s.reset_index().assign(param=param, metric=metric, direction=direction,
                                   selected=lambda x: x.value.eq(best))
        out.append(s)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--campaign', choices=['smoke', 'spot', 'full', 'final', 'sensitivity'], default='sensitivity')
    p.add_argument('--seeds', type=int, default=5)
    p.add_argument('--ablation-seeds', type=int, default=3, help='final campaign: spot-test seeds for ablation')
    p.add_argument('--workers', type=int, default=2, help='shared machine: at most half the logical cores')
    p.add_argument('--min-free-ram-share', type=float, default=0.25,
                   help='shared machine: wait before starting a test while free RAM < this share of total')
    p.add_argument('--watchdog', type=float, default=20.0, help='minutes between status messages')
    p.add_argument('--authors', type=int, default=16)
    p.add_argument('--max-papers', type=int, default=8)
    p.add_argument('--cite-scale', type=float, default=0.5)
    p.add_argument('--targets', type=int, default=3)
    p.add_argument('--role-merit', action='store_true')
    p.add_argument('--out', default='results/campaign')
    a = p.parse_args()
    out = Path(a.out) / a.campaign
    out.mkdir(parents=True, exist_ok=True)
    size = dict(authors=a.authors, max_papers=a.max_papers, cite_scale=a.cite_scale, targets=a.targets,
                outliers=0.0, cap_q=0.999, role_merit=a.role_merit)
    if a.campaign == 'smoke':
        jobs = [(smoke_test, (i, size)) for i in range(a.seeds)]
    elif a.campaign == 'final':
        jobs = ([(final_test, ('sota', i, size)) for i in range(a.seeds)] +
                [(final_test, ('ablation', i, size)) for i in range(a.ablation_seeds)])
    elif a.campaign in ('full', 'spot'):
        jobs = [(full_test, (i, size)) for i in range(a.seeds)]
    else:
        jobs = [(evaluate, (param, v, s, size)) for param, values in GRID.items()
                for v in values for s in range(a.seeds)]
    dog = Watchdog(a.campaign, len(jobs), a.watchdog, out / 'campaign_status.log')
    threading.Thread(target=dog.run, daemon=True).start()
    rows, failed = [], []
    a.workers = max(1, min(a.workers, (os.cpu_count() or 2) // 2))
    free_ram_gb()
    low_priority()
    with ProcessPoolExecutor(max_workers=a.workers, initializer=low_priority) as pool:
        futures = {}
        for fn, args in jobs:
            while free_ram_gb() < a.min_free_ram_share * free_ram_gb.total:   # keep >= 25% RAM free
                time.sleep(30)
            futures[pool.submit(fn, *args)] = (fn, args, 0)
        dog.running = min(a.workers, len(jobs))
        while futures:
            for fut in as_completed(list(futures)):
                fn, args, tries = futures.pop(fut)
                try:
                    res = fut.result()
                    rows.extend(res if isinstance(res, list) else [res])
                    with dog.lock:
                        dog.passed += 1
                        dog.fixed += tries          # passed on a retry
                except Exception:
                    if tries == 0:                  # retry once
                        futures[pool.submit(fn, *args)] = (fn, args, 1)
                    else:
                        failed.append((args, traceback.format_exc()))
                        with dog.lock:
                            dog.total -= 1
                with dog.lock:
                    dog.running = min(a.workers, len(futures))
                pd.DataFrame(rows).to_csv(out / f'{a.campaign}_cycles_partial.csv', index=False)
                break
    dog.stop.set()
    dog.emit()
    if a.campaign in ('full', 'spot', 'final') and rows:
        cyc = pd.DataFrame(rows).sort_values(['experiment', 'method', 'x', 'seed'])
        cyc['running_mean'] = cyc.groupby(['experiment', 'method', 'x']).value.transform(
            lambda v: v.expanding().mean())
        cyc.to_csv(out / 'cycles.csv', index=False)
        sb.summarise(cyc).to_csv(out / 'summary.csv', index=False)
    if a.campaign == 'sensitivity' and rows:
        df = pd.DataFrame(rows).sort_values(['param', 'value', 'seed'])
        for m in ('auc', 'seniority_bias', 'selfcite_inflation'):
            if m in df:
                df[m + '_running_mean'] = df.groupby(['param', 'value'])[m].transform(lambda v: v.expanding().mean())
        df.to_csv(out / 'sensitivity_cycles.csv', index=False)
        summarise(rows).to_csv(out / 'sensitivity_summary.csv', index=False)
    for args, tb in failed:
        print('FAILED', args, tb.splitlines()[-1])


if __name__ == '__main__':
    main()
