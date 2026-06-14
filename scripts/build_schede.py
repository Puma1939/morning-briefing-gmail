#!/usr/bin/env python3
"""Genera le schede per singola farmacia (territorio + arricchimento + bilancio).

Uso:
    python scripts/build_schede.py [CODICE ...]

Senza argomenti genera le schede per tutte le farmacie con dati di arricchimento.
Output in report/schede/ (HTML e, se weasyprint e installato, PDF).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pharma import DATA, REPORT, enrichment as enr, financials as fin, schede


def main(argv: list[str]) -> None:
    farmacie = pd.read_csv(DATA / "farmacie.csv")
    farmacie["CODICE_FARMACIA"] = farmacie["CODICE_FARMACIA"].astype(str)

    enrichment = enr.load_enrichment(DATA / "enrichment_farmacie.csv", farmacie["CODICE_FARMACIA"])

    fin_path = DATA / "financials_farmacie.csv"
    financials_computed = None
    if fin_path.exists():
        financials_computed = fin.compute(fin.load_financials(fin_path), farmacie)

    codici = argv or None
    out = schede.build_all(
        farmacie, enrichment, financials_computed, REPORT / "schede", codici=codici
    )
    print(f"OK - {len(out)} schede generate in {(REPORT / 'schede').relative_to(REPORT.parent)}/")
    for p in out:
        print(f"     {p.name}")


if __name__ == "__main__":
    main(sys.argv[1:])
