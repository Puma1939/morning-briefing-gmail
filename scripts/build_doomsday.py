#!/usr/bin/env python3
"""Citrini Doomsday Scenario - pipeline settimanale.

Scarica i dati (FRED + Stooq), calcola il termometro composito 0-100 e la
performance del basket long/short, storicizza il valore in un CSV e genera il
report HTML autoconsistente + gli artefatti per l'email.

Uso:
    python scripts/build_doomsday.py            # fetch reale (serve rete: CI ok)
    python scripts/build_doomsday.py --cache data/doomsday_cache   # cache offline
    python scripts/build_doomsday.py --demo     # dati sintetici, nessuna rete (test)

Output:
    report/citrini_doomsday.html        report completo
    report/citrini_doomsday_summary.txt riga di sintesi (oggetto email)
    data/doomsday_history.csv           storico settimanale (append, dedup per data)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from doomsday import DATA, REPORT, config
from doomsday.indicator import build_snapshot
from doomsday.report import build_html

HISTORY = DATA / "doomsday_history.csv"
REPORT_HTML = REPORT / "citrini_doomsday.html"
SUMMARY_TXT = REPORT / "citrini_doomsday_summary.txt"


def _demo_raw() -> dict:
    """Serie sintetiche plausibili per validare calcolo e report senza rete."""
    import numpy as np

    rng = np.random.default_rng(42)
    days = pd.bdate_range(end="2026-06-26", periods=320)
    weeks = pd.date_range(end="2026-06-26", periods=80, freq="W-FRI")

    def walk(start, drift, vol, idx):
        steps = rng.normal(drift, vol, len(idx))
        return pd.Series(start * np.exp(np.cumsum(steps)), index=idx)

    raw = {
        # componenti
        "labor": walk(230_000, 0.0015, 0.01, weeks),       # initial claims, in salita
        "credit": pd.Series(3.5 + np.linspace(0, 2.0, len(weeks)) + rng.normal(0, 0.1, len(weeks)), index=weeks),
        "equity": walk(5800, -0.0008, 0.011, days),        # S&P in lieve drawdown
        "vol": pd.Series(18 + np.abs(rng.normal(0, 6, len(days))).cumsum() / 40, index=days),
        "curve": pd.Series(np.linspace(-0.3, 0.4, len(days)) + rng.normal(0, 0.03, len(days)), index=days),
    }
    # cyclical = rapporto XLY/XLP via raw dei due ticker
    raw["xly.us"] = walk(190, -0.0004, 0.009, days)
    raw["xlp.us"] = walk(78, 0.0003, 0.005, days)
    raw["cyclical"] = (raw["xly.us"] / raw["xlp.us"]).dropna()
    # basket: una serie sintetica per ogni ticker (long e short)
    for _t, (stooq_t, _name) in {**config.BASKET_LONG, **config.BASKET_SHORT}.items():
        raw[stooq_t] = walk(100, rng.normal(0, 0.0004), 0.01, days)
    return raw


def append_history(snap) -> pd.DataFrame:
    row = snap.history_row()
    if HISTORY.exists():
        hist = pd.read_csv(HISTORY)
        hist = hist[hist["date"] != row["date"]]  # dedup: una riga per data
        hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
    else:
        hist = pd.DataFrame([row])
    hist = hist.sort_values("date").reset_index(drop=True)
    hist.to_csv(HISTORY, index=False)
    return hist


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="usa dati sintetici (nessuna rete)")
    ap.add_argument("--cache", type=str, default=None, help="directory di cache per il fetch offline")
    args = ap.parse_args()

    cache_dir = Path(args.cache) if args.cache else None
    raw = _demo_raw() if args.demo else None

    snap = build_snapshot(cache_dir=cache_dir, raw=raw)
    hist = append_history(snap)

    html = build_html(snap, history=hist)
    REPORT.mkdir(parents=True, exist_ok=True)
    REPORT_HTML.write_text(html, encoding="utf-8")

    summary = (
        f"Citrini Doomsday {snap.composite:.0f}/100 ({snap.regime}) · "
        f"basket 1m {snap.spread['1m']:+.1f}% · dati al {snap.asof}"
    )
    SUMMARY_TXT.write_text(summary, encoding="utf-8")

    print("OK -", summary)
    print("    report:", REPORT_HTML.relative_to(REPORT.parent))
    print("    storico:", HISTORY.relative_to(REPORT.parent), f"({len(hist)} righe)")


if __name__ == "__main__":
    main()
