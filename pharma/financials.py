"""Modulo commercialisti: bilancio vs potenziale territoriale.

I dati di bilancio sono privati e non presenti negli open data: vanno inseriti
dal consulente nel file `data/financials_farmacie.csv` (template). Il modulo
incrocia il bilancio con il potenziale territoriale del NIL per dire se una
farmacia rende sopra o sotto le attese della sua zona, e confronta i margini
con benchmark di settore.

ATTENZIONE: i parametri sotto sono assunzioni dichiarate, da tarare sui dati
reali del cliente o su fonti di settore (Federfarma, bilanci aggregati).
"""
from __future__ import annotations

import pandas as pd

# --- assunzioni dichiarate (da tarare) ---
SPESA_PROCAPITE_ANNUA = 450.0      # euro/anno per residente nel canale farmacia (pubblico + privato)
MOLTIPLICATORE_SENIOR = 2.2        # gli over 65 spendono ~2.2x la media
# benchmark di settore (mediane indicative)
BENCH_MARGINE_LORDO_PCT = 28.0
BENCH_EBITDA_PCT = 7.0
BENCH_ROTAZIONE = 9.0

FINANCIALS_SCHEMA: dict[str, str] = {
    "codice_farmacia": "key",
    "anno": "num",
    "ricavi": "num",                 # euro
    "margine_lordo_pct": "num",      # % sui ricavi
    "costo_personale": "num",        # euro
    "rotazione_magazzino": "num",    # volte/anno
    "ebitda": "num",                 # euro
}


def template(codici: pd.Series, anno: int) -> pd.DataFrame:
    df = pd.DataFrame({"codice_farmacia": codici.astype(str).values})
    df["anno"] = anno
    for col in ["ricavi", "margine_lordo_pct", "costo_personale", "rotazione_magazzino", "ebitda"]:
        df[col] = pd.NA
    return df


def load_financials(path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"codice_farmacia": str})


def ricavi_attesi(pop_per_farmacia: float, quota_over65_pct: float) -> float:
    """Ricavi teorici dalla sola domanda territoriale del NIL.

    Pesa la popolazione per la maggiore spesa degli over 65.
    """
    q = quota_over65_pct / 100.0
    fattore_senior = 1 + q * (MOLTIPLICATORE_SENIOR - 1)
    return pop_per_farmacia * SPESA_PROCAPITE_ANNUA * fattore_senior


def _giudizio_potenziale(ratio: float) -> str:
    if pd.isna(ratio):
        return "dato mancante"
    if ratio < 0.85:
        return "sotto il potenziale della zona"
    if ratio > 1.15:
        return "sopra il potenziale della zona"
    return "in linea con il potenziale"


def compute(financials: pd.DataFrame, farmacie_scored: pd.DataFrame) -> pd.DataFrame:
    """Unisce bilancio e territorio e calcola gli indicatori del modulo.

    `farmacie_scored` deve contenere: CODICE_FARMACIA, pop_per_farmacia,
    quota_over65_pct, archetipo, opportunity_score.
    """
    terr = farmacie_scored.rename(columns={"CODICE_FARMACIA": "codice_farmacia"})[
        ["codice_farmacia", "DESCRIZIONE_FARMACIA", "NIL", "pop_per_farmacia",
         "quota_over65_pct", "archetipo", "opportunity_score"]
    ].copy()
    terr["codice_farmacia"] = terr["codice_farmacia"].astype(str)

    df = financials.merge(terr, on="codice_farmacia", how="left")
    df["ricavi_attesi"] = df.apply(
        lambda r: ricavi_attesi(r["pop_per_farmacia"], r["quota_over65_pct"]), axis=1
    )
    df["performance_ratio"] = df["ricavi"] / df["ricavi_attesi"]
    df["giudizio_potenziale"] = df["performance_ratio"].apply(_giudizio_potenziale)
    # nelle zone centrali ad alto flusso non residente (uffici, turismo, transiti)
    # il potenziale su base residenti sottostima la domanda reale: niente verdetto secco
    alto_flusso = df["archetipo"] == "Zona molto competitiva"
    df.loc[alto_flusso, "giudizio_potenziale"] = (
        "zona ad alto flusso non residente: potenziale su base residenti poco indicativo"
    )

    df["ebitda_pct"] = df["ebitda"] / df["ricavi"] * 100
    df["delta_margine_pp"] = df["margine_lordo_pct"] - BENCH_MARGINE_LORDO_PCT
    df["delta_ebitda_pp"] = df["ebitda_pct"] - BENCH_EBITDA_PCT
    df["delta_rotazione"] = df["rotazione_magazzino"] - BENCH_ROTAZIONE
    df["costo_personale_pct"] = df["costo_personale"] / df["ricavi"] * 100
    return df
