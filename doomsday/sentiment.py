"""Componente qualitativo "narrativa AI-crisis" da Bigdata.com.

A differenza dei 6 componenti di mercato (FRED + Stooq, vedi `config.py`),
questo sub-punteggio 0-100 non si ricava da una serie storica ma dal sentiment
di news / filing / transcript sulla catena della tesi Citrini, interrogati sul
connettore Bigdata.com (https://bigdata.com):

    lavoro sostituito dall'AI -> layoff nel software -> stress sul private credit
    -> debolezza di pagamenti e logistica/consumi.

Il connettore Bigdata.com vive nella sessione Claude e NON e richiamabile dallo
script Python della pipeline (GitHub Actions). Per questo il valore viene
calcolato da una sessione Claude e salvato in `doomsday/sentiment.json`, che la
pipeline legge. Se il file manca o e piu vecchio di `max_age_days`, il componente
viene semplicemente escluso e il termometro si rinormalizza sui componenti
rimasti (vedi `indicator.build_snapshot`).

Rigenerazione: `python scripts/refresh_sentiment.py` (documenta le query e
ricalcola il sub-punteggio dai temi).
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path


def composite_from_themes(themes: list[dict]) -> float:
    """Media pesata (0-100) dei punteggi per tema. I pesi non devono sommare a 1:
    la media si rinormalizza sul totale dei pesi presenti."""
    tot_w = sum(float(t.get("weight", 0)) for t in themes)
    if tot_w <= 0:
        return 0.0
    s = sum(float(t["score"]) * float(t["weight"]) for t in themes)
    return round(s / tot_w, 1)


def _parse_asof(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def load_sentiment(
    path: Path | str,
    *,
    max_age_days: int = 14,
    today: date | None = None,
) -> dict | None:
    """Carica `sentiment.json` e ne restituisce una struttura normalizzata:

        {"subscore": float, "asof": str, "age_days": int, "themes": [...],
         "source": str, "window_days": int}

    Ricalcola sempre `subscore` dai temi (il valore salvato e solo informativo).
    Restituisce `None` se il file manca, e illeggibile, non ha temi, o e piu
    vecchio di `max_age_days` (dato obsoleto: meglio escludere il componente che
    pesare una narrativa vecchia)."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    themes = data.get("themes") or []
    if not themes:
        return None

    asof = _parse_asof(data.get("asof", ""))
    today = today or date.today()
    age_days = (today - asof).days if asof else None
    if age_days is None or age_days < 0 or age_days > max_age_days:
        return None

    return {
        "subscore": composite_from_themes(themes),
        "asof": data.get("asof"),
        "age_days": age_days,
        "themes": themes,
        "source": data.get("source", "Bigdata.com"),
        "window_days": data.get("window_days"),
        "note": data.get("note"),
    }
