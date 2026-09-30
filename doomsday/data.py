"""Fetch dei dati grezzi da fonti gratuite e senza API key.

FRED  -> https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIE>
Stooq -> https://stooq.com/q/d/l/?s=<ticker>&i=d   (CSV giornaliero OHLC)

Tutte le serie vengono restituite come `pandas.Series` indicizzate per data
(ascendente, NaN rimossi). Nessuna dipendenza oltre a pandas/stdlib.

In CI la rete e aperta e il fetch reale funziona. In ambienti con egress
ristretto si puo passare `cache_dir`: le serie vengono lette/scritte da CSV
locali cosi la pipeline resta riproducibile offline.
"""
from __future__ import annotations

import io
import urllib.request
from pathlib import Path

import pandas as pd

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
STOOQ_CSV = "https://stooq.com/q/d/l/?s={ticker}&i=d"

_UA = "Mozilla/5.0 (compatible; citrini-doomsday/1.0)"


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _cache_path(cache_dir: Path | None, name: str) -> Path | None:
    if cache_dir is None:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{name}.csv"


def fred_series(sid: str, cache_dir: Path | None = None) -> pd.Series:
    """Serie FRED come Series(float) indicizzata per data."""
    cp = _cache_path(cache_dir, f"fred_{sid}")
    try:
        text = _get(FRED_CSV.format(sid=sid))
        if cp is not None:
            cp.write_text(text, encoding="utf-8")
    except Exception:
        if cp is not None and cp.exists():
            text = cp.read_text(encoding="utf-8")
        else:
            raise
    df = pd.read_csv(io.StringIO(text))
    # fredgraph usa "DATE" + colonna omonima alla serie; i missing sono "."
    date_col = df.columns[0]
    val_col = df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    s = pd.to_numeric(df[val_col], errors="coerce")
    s.index = df[date_col]
    return s.dropna().sort_index()


def stooq_prices(ticker: str, cache_dir: Path | None = None) -> pd.Series:
    """Prezzo di chiusura giornaliero (Close) come Series indicizzata per data."""
    cp = _cache_path(cache_dir, f"stooq_{ticker.replace('^', '_').replace('.', '_')}")
    try:
        text = _get(STOOQ_CSV.format(ticker=ticker))
        if cp is not None and "Date,Open" in text:
            cp.write_text(text, encoding="utf-8")
    except Exception:
        if cp is not None and cp.exists():
            text = cp.read_text(encoding="utf-8")
        else:
            raise
    if "Date,Open" not in text:  # Stooq risponde "N/A" su ticker sconosciuti/limiti
        raise ValueError(f"Stooq: risposta non valida per '{ticker}': {text[:80]!r}")
    df = pd.read_csv(io.StringIO(text))
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    s = pd.to_numeric(df["Close"], errors="coerce")
    s.index = df["Date"]
    return s.dropna().sort_index()


def fetch_one(source: tuple, cache_dir: Path | None = None) -> pd.Series:
    """Risolve una tupla `source` di config in una Series.

    ("fred", "ICSA")            -> serie FRED
    ("stooq", "^spx")           -> prezzi Stooq
    ("stooq", "xly.us", "xlp.us") -> rapporto fra due prezzi Stooq
    """
    kind = source[0]
    if kind == "fred":
        return fred_series(source[1], cache_dir)
    if kind == "stooq":
        if len(source) == 3:  # rapporto
            num = stooq_prices(source[1], cache_dir)
            den = stooq_prices(source[2], cache_dir)
            joined = pd.concat({"num": num, "den": den}, axis=1).dropna()
            return (joined["num"] / joined["den"]).sort_index()
        return stooq_prices(source[1], cache_dir)
    raise ValueError(f"sorgente sconosciuta: {source!r}")
