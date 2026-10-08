"""Report HTML autoconsistente del Citrini Doomsday Scenario.

Grafici renderizzati con matplotlib e incorporati in base64, cosi l'HTML resta
visualizzabile anche spostato fuori dal repo (stesso approccio del report pharma).
"""
from __future__ import annotations

import base64
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config
from .indicator import Snapshot

# Palette coerente con il resto del progetto
INK = "#1F2430"
MUTED = "#6F768A"
GRID = "#E6E8F0"
ACCENT = "#2F6FED"
WARN = "#E0703A"
GOOD = "#2Fae7d"
BAD = "#C03A2B"
BRAND_RED = "#C0202B"  # brand Macro Grisa / bande di separazione
DARK_RED = "#8E1120"   # rosso scuro per il masthead (titolo + marchio)

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "figure.dpi": 130,
    }
)


def _b64(fig) -> str:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _gauge(snap: Snapshot) -> str:
    fig, ax = plt.subplots(figsize=(7.2, 4.0), subplot_kw={"aspect": "equal"})
    ax.axis("off")
    # archi colorati per regime sul semicerchio (180 -> 0 gradi)
    for lo, hi, _label, color in config.REGIMES:
        hi = min(hi, 100)
        a0 = 180 - lo / 100 * 180
        a1 = 180 - hi / 100 * 180
        theta = np.linspace(np.radians(a1), np.radians(a0), 60)
        ax.plot(np.cos(theta), np.sin(theta), lw=22, color=color, solid_capstyle="butt")
    # lancetta
    ang = np.radians(180 - snap.composite / 100 * 180)
    ax.plot([0, 0.82 * np.cos(ang)], [0, 0.82 * np.sin(ang)], lw=3.2, color=INK)
    ax.scatter([0], [0], s=120, color=INK, zorder=5)
    ax.text(0, -0.22, f"{snap.composite:.0f}", ha="center", fontsize=40, fontweight="bold", color=snap.regime_color)
    ax.text(0, -0.42, f"/ 100  ·  {snap.regime}", ha="center", fontsize=14, color=MUTED)
    ax.set_xlim(-1.15, 1.15)
    ax.set_ylim(-0.5, 1.15)
    return _b64(fig)


def _components_bar(snap: Snapshot) -> str:
    comps = sorted(snap.components, key=lambda c: c.subscore)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    colors = [config.regime_for(c.subscore)[1] for c in comps]
    ax.barh([c.label for c in comps], [c.subscore for c in comps], color=colors)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Sub-punteggio (0 = nessun segnale, 100 = massimo stress)")
    ax.set_title("Contributo per componente", loc="left", fontsize=14, color=INK)
    for y, c in enumerate(comps):
        ax.text(c.subscore + 1.5, y, f"{c.subscore:.0f}  ·  peso {c.weight:.0%}", va="center", fontsize=9, color=MUTED)
    ax.grid(axis="y", visible=False)
    return _b64(fig)


def _basket_bar(snap: Snapshot) -> str:
    horizons = list(config.HORIZONS.keys())
    vals = [snap.spread[h] for h in horizons]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    colors = [GOOD if v >= 0 else BAD for v in vals]
    ax.bar(horizons, vals, color=colors, width=0.6)
    ax.axhline(0, color=MUTED, lw=1)
    ax.set_ylabel("Spread % (LONG difensivi − SHORT vulnerabili)")
    ax.set_title("Performance del Doomsday trade", loc="left", fontsize=14, color=INK)
    for x, v in enumerate(vals):
        ax.text(x, v + (0.3 if v >= 0 else -0.3), f"{v:+.1f}%", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=10, color=INK)
    ax.grid(axis="x", visible=False)
    return _b64(fig)


def _history_line(history: pd.DataFrame | None) -> str | None:
    if history is None or len(history) < 2:
        return None
    h = history.copy()
    h["date"] = pd.to_datetime(h["date"], errors="coerce")
    h = h.dropna(subset=["date"]).sort_values("date")
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(h["date"], h["composite"], color=ACCENT, lw=2, marker="o", ms=3)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Termometro")
    ax.set_title("Storico del termometro", loc="left", fontsize=14, color=INK)
    for lo, hi, _l, color in config.REGIMES:
        ax.axhspan(lo, min(hi, 100), color=color, alpha=0.06)
    return _b64(fig)


def _legs_table(legs, horizons) -> str:
    head = "".join(f"<th>{h}</th>" for h in horizons)
    rows = []
    for leg in legs:
        cells = "".join(
            f'<td style="color:{GOOD if leg.returns[h] >= 0 else BAD}">{leg.returns[h]:+.1f}%</td>'
            for h in horizons
        )
        rows.append(f"<tr><td><strong>{leg.ticker}</strong> <small>{leg.name}</small></td>{cells}</tr>")
    return (
        f"<table><thead><tr><th>Strumento</th>{head}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _comp_table(snap: Snapshot) -> str:
    rows = []
    for c in snap.components:
        rows.append(
            f"<tr><td>{c.label}</td><td class='note'>{c.desc}</td>"
            f"<td>{c.observed:+.2f}</td><td>{c.weight:.0%}</td>"
            f"<td><strong>{c.subscore:.0f}</strong></td></tr>"
        )
    return (
        "<table><thead><tr><th>Componente</th><th>Cosa misura</th>"
        "<th>Valore osservato</th><th>Peso</th><th>Sub-punteggio</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _sentiment_block(snap: Snapshot) -> str:
    """Sezione dedicata al 7o componente (narrativa AI-crisis da Bigdata.com):
    breakdown per tema con punteggio, peso ed evidenze citate. Vuota se assente."""
    s = snap.sentiment
    if not s:
        return (
            '<h2>Narrativa AI-crisis (Bigdata.com)</h2>'
            '<p class="note">Layer sentiment non disponibile o obsoleto in questa esecuzione: '
            'il termometro e stato calcolato sui soli componenti di mercato. Rigenerare '
            '<code>doomsday/sentiment.json</code> con <code>scripts/refresh_sentiment.py</code>.</p>'
        )
    rows = []
    for t in s["themes"]:
        ev = "".join(
            f'<li><a href="{e["url"]}">{e["headline"]}</a> '
            f'<small>{e.get("source","")} · {e.get("date","")}</small></li>'
            for e in t.get("evidence", [])
        )
        ev_html = f"<ul class='ev'>{ev}</ul>" if ev else ""
        rows.append(
            f"<tr><td><strong>{t['label']}</strong>{ev_html}</td>"
            f"<td>{float(t['weight']):.0%}</td>"
            f"<td><strong>{float(t['score']):.0f}</strong></td></tr>"
        )
    age = s.get("age_days")
    age_txt = f" · dato di {age}g fa" if age is not None else ""
    return (
        '<h2>Narrativa AI-crisis (Bigdata.com)</h2>'
        f'<p>Sub-punteggio <strong>{s["subscore"]:.0f}/100</strong> dalla cronaca degli ultimi '
        f'{s.get("window_days","~30")} giorni (news, filing, transcript) interrogata su '
        f'<a href="https://bigdata.com">Bigdata.com</a>{age_txt}. Misura quanto la catena della '
        'tesi Citrini si stia materializzando nei fatti, non nei prezzi: utile quando i segnali di '
        'mercato sono ancora benigni ma la narrativa accelera.</p>'
        "<table><thead><tr><th>Tema</th><th>Peso</th><th>Punteggio</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def build_html(snap: Snapshot, history: pd.DataFrame | None = None) -> str:
    horizons = list(config.HORIZONS.keys())
    history_chart = _history_line(history)
    history_block = (
        f'<h2>Andamento nel tempo</h2><img src="{history_chart}" alt="Storico del termometro">'
        if history_chart else
        '<h2>Andamento nel tempo</h2><p class="note">Lo storico comparira dalla seconda '
        'esecuzione settimanale in poi (file <code>data/doomsday_history.csv</code>).</p>'
    )
    delta = ""
    if history is not None and len(history) >= 2:
        prev = float(history.sort_values("date")["composite"].iloc[-2])
        d = snap.composite - prev
        arrow = "▲" if d > 0 else ("▼" if d < 0 else "▬")
        delta = f'<span class="delta">{arrow} {d:+.1f} vs settimana prec.</span>'

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Citrini Doomsday Scenario</title>
<style>
  body {{ margin:0; background:#FCFCFD; color:{INK}; font-family:Inter,Aptos,'Segoe UI',Arial,sans-serif; }}
  main {{ max-width:1040px; margin:0 auto; padding:32px 24px 72px; }}
  .brandbar {{ background:#fff; border-bottom:4px solid {DARK_RED}; padding:4px 0 14px; margin-bottom:22px; }}
  .brandbar .mark {{ display:block; color:{DARK_RED}; font-weight:800; letter-spacing:3px; font-size:14px; text-transform:uppercase; margin-bottom:5px; }}
  .brandbar .tag {{ display:block; color:{DARK_RED}; font-size:27px; font-weight:800; line-height:1.15; }}
  h1 {{ font-size:34px; line-height:1.12; margin:0 0 8px; font-weight:800; }}
  .subtitle {{ color:{MUTED}; margin:0 0 20px; font-weight:600; }}
  h2 {{ font-size:22px; margin:26px 0 12px; font-weight:800; border-left:5px solid {BRAND_RED}; padding-left:12px; }}
  h3 {{ font-weight:800; }}
  .redband {{ height:4px; background:{BRAND_RED}; border-radius:2px; margin:38px 0 4px; }}
  .about {{ background:#fff; border:1px solid {GRID}; border-left:5px solid {BRAND_RED}; border-radius:8px; padding:16px 20px; margin:0 0 10px; }}
  .about h2 {{ border:0; padding:0; margin:0 0 8px; font-size:19px; }}
  .about p {{ margin:0 0 8px; }}
  p, li {{ font-size:15.5px; line-height:1.58; }}
  .hero {{ background:#fff; border:1px solid {GRID}; border-radius:8px; padding:18px 22px; text-align:center; }}
  .delta {{ display:inline-block; margin-top:6px; color:{MUTED}; font-size:14px; }}
  .metrics {{ display:grid; grid-template-columns:repeat(5,1fr); gap:10px; margin:22px 0 12px; }}
  .metric {{ background:#fff; border:1px solid {GRID}; border-radius:8px; padding:14px; text-align:center; }}
  .metric strong {{ display:block; font-size:20px; margin-bottom:4px; }}
  .metric span {{ color:{MUTED}; font-size:12.5px; }}
  img {{ max-width:100%; display:block; margin:14px auto 8px; }}
  table {{ width:100%; border-collapse:collapse; margin:14px 0 26px; background:#fff; border:1px solid {GRID}; }}
  th, td {{ padding:9px 11px; border-bottom:1px solid {GRID}; text-align:left; font-size:13.5px; }}
  th {{ color:#464C55; background:#F4F5F7; }}
  td small {{ color:{MUTED}; }}
  .note {{ color:{MUTED}; font-size:13px; }}
  .two {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
  ul.ev {{ margin:6px 0 0; padding-left:18px; }}
  ul.ev li {{ font-size:12.5px; line-height:1.4; color:{MUTED}; margin-bottom:2px; }}
  ul.ev a {{ color:{BRAND_RED}; text-decoration:none; }}
  @media (max-width:760px) {{ .metrics {{ grid-template-columns:repeat(2,1fr); }} .two {{ grid-template-columns:1fr; }} h1 {{ font-size:28px; }} }}
  @page {{ size:A4; margin:16mm 14mm; }}
  @media print {{ main {{ padding:0; max-width:none; }} img, table, .metric, .hero {{ break-inside:avoid; }} }}
</style>
</head>
<body>
<main>
  <div class="brandbar"><span class="mark">Macro Grisa</span><span class="tag">Citrini Doomsday Scenario · report settimanale</span></div>
  <h1>Citrini Doomsday Scenario</h1>
  <p class="subtitle">Termometro settimanale della tesi "AI Doomsday / 2028 Global Intelligence Crisis" — dati al {snap.asof}.</p>

  <section class="about">
    <h2>Cos'è questo indicatore</h2>
    <p>Il <strong>Doomsday Scenario</strong> è un termometro settimanale (<strong>0–100</strong>) che misura quanto i dati di mercato stanno già confermando la tesi "AI Doomsday" di Citrini Research. La catena è: l'AI sostituisce il lavoro &rarr; sale la disoccupazione &rarr; crollano i consumi &rarr; si rompe il credito privato (molto esposto al settore tech/AI) &rarr; recessione e drawdown azionario. L'indicatore non prevede lo scenario: misura <em>quanto</em> i mercati lo stanno già prezzando.</p>
    <p><strong>Come funziona:</strong> sei componenti osservabili vengono convertite in sub-punteggi 0–100 e combinate in una media pesata &mdash; <strong>deterioramento del lavoro</strong> (richieste iniziali di sussidio, 20%), <strong>stress sul credito</strong> (High Yield OAS, 20%), <strong>drawdown azionario</strong> (S&amp;P 500 dal massimo 52w, 20%), <strong>paura/volatilità</strong> (VIX, 15%), <strong>debolezza dei consumi</strong> (ciclici vs difensivi XLY/XLP, 15%) e <strong>segnale di recessione</strong> (curva 10y-2y, 10%). A queste si aggiunge un settimo componente qualitativo &mdash; <strong>narrativa AI-crisis</strong> &mdash; dal sentiment di news, filing e transcript interrogati su <a href="https://bigdata.com">Bigdata.com</a>. <strong>0</strong> = nessun segnale, <strong>100</strong> = scenario in pieno svolgimento; il punteggio complessivo definisce il <strong>regime</strong> (da Quiescente a Doomsday).</p>
    <p><strong>Doomsday trade:</strong> accanto al termometro, un basket <strong>long/short</strong> mostra se il mercato sta ruotando verso lo scenario. <strong>LONG</strong> sui rifugi (oro, Treasury lunghi, utility, beni di prima necessità); <strong>SHORT</strong> sugli asset più vulnerabili (software, private credit/BDC, banche regionali, retail, trasporti). Se il long sovraperforma lo short, il mercato sta iniziando a prezzare il rischio.</p>
  </section>

  <section class="hero">
    <img src="{_gauge(snap)}" alt="Termometro composito">
    <div>{delta}</div>
  </section>

  <section class="metrics">
    {''.join(f'<div class="metric"><strong>{snap.spread[h]:+.1f}%</strong><span>Basket {h}</span></div>' for h in horizons)}
  </section>

  <div class="redband"></div>
  <h2>Cosa dice questa settimana</h2>
  <p>Il termometro composito e a <strong>{snap.composite:.0f}/100</strong> ({snap.regime}). Misura quanto i
  dati di mercato stanno gia confermando la catena della tesi Citrini: shock occupazionale da AI -&gt;
  crollo dei consumi -&gt; stress sul credito privato -&gt; recessione e drawdown azionario. Il
  <strong>Doomsday trade</strong> (long sui rifugi, short sui settori vulnerabili) rende
  <strong>{snap.spread['1m']:+.1f}%</strong> nell'ultimo mese: valori positivi indicano che il mercato
  sta prezzando lo scenario.</p>

  <div class="redband"></div>
  <h2>Il termometro per componente</h2>
  <img src="{_components_bar(snap)}" alt="Contributo per componente">
  {_comp_table(snap)}

  <div class="redband"></div>
  {_sentiment_block(snap)}

  <div class="redband"></div>
  <h2>Il Doomsday trade (basket long/short)</h2>
  <p>Spread fra un paniere di <strong>rifugi</strong> (oro, Treasury lunghi, utility, beni di prima
  necessita) e un paniere di <strong>settori vulnerabili</strong> alla tesi (software, private credit,
  banche regionali, retail, logistica). Performance = media LONG − media SHORT.</p>
  <img src="{_basket_bar(snap)}" alt="Performance del basket">
  <div class="two">
    <div><h3 style="margin:0 0 6px">LONG · rifugi</h3>{_legs_table(snap.long_legs, horizons)}</div>
    <div><h3 style="margin:0 0 6px">SHORT · vulnerabili</h3>{_legs_table(snap.short_legs, horizons)}</div>
  </div>

  <div class="redband"></div>
  {history_block}

  <div class="redband"></div>
  <h2>Metodologia e assunzioni</h2>
  <p class="note">Indicatore prototipale a scopo informativo, <strong>non e una raccomandazione di
  investimento</strong>. I proxy, i pesi e le soglie sono scelte dichiarate in
  <code>doomsday/config.py</code> e vanno ritarate sui propri criteri. Fonti gratuite senza API key:
  serie macro da FRED (St. Louis Fed), prezzi da Stooq. Il 7o componente
  &mdash; <strong>narrativa AI-crisis</strong> &mdash; deriva dal sentiment di news, filing e transcript
  della catena della tesi interrogati su <a href="https://bigdata.com">Bigdata.com</a>: viene calcolato da
  una sessione Claude (il connettore non e richiamabile dalla pipeline) e salvato in
  <code>doomsday/sentiment.json</code>; se manca o e obsoleto viene escluso e il termometro si rinormalizza
  sui componenti rimasti. Il punteggio composito e la media pesata rinormalizzata dei sub-punteggi 0-100 di
  ciascuna componente. Rigenerato dalla pipeline <code>scripts/build_doomsday.py</code>.</p>
</main>
</body>
</html>
"""
