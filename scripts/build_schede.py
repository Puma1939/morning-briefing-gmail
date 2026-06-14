#!/usr/bin/env python3
"""Genera le schede per singola farmacia (territorio + arricchimento + bilancio).

Uso:
    python scripts/build_schede.py                  # solo farmacie arricchite (+PDF)
    python scripts/build_schede.py --all            # tutte le 422 farmacie (HTML)
    python scripts/build_schede.py --all --pdf      # tutte, anche in PDF (lento)
    python scripts/build_schede.py MI2052 MI1440    # solo alcune
    python scripts/build_schede.py --no-pdf         # niente PDF

Output in report/schede/ (HTML, PDF opzionale, e index.html navigabile).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pharma import DATA, REPORT, enrichment as enr, financials as fin, schede


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("codici", nargs="*", help="codici farmacia specifici")
    ap.add_argument("--all", action="store_true", help="genera per tutte le farmacie")
    pdf = ap.add_mutually_exclusive_group()
    pdf.add_argument("--pdf", dest="pdf", action="store_true", help="genera anche i PDF")
    pdf.add_argument("--no-pdf", dest="pdf", action="store_false", help="solo HTML")
    ap.set_defaults(pdf=None)
    args = ap.parse_args()

    farmacie = pd.read_csv(DATA / "farmacie.csv")
    farmacie["CODICE_FARMACIA"] = farmacie["CODICE_FARMACIA"].astype(str)

    enrichment = enr.load_enrichment(DATA / "enrichment_farmacie.csv", farmacie["CODICE_FARMACIA"])

    fin_path = DATA / "financials_farmacie.csv"
    financials_computed = None
    if fin_path.exists():
        financials_computed = fin.compute(fin.load_financials(fin_path), farmacie)

    if args.codici:
        codici = args.codici
    elif args.all:
        codici = farmacie["CODICE_FARMACIA"].tolist()
    else:
        codici = enrichment.loc[enrichment["completezza_pct"] > 0, "codice_farmacia"].tolist()

    # PDF: default sì per pochi, no quando si generano tutte (sarebbe lento e pesante)
    want_pdf = args.pdf if args.pdf is not None else (not args.all)

    out_dir = REPORT / "schede"
    written = schede.build_all(
        farmacie, enrichment, financials_computed, out_dir, codici=codici, pdf=want_pdf
    )
    index = schede.build_index(farmacie, [p.stem.replace("scheda_", "") for p in written], out_dir)
    print(f"OK - {len(written)} schede generate ({'con' if want_pdf else 'senza'} PDF)")
    print(f"     indice: {index.relative_to(REPORT.parent)}")


if __name__ == "__main__":
    main()
