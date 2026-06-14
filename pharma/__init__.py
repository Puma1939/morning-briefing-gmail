"""Pharma Milano Intelligence - pacchetto di analisi territoriale.

Moduli:
    scoring     ricostruzione delle metriche e dei punteggi dai dati grezzi
    enrichment  schema e merge dei dati di arricchimento per farmacia
    financials  modulo commercialisti: bilancio vs potenziale territoriale
    schede      generazione delle schede per singola farmacia (HTML/PDF)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORT = ROOT / "report"
