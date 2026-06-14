"""Arricchimento delle schede farmacia.

Gli open data non contengono orari, servizi, recensioni, sito o presenza social:
questi attributi vanno raccolti da fonti esterne (Google Places, siti, social) o
a mano. Questo modulo definisce lo schema, carica il file di arricchimento e lo
unisce all'anagrafica, calcolando un indice di completezza per ogni farmacia.
"""
from __future__ import annotations

import pandas as pd

# schema: campo -> tipo logico ("bool", "list" pipe-separated, "num", "text")
ENRICHMENT_SCHEMA: dict[str, str] = {
    "codice_farmacia": "key",
    "catena": "text",            # Indipendente / LloydsFarmacia / Comunale / ...
    "orari": "text",             # es. "Lun-Ven 8:30-19:30; Sab 9-13"
    "aperta_24h": "bool",
    "servizi": "list",           # "autoanalisi|ECG|holter|CUP|noleggio"
    "sito_web": "text",
    "ecommerce": "bool",
    "consegna_domicilio": "bool",
    "telemedicina": "bool",
    "cup": "bool",               # prenotazioni SSN
    "dermocosmesi": "bool",
    "instagram": "text",
    "facebook": "text",
    "recensioni_n": "num",
    "rating": "num",
}

# campi che concorrono all'indice di completezza
COMPLETENESS_FIELDS = [c for c in ENRICHMENT_SCHEMA if c != "codice_farmacia"]


def empty_enrichment(codici: pd.Series) -> pd.DataFrame:
    """Schema vuoto pronto da popolare, una riga per farmacia."""
    df = pd.DataFrame({"codice_farmacia": codici.values})
    for col in COMPLETENESS_FIELDS:
        df[col] = pd.NA
    return df


def load_enrichment(path, codici: pd.Series) -> pd.DataFrame:
    """Carica l'arricchimento e lo riallinea a tutte le farmacie note.

    Le farmacie senza riga di arricchimento restano con campi vuoti.
    """
    try:
        e = pd.read_csv(path, dtype={"codice_farmacia": str})
    except FileNotFoundError:
        e = empty_enrichment(codici)
    base = pd.DataFrame({"codice_farmacia": codici.astype(str).values})
    merged = base.merge(e, on="codice_farmacia", how="left")
    for col in COMPLETENESS_FIELDS:
        if col not in merged.columns:
            merged[col] = pd.NA
    merged["completezza_pct"] = _completeness(merged)
    return merged


def _completeness(df: pd.DataFrame) -> pd.Series:
    filled = df[COMPLETENESS_FIELDS].notna().sum(axis=1)
    return (filled / len(COMPLETENESS_FIELDS) * 100).round(0)


def is_true(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "si", "sì", "yes", "x", "vero"}


def as_list(value) -> list[str]:
    if pd.isna(value) or str(value).strip() == "":
        return []
    return [v.strip() for v in str(value).split("|") if v.strip()]
