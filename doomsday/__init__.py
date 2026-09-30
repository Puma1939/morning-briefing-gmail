"""Citrini Doomsday Scenario - indicatore macro + basket.

Traccia, con cadenza settimanale, quanto i mercati stiano prezzando la tesi
"AI Doomsday / 2028 Global Intelligence Crisis" di Citrini Research (febbraio
2026): l'AI sostituisce il lavoro umano -> disoccupazione -> crollo dei consumi
-> crisi del credito privato -> recessione e drawdown azionario da GFC.

Moduli:
    config      assunzioni dichiarate: serie FRED, ticker del basket, pesi, soglie
    data        fetch da fonti gratuite senza API key (FRED CSV + Stooq)
    indicator   termometro composito 0-100 + performance del basket long/short
    report      report HTML autoconsistente (grafici in base64)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
REPORT = ROOT / "report"
