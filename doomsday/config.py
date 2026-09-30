"""Assunzioni dichiarate del Citrini Doomsday Scenario.

Tutto cio che e una scelta (proxy, pesi, soglie, composizione del basket) sta
qui, in chiaro, per poter essere discusso e ritarato senza toccare la logica.
Nessuna di queste serie richiede API key: FRED espone i CSV via fredgraph,
Stooq espone i prezzi giornalieri via download diretto.

LA TESI (Citrini Research, "2028 Global Intelligence Crisis", feb 2026)
    AI -> sostituzione del lavoro -> disoccupazione -> crollo consumi ->
    impairment dei redditi -> stress su mutui e credito privato -> recessione
    e drawdown azionario paragonabile alla GFC (~-57%, S&P verso ~3500).
    Settori vulnerabili segnalati nel memo: software dipendente da lavoro
    custom, payment processor, private credit/assicurazioni, logistica/delivery.

Il termometro 0-100 misura QUANTO i dati stanno gia confermando questa catena.
0 = nessun segnale, 100 = scenario in pieno svolgimento.
"""
from __future__ import annotations

# --------------------------------------------------------------------------- #
# Componenti del termometro composito                                         #
# --------------------------------------------------------------------------- #
# Ogni componente produce un sub-punteggio 0-100 (100 = massimo "doom") a
# partire da una serie osservabile. `kind` dice a indicator.py come mappare la
# serie sul sub-punteggio:
#   level_band   -> il livello assoluto della serie, scalato tra lo (=0) e hi (=100)
#   pct_from_low -> distanza % dal minimo a 52 settimane (per serie "che salgono = doom")
#   drawdown     -> drawdown % dal massimo a 52 settimane (per prezzi "che scendono = doom")
#   ratio_drawdown -> drawdown del rapporto fra due prezzi (ciclici/difensivi)
#
# I pesi sommano a 1.0.
COMPONENTS = [
    {
        "key": "labor",
        "label": "Deterioramento del lavoro",
        "desc": "Richieste iniziali di sussidio (proxy timely dello shock occupazionale da AI).",
        "weight": 0.20,
        "kind": "pct_from_low",
        "source": ("fred", "ICSA"),     # Initial Claims, settimanale
        "lo": 0.0,                       # 0% sopra il minimo 52w -> 0
        "hi": 60.0,                      # +60% sopra il minimo 52w -> 100
    },
    {
        "key": "credit",
        "label": "Stress sul credito",
        "desc": "High Yield OAS (fragilita del credito privato e dei bilanci leva).",
        "weight": 0.20,
        "kind": "level_band",
        "source": ("fred", "BAMLH0A0HYM2"),  # ICE BofA US HY OAS, %
        "lo": 3.0,                       # spread 3% -> 0
        "hi": 9.0,                       # spread 9% -> 100 (territorio recessivo)
    },
    {
        "key": "equity",
        "label": "Drawdown azionario",
        "desc": "Drawdown dell'S&P 500 dal massimo 52w (il memo punta a ~-57%).",
        "weight": 0.20,
        "kind": "drawdown",
        "source": ("stooq", "^spx"),
        "lo": 0.0,                       # nessun drawdown -> 0
        "hi": 40.0,                      # -40% -> 100
    },
    {
        "key": "vol",
        "label": "Paura / volatilita",
        "desc": "VIX (premio per il rischio di coda).",
        "weight": 0.15,
        "kind": "level_band",
        "source": ("stooq", "^vix"),
        "lo": 14.0,                      # VIX 14 -> 0
        "hi": 45.0,                      # VIX 45 -> 100
    },
    {
        "key": "curve",
        "label": "Segnale di recessione (curva)",
        "desc": "Spread 10y-2y: la ri-inclinazione da inversione profonda precede le recessioni.",
        "weight": 0.10,
        "kind": "level_band",
        "source": ("fred", "T10Y2Y"),
        "lo": 1.50,                      # curva ripida +150bp -> 0
        "hi": -0.50,                     # invertita -50bp -> 100 (lo>hi: invertito)
    },
    {
        "key": "cyclical",
        "label": "Debolezza dei consumi",
        "desc": "Discrezionali vs difensivi (XLY/XLP): rotazione difensiva = stress.",
        "weight": 0.15,
        "kind": "ratio_drawdown",
        "source": ("stooq", "xly.us", "xlp.us"),
        "lo": 0.0,
        "hi": 18.0,                      # -18% sul rapporto -> 100
    },
]

# --------------------------------------------------------------------------- #
# Il basket "Doomsday trade" (long difensivi / short vulnerabili)             #
# --------------------------------------------------------------------------- #
# Esprime la tesi come spread: se lo scenario si materializza, il leg LONG
# (rifugi) batte il leg SHORT (settori vulnerabili) e lo spread va in positivo.
# Performance dello spread = media(LONG) - media(SHORT).
BASKET_LONG = {
    "GLD": ("gld.us", "Oro"),
    "TLT": ("tlt.us", "Treasury lunghi"),
    "XLU": ("xlu.us", "Utility"),
    "XLP": ("xlp.us", "Beni di prima necessita"),
}
BASKET_SHORT = {
    "IGV": ("igv.us", "Software"),
    "BIZD": ("bizd.us", "Private credit (BDC)"),
    "KRE": ("kre.us", "Banche regionali"),
    "XRT": ("xrt.us", "Retail"),
    "IYT": ("iyt.us", "Trasporti / logistica"),
}

# Orizzonti (in giorni di borsa ~) per la performance del basket.
HORIZONS = {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "YTD": None}

# --------------------------------------------------------------------------- #
# Soglie di regime sul punteggio composito                                    #
# --------------------------------------------------------------------------- #
REGIMES = [
    (0, 20, "Quiescente", "#2Fae7d"),
    (20, 40, "Sorvegliato", "#7FB069"),
    (40, 60, "Elevato", "#E0B23A"),
    (60, 80, "Critico", "#E0703A"),
    (80, 101, "Doomsday in corso", "#C03A2B"),
]


def regime_for(score: float) -> tuple[str, str]:
    """Restituisce (etichetta, colore) per un punteggio composito."""
    for lo, hi, label, color in REGIMES:
        if lo <= score < hi:
            return label, color
    return REGIMES[-1][2], REGIMES[-1][3]
