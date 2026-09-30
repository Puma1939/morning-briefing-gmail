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
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

# La API ufficiale FRED (api.stlouisfed.org) e un servizio distinto dal server
# dei grafici (fred.stlouisfed.org): quest'ultimo tende a stallare dagli IP dei
# runner CI. Se e presente una API key (env FRED_API_KEY) la usiamo come sorgente
# primaria; altrimenti si ripiega sull'endpoint CSV pubblico dei grafici.
FRED_API = (
    "https://api.stlouisfed.org/fred/series/observations"
    "?series_id={sid}&api_key={key}&file_type=json"
)
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
STOOQ_CSV = "https://stooq.com/q/d/l/?s={ticker}&i=d"

_UA = "Mozilla/5.0 (compatible; citrini-doomsday/1.0)"

# Le fonti gratuite (FRED/Stooq) possono rispondere lentamente o resettare la
# connessione, soprattutto dagli IP di CI. Un timeout piu ampio e qualche
# tentativo con backoff rendono il fetch robusto a intoppi temporanei.
_TIMEOUT = 60
_RETRIES = 4
_BACKOFF = 3.0


def _get(url: str, timeout: int = _TIMEOUT, retries: int = _RETRIES) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(_BACKOFF * (2 ** attempt))
    raise last_exc  # type: ignore[misc]


def _cache_path(cache_dir: Path | None, name: str) -> Path | None:
    if cache_dir is None:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{name}.csv"


def _fred_api_csv(sid: str) -> str:
    """Scarica la serie dalla API ufficiale FRED e la restituisce in formato
    CSV "DATE,<sid>" (stesso formato del server dei grafici), cosi il resto
    del codice e la cache restano invariati. Richiede env FRED_API_KEY."""
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise RuntimeError("FRED_API_KEY non impostata")
    raw = _get(FRED_API.format(sid=urllib.parse.quote(sid), key=urllib.parse.quote(key)))
    obs = json.loads(raw).get("observations", [])
    lines = [f"DATE,{sid}"]
    for o in obs:
        lines.append(f"{o.get('date', '')},{o.get('value', '.')}")
    return "\n".join(lines) + "\n"


def fred_series(sid: str, cache_dir: Path | None = None) -> pd.Series:
    """Serie FRED come Series(float) indicizzata per data.

    Ordine delle sorgenti: (1) API ufficiale FRED se FRED_API_KEY e presente,
    (2) endpoint CSV pubblico dei grafici, (3) cache locale se disponibile.
    """
    cp = _cache_path(cache_dir, f"fred_{sid}")
    text = None
    for fetch in (_fred_api_csv, lambda s=sid: _get(FRED_CSV.format(sid=s))):
        try:
            text = fetch(sid) if fetch is _fred_api_csv else fetch()
            break
        except Exception:
            continue
    if text is not None:
        if cp is not None:
            cp.write_text(text, encoding="utf-8")
    elif cp is not None and cp.exists():
        text = cp.read_text(encoding="utf-8")
    else:
        raise RuntimeError(f"impossibile scaricare la serie FRED '{sid}' (API/CSV falliti, nessuna cache)")
    df = pd.read_csv(io.StringIO(text))
    # formato "DATE" + colonna omonima alla serie; i missing sono "."
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
