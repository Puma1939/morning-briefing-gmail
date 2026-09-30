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
# Yahoo Finance come fallback ai prezzi: Stooq dai runner CI a volte risponde con
# una pagina HTML (rate-limit/robots) invece del CSV. Yahoo non richiede API key.
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=2y"

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


def _stooq_to_yahoo(ticker: str) -> str:
    """Converte un ticker Stooq nel simbolo Yahoo corrispondente.

    "^spx" -> "^GSPC", "^vix" -> "^VIX", "gld.us" -> "GLD", "xly.us" -> "XLY".
    """
    t = ticker.lower()
    special = {"^spx": "^GSPC", "^vix": "^VIX", "^ndx": "^NDX", "^dji": "^DJI"}
    if t in special:
        return special[t]
    if t.endswith(".us"):
        return ticker[:-3].upper()
    return ticker.upper()


def _yahoo_prices(ticker: str) -> pd.Series:
    """Chiusure giornaliere da Yahoo Finance come Series indicizzata per data."""
    sym = _stooq_to_yahoo(ticker)
    raw = _get(YAHOO_CHART.format(sym=urllib.parse.quote(sym)))
    result = json.loads(raw)["chart"]["result"][0]
    ts = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    s = pd.Series(closes, index=pd.to_datetime(ts, unit="s").normalize())
    s = pd.to_numeric(s, errors="coerce").dropna().sort_index()
    if s.empty:
        raise ValueError(f"Yahoo: nessun dato per '{sym}'")
    return s


def stooq_prices(ticker: str, cache_dir: Path | None = None) -> pd.Series:
    """Chiusura giornaliera come Series indicizzata per data.

    Sorgenti in ordine: (1) Stooq CSV; (2) Yahoo Finance se Stooq fallisce o
    risponde con una pagina non valida (HTML/rate-limit); (3) cache locale.
    """
    cp = _cache_path(cache_dir, f"stooq_{ticker.replace('^', '_').replace('.', '_')}")

    # (1) Stooq
    try:
        text = _get(STOOQ_CSV.format(ticker=ticker))
        if "Date,Open" in text:
            if cp is not None:
                cp.write_text(text, encoding="utf-8")
            df = pd.read_csv(io.StringIO(text))
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            s = pd.to_numeric(df["Close"], errors="coerce")
            s.index = df["Date"]
            return s.dropna().sort_index()
    except Exception:
        pass

    # (2) Yahoo Finance
    try:
        s = _yahoo_prices(ticker)
        if cp is not None:
            cp.write_text("Date,Close\n" + "\n".join(f"{d:%Y-%m-%d},{v}" for d, v in s.items()) + "\n", encoding="utf-8")
        return s
    except Exception:
        pass

    # (3) cache locale
    if cp is not None and cp.exists():
        df = pd.read_csv(io.StringIO(cp.read_text(encoding="utf-8")))
        close_col = "Close" if "Close" in df.columns else df.columns[-1]
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        s = pd.to_numeric(df[close_col], errors="coerce")
        s.index = df["Date"]
        return s.dropna().sort_index()
    raise ValueError(f"impossibile scaricare i prezzi per '{ticker}' (Stooq/Yahoo falliti, nessuna cache)")


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
