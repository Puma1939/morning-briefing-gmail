"""Calcolo del termometro composito e della performance del basket.

Input: serie grezze (FRED + Stooq) gia scaricate da `data.py`.
Output: una struttura `Snapshot` con il punteggio 0-100, i sub-punteggi per
componente e la performance del basket long/short su piu orizzonti.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import config
from .data import fetch_one, stooq_prices
from .sentiment import load_sentiment


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _scale(value: float, lo: float, hi: float) -> float:
    """Mappa `value` da [lo, hi] a [0, 100]. Gestisce anche lo > hi (invertito)."""
    if hi == lo:
        return 0.0
    return round(_clip01((value - lo) / (hi - lo)) * 100, 1)


def _subscore(comp: dict, series: pd.Series) -> tuple[float, float]:
    """Restituisce (sub_punteggio_0_100, valore_osservato_grezzo)."""
    kind = comp["kind"]
    s = series.dropna()
    if s.empty:
        raise ValueError(f"serie vuota per componente {comp['key']}")
    last = float(s.iloc[-1])

    if kind == "level_band":
        return _scale(last, comp["lo"], comp["hi"]), last

    window = s[s.index >= s.index[-1] - pd.Timedelta(days=372)]  # ~52 settimane
    if kind == "pct_from_low":
        low = float(window.min())
        pct = (last - low) / low * 100 if low else 0.0
        return _scale(pct, comp["lo"], comp["hi"]), pct
    if kind in ("drawdown", "ratio_drawdown"):
        high = float(window.max())
        dd = (high - last) / high * 100 if high else 0.0  # positivo = quanto sotto il massimo
        return _scale(dd, comp["lo"], comp["hi"]), dd
    raise ValueError(f"kind sconosciuto: {kind}")


@dataclass
class Component:
    key: str
    label: str
    desc: str
    weight: float
    subscore: float
    observed: float


@dataclass
class BasketLeg:
    ticker: str
    name: str
    returns: dict  # orizzonte -> rendimento %


@dataclass
class Snapshot:
    asof: str
    composite: float
    regime: str
    regime_color: str
    components: list[Component] = field(default_factory=list)
    long_legs: list[BasketLeg] = field(default_factory=list)
    short_legs: list[BasketLeg] = field(default_factory=list)
    spread: dict = field(default_factory=dict)  # orizzonte -> spread % (long - short)
    sentiment: dict | None = None  # dettaglio del layer Bigdata.com (temi + evidenze), se presente

    def history_row(self) -> dict:
        row = {"date": self.asof, "composite": self.composite, "regime": self.regime}
        for c in self.components:
            row[f"sub_{c.key}"] = c.subscore
        for h, v in self.spread.items():
            row[f"basket_{h}"] = v
        return row


def _returns(prices: pd.Series) -> dict:
    """Rendimenti % su ciascun orizzonte di config.HORIZONS."""
    prices = prices.dropna()
    last = float(prices.iloc[-1])
    out = {}
    for h, ndays in config.HORIZONS.items():
        if h == "YTD":
            year = prices.index[-1].year
            ytd = prices[prices.index >= f"{year}-01-01"]
            base = float(ytd.iloc[0]) if len(ytd) else last
        elif len(prices) > ndays:
            base = float(prices.iloc[-1 - ndays])
        else:
            base = float(prices.iloc[0])
        out[h] = round((last / base - 1) * 100, 2) if base else 0.0
    return out


def build_snapshot(
    cache_dir: Path | None = None,
    raw: dict | None = None,
    sentiment_path: Path | str | None = None,
    include_sentiment: bool = True,
) -> Snapshot:
    """Costruisce lo snapshot. Se `raw` e fornito (dict di Series), usa quello e
    salta la rete: utile per test/demo. Altrimenti scarica tutto via data.py.

    Il 7o componente "narrativa AI-crisis" (Bigdata.com) viene aggiunto se
    `include_sentiment` e True e il file `sentiment_path` (default
    `config.SENTIMENT_FILE`) esiste ed e recente; in demo/test puo essere passato
    come numero 0-100 in `raw["sentiment"]`. Il composito e la media pesata
    rinormalizzata sui componenti effettivamente presenti, cosi l'assenza di una
    fonte (sentiment o una serie) non sballa la scala."""

    def get_component_series(comp: dict) -> pd.Series:
        if raw is not None and comp["key"] in raw:
            return raw[comp["key"]]
        return fetch_one(comp["source"], cache_dir)

    def get_prices(ticker: str) -> pd.Series:
        if raw is not None and ticker in raw:
            return raw[ticker]
        return stooq_prices(ticker, cache_dir)

    # --- componenti ---
    components: list[Component] = []
    asof_dates = []
    for comp in config.COMPONENTS:
        series = get_component_series(comp)
        sub, obs = _subscore(comp, series)
        components.append(
            Component(comp["key"], comp["label"], comp["desc"], comp["weight"], sub, obs)
        )
        asof_dates.append(series.index[-1])

    # --- 7o componente: narrativa AI-crisis (Bigdata.com) ---
    sentiment_detail: dict | None = None
    sc = config.SENTIMENT
    if raw is not None and "sentiment" in raw:
        val = float(raw["sentiment"])
        components.append(Component(sc["key"], sc["label"], sc["desc"], sc["weight"], val, val))
    elif include_sentiment:
        loaded = load_sentiment(
            sentiment_path or config.SENTIMENT_FILE, max_age_days=sc["max_age_days"]
        )
        if loaded is not None:
            val = loaded["subscore"]
            components.append(Component(sc["key"], sc["label"], sc["desc"], sc["weight"], val, val))
            sentiment_detail = loaded

    # media pesata rinormalizzata sui componenti presenti (se tutti e 6 di mercato
    # ci sono e senza sentiment, i pesi sommano a 1.0 -> identico a prima)
    tot_w = sum(c.weight for c in components)
    composite = round(sum(c.subscore * c.weight for c in components) / tot_w, 1) if tot_w else 0.0
    regime, color = config.regime_for(composite)
    asof = max(asof_dates).strftime("%Y-%m-%d")

    # --- basket ---
    long_legs, short_legs = [], []
    long_ret_by_h: dict = {h: [] for h in config.HORIZONS}
    short_ret_by_h: dict = {h: [] for h in config.HORIZONS}

    for ticker, (stooq_t, name) in config.BASKET_LONG.items():
        r = _returns(get_prices(stooq_t))
        long_legs.append(BasketLeg(ticker, name, r))
        for h, v in r.items():
            long_ret_by_h[h].append(v)
    for ticker, (stooq_t, name) in config.BASKET_SHORT.items():
        r = _returns(get_prices(stooq_t))
        short_legs.append(BasketLeg(ticker, name, r))
        for h, v in r.items():
            short_ret_by_h[h].append(v)

    spread = {}
    for h in config.HORIZONS:
        lmean = sum(long_ret_by_h[h]) / len(long_ret_by_h[h])
        smean = sum(short_ret_by_h[h]) / len(short_ret_by_h[h])
        spread[h] = round(lmean - smean, 2)

    return Snapshot(
        asof=asof,
        composite=composite,
        regime=regime,
        regime_color=color,
        components=components,
        long_legs=long_legs,
        short_legs=short_legs,
        spread=spread,
        sentiment=sentiment_detail,
    )
