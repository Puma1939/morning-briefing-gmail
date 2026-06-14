#!/usr/bin/env python3
"""Pharma Milano Intelligence - pipeline di rielaborazione.

Legge gli export CSV (data/), rigenera i grafici (report/charts/) e produce
un report HTML autoconsistente con le immagini incorporate in base64, in modo
che il file resti leggibile anche spostato fuori dalla cartella del progetto.

Uso:
    python scripts/build_report.py
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CHARTS = ROOT / "report" / "charts"
REPORT_HTML = ROOT / "report" / "pharma_milano_intelligence.html"

# Palette coerente con il report
INK = "#1F2430"
MUTED = "#6F768A"
GRID = "#E6E8F0"
ACCENT = "#2F6FED"
ACCENT_WARM = "#E0703A"
ACCENT_GREEN = "#2Fae7d"

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


def load_data() -> dict[str, pd.DataFrame]:
    nil = pd.read_csv(DATA / "nil_scoring.csv")
    farmacie = pd.read_csv(DATA / "farmacie.csv")
    para = pd.read_csv(DATA / "parafarmacie_attive.csv")
    fonti = pd.read_csv(DATA / "fonti.csv")
    return {"nil": nil, "farmacie": farmacie, "para": para, "fonti": fonti}


def muni_label(value) -> str:
    """Etichetta municipio robusta: gestisce sia '5' sia '1, 5' (NIL a cavallo)."""
    s = str(value).strip()
    parts = [p.strip() for p in s.replace(".0", "").split(",") if p.strip()]
    return "M" + ", ".join(parts)


def _finish(fig, name: str) -> None:
    fig.tight_layout()
    CHARTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHARTS / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def chart_top_opportunity(nil: pd.DataFrame) -> None:
    top = nil.sort_values("opportunity_score", ascending=False).head(12)[::-1]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.barh(top["zona"], top["opportunity_score"], color=ACCENT_GREEN)
    ax.set_xlabel("Opportunity score")
    ax.set_title("NIL con maggiore opportunita territoriale", loc="left", fontsize=14, color=INK)
    for y, v in zip(range(len(top)), top["opportunity_score"]):
        ax.text(v - 2, y, f"{v:.1f}", va="center", ha="right", color="white", fontsize=9, fontweight="bold")
    ax.grid(axis="y", visible=False)
    _finish(fig, "top_opportunity.png")


def chart_top_saturation(nil: pd.DataFrame) -> None:
    top = nil.sort_values("saturation_index", ascending=False).head(12)[::-1]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.barh(top["zona"], top["saturation_index"], color=ACCENT_WARM)
    ax.set_xlabel("Saturation index")
    ax.set_title("NIL con maggiore saturazione competitiva", loc="left", fontsize=14, color=INK)
    for y, v in zip(range(len(top)), top["saturation_index"]):
        ax.text(v - 2, y, f"{v:.1f}", va="center", ha="right", color="white", fontsize=9, fontweight="bold")
    ax.grid(axis="y", visible=False)
    _finish(fig, "top_saturation.png")


def chart_scatter_pressure_senior(nil: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    sizes = (nil["residenti_2025"] / nil["residenti_2025"].max() * 600 + 20)
    sc = ax.scatter(
        nil["pop_per_farmacia"],
        nil["quota_over65_pct"],
        s=sizes,
        c=nil["opportunity_score"],
        cmap="viridis",
        alpha=0.8,
        edgecolor="white",
        linewidth=0.6,
    )
    ax.set_xlabel("Residenti per farmacia  (domanda potenziale)")
    ax.set_ylabel("Quota over 65 (%)  (domanda sanitaria)")
    ax.set_xlim(right=nil["pop_per_farmacia"].max() * 1.18)
    ax.set_title("Mappa decisionale: pressione vs domanda senior", loc="left", fontsize=14, color=INK)
    cbar = fig.colorbar(sc, ax=ax)
    cbar.set_label("Opportunity score", color=MUTED)
    # etichetta i 6 NIL a piu alto opportunity score
    for _, r in nil.sort_values("opportunity_score", ascending=False).head(6).iterrows():
        ax.annotate(
            r["nil"],
            (r["pop_per_farmacia"], r["quota_over65_pct"]),
            fontsize=8,
            color=INK,
            xytext=(5, 5),
            textcoords="offset points",
        )
    _finish(fig, "scatter_pressure_senior.png")


def chart_archetipi(nil: pd.DataFrame) -> None:
    counts = nil["archetipo"].value_counts()
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.barh(counts.index[::-1], counts.values[::-1], color=ACCENT)
    ax.set_xlabel("Numero di NIL")
    ax.set_title("Distribuzione dei NIL per archetipo", loc="left", fontsize=14, color=INK)
    for y, v in enumerate(counts.values[::-1]):
        ax.text(v + 0.2, y, str(v), va="center", color=INK, fontsize=9)
    ax.grid(axis="y", visible=False)
    _finish(fig, "archetipi.png")


def chart_municipi(nil: pd.DataFrame) -> None:
    # Un NIL a cavallo (es. municipio "1, 5") contribuisce a entrambi i municipi.
    rows = []
    for _, r in nil.iterrows():
        for part in str(r["municipio"]).replace(".0", "").split(","):
            part = part.strip()
            if part:
                rows.append({"m": int(float(part)), "farmacie": r["farmacie"], "para": r["parafarmacie_attive"]})
    g = (
        pd.DataFrame(rows)
        .groupby("m")
        .agg(farmacie=("farmacie", "sum"), parafarmacie=("para", "sum"))
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = range(len(g))
    ax.bar([i - 0.2 for i in x], g["farmacie"], width=0.4, label="Farmacie", color=ACCENT)
    ax.bar([i + 0.2 for i in x], g["parafarmacie"], width=0.4, label="Parafarmacie", color=ACCENT_WARM)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"M{int(m)}" for m in g.index])
    ax.set_ylabel("Numero di esercizi")
    ax.set_title("Farmacie e parafarmacie per municipio", loc="left", fontsize=14, color=INK)
    ax.legend(frameon=False)
    ax.grid(axis="x", visible=False)
    _finish(fig, "municipi.png")


def img_b64(name: str) -> str:
    data = (CHARTS / name).read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _rows(df: pd.DataFrame, cols: list[tuple[str, str]], fmt: dict | None = None) -> str:
    fmt = fmt or {}
    out = []
    for _, r in df.iterrows():
        cells = []
        for key, _label in cols:
            val = r[key]
            if key in fmt:
                val = fmt[key](r[key])
            cells.append(f"<td>{val}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(out)


def build_demo_cards(nil: pd.DataFrame) -> str:
    """Le 3 schede demo indicate nei next step: alto potenziale, satura, senior."""
    alto = nil.sort_values("opportunity_score", ascending=False).iloc[0]
    satura = nil.sort_values("saturation_index", ascending=False).iloc[0]
    senior = nil.sort_values("quota_over65_pct", ascending=False).iloc[0]

    def card(r, tag, color) -> str:
        return f"""
        <div class="card">
          <span class="tag" style="background:{color}">{tag}</span>
          <h3>{r['nil']} <small>({muni_label(r['municipio'])})</small></h3>
          <ul>
            <li>Farmacie in zona: <strong>{int(r['farmacie'])}</strong></li>
            <li>Residenti 2025: <strong>{int(r['residenti_2025']):,}</strong></li>
            <li>Residenti per farmacia: <strong>{int(r['pop_per_farmacia']):,}</strong></li>
            <li>Quota over 65: <strong>{r['quota_over65_pct']:.1f}%</strong></li>
            <li>Parafarmacie attive: <strong>{int(r['parafarmacie_attive'])}</strong></li>
            <li>Opportunity score: <strong>{r['opportunity_score']:.1f}</strong> &middot; Saturation: <strong>{r['saturation_index']:.1f}</strong></li>
          </ul>
          <p class="archetipo">{r['archetipo']}</p>
        </div>""".replace(",", ".")

    return (
        '<div class="cards">'
        + card(alto, "Alto potenziale", ACCENT_GREEN)
        + card(satura, "Zona satura", ACCENT_WARM)
        + card(senior, "Zona senior", ACCENT)
        + "</div>"
    )


def build_html(data: dict[str, pd.DataFrame]) -> str:
    nil = data["nil"]
    farmacie = data["farmacie"]
    para = data["para"]
    fonti = data["fonti"]

    n_farmacie = len(farmacie)
    n_para = len(para)
    n_nil = nil["id_nil"].nunique()
    residenti = int(nil["residenti_2025"].sum())

    top_opp = nil.sort_values("opportunity_score", ascending=False).head(12)
    top_sat = nil.sort_values("saturation_index", ascending=False).head(12)

    opp_cols = [
        ("nil", "NIL"), ("municipio", "Municipio"), ("farmacie", "Farmacie"),
        ("residenti_2025", "Residenti 2025"), ("pop_per_farmacia", "Residenti per farmacia"),
        ("quota_over65_pct", "Over 65"), ("opportunity_score", "Opportunity score"),
    ]
    opp_fmt = {
        "municipio": muni_label,
        "residenti_2025": lambda v: f"{int(v):,}".replace(",", "."),
        "pop_per_farmacia": lambda v: f"{int(v):,}".replace(",", "."),
        "quota_over65_pct": lambda v: f"{v:.1f}%",
        "opportunity_score": lambda v: f"<strong>{v:.1f}</strong>",
    }
    sat_cols = [
        ("nil", "NIL"), ("municipio", "Municipio"), ("farmacie", "Farmacie"),
        ("farmacie_per_10k", "Farmacie ogni 10k ab."), ("distanza_mediana_farmacia_m", "Distanza mediana competitor"),
        ("parafarmacie_attive", "Parafarmacie"), ("saturation_index", "Saturation index"),
    ]
    sat_fmt = {
        "municipio": muni_label,
        "farmacie_per_10k": lambda v: f"{v:.2f}",
        "distanza_mediana_farmacia_m": lambda v: f"{v:.0f} m",
        "saturation_index": lambda v: f"<strong>{v:.1f}</strong>",
    }

    fonti_rows = "\n".join(
        f"<tr><td>{r['fonte']}</td><td>{r['dataset']}</td><td>{r['aggiornamento']}</td></tr>"
        for _, r in fonti.iterrows()
    )

    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pharma Milano Intelligence</title>
<style>
  body {{ margin:0; background:#FCFCFD; color:{INK}; font-family:Inter,Aptos,'Segoe UI',Arial,sans-serif; }}
  main {{ max-width:1040px; margin:0 auto; padding:48px 24px 72px; }}
  h1 {{ font-size:34px; line-height:1.12; margin:0 0 8px; }}
  .subtitle {{ color:{MUTED}; margin:0 0 28px; }}
  h2 {{ font-size:22px; margin:42px 0 12px; }}
  h3 {{ font-size:17px; margin:0 0 10px; }}
  p, li {{ font-size:15.5px; line-height:1.58; }}
  .summary {{ background:#fff; border:1px solid {GRID}; border-radius:8px; padding:22px 24px; }}
  .summary p {{ margin:0 0 12px; }}
  .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:24px 0 12px; }}
  .metric {{ background:#fff; border:1px solid {GRID}; border-radius:8px; padding:16px; }}
  .metric strong {{ display:block; font-size:24px; margin-bottom:4px; }}
  .metric span {{ color:{MUTED}; font-size:13px; }}
  img {{ max-width:100%; display:block; margin:14px 0 8px; border:1px solid {GRID}; border-radius:8px; }}
  table {{ width:100%; border-collapse:collapse; margin:14px 0 26px; background:#fff; border:1px solid {GRID}; }}
  th, td {{ padding:10px 11px; border-bottom:1px solid {GRID}; text-align:left; font-size:13.5px; }}
  th {{ color:#464C55; background:#F4F5F7; }}
  .cards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:14px 0 8px; }}
  .card {{ background:#fff; border:1px solid {GRID}; border-radius:8px; padding:18px; }}
  .card ul {{ padding-left:18px; margin:8px 0; }}
  .tag {{ display:inline-block; color:#fff; font-size:12px; font-weight:600; padding:3px 9px; border-radius:99px; margin-bottom:8px; }}
  .archetipo {{ color:{MUTED}; font-style:italic; margin:6px 0 0; }}
  .note {{ color:{MUTED}; font-size:13.5px; }}
  @media (max-width:760px) {{ .metrics,.cards {{ grid-template-columns:1fr 1fr; }} h1 {{ font-size:28px; }} }}
  @page {{ size:A4; margin:16mm 14mm; }}
  @media print {{
    main {{ padding:0; max-width:none; }}
    h2 {{ break-after:avoid; }}
    img, table, .card, .metric, .summary {{ break-inside:avoid; }}
    .cards {{ break-inside:avoid; }}
  }}
</style>
</head>
<body>
<main>
  <h1>Pharma Milano Intelligence</h1>
  <p class="subtitle">Osservatorio territoriale su farmacie e parafarmacie del Comune di Milano - report rigenerato automaticamente dai dati open.</p>

  <section class="summary">
    <h2 style="margin-top:0">Executive Summary</h2>
    <p><strong>Il prodotto vendibile e un osservatorio territoriale, non un semplice elenco.</strong> La base pubblica consente gia di profilare {n_farmacie} farmacie milanesi per NIL/municipio, confrontarle con i residenti 2025 e stimare saturazione competitiva e domanda potenziale.</p>
    <p><strong>La prima leva commerciale e il benchmark di zona.</strong> Ogni farmacia puo ricevere una scheda che indica se opera in una zona satura, scoperta, senior-oriented o sotto pressione parafarmacie.</p>
    <p><strong>Per commercialisti e consulenti il valore aumenta collegando bilancio e territorio.</strong> Una farmacia con margini deboli in un NIL ad alto potenziale e un caso diverso da una farmacia debole in zona gia molto satura.</p>
  </section>

  <section class="metrics">
    <div class="metric"><strong>{n_farmacie}</strong><span>farmacie mappate</span></div>
    <div class="metric"><strong>{n_para}</strong><span>parafarmacie attive</span></div>
    <div class="metric"><strong>{n_nil}</strong><span>NIL analizzati</span></div>
    <div class="metric"><strong>{residenti:,}</strong><span>residenti 2025 nei NIL</span></div>
  </section>

  <h2>Dove il mercato sembra piu espandibile</h2>
  <p><strong>Le zone ad alto opportunity score combinano molti residenti per farmacia, domanda senior elevata e minore pressione da parafarmacie.</strong> Sono le aree dove una farmacia potrebbe avere piu spazio per servizi, fidelizzazione e ampliamento categorie, oppure dove un consulente puo leggere una performance sotto potenziale.</p>
  <img src="{img_b64('top_opportunity.png')}" alt="NIL con maggiore opportunita territoriale">
  <table>
    <thead><tr>{''.join(f'<th>{l}</th>' for _, l in opp_cols)}</tr></thead>
    <tbody>{_rows(top_opp, opp_cols, opp_fmt)}</tbody>
  </table>

  <h2>Dove la concorrenza e piu compressa</h2>
  <p><strong>La saturazione non e solo quante farmacie ci sono: conta anche quanto sono vicine tra loro e quanta concorrenza laterale arriva dalle parafarmacie.</strong> Questi NIL sono utili per vendere analisi di differenziazione, pricing, orari e servizi ad alto margine.</p>
  <img src="{img_b64('top_saturation.png')}" alt="NIL con maggiore saturazione competitiva">
  <table>
    <thead><tr>{''.join(f'<th>{l}</th>' for _, l in sat_cols)}</tr></thead>
    <tbody>{_rows(top_sat, sat_cols, sat_fmt)}</tbody>
  </table>

  <h2>La mappa decisionale per vendere alle farmacie</h2>
  <p><strong>Il posizionamento ideale del prodotto nasce dall'incrocio tra pressione competitiva e domanda sanitaria locale.</strong> I NIL in alto a sinistra sono meno presidiati ma con quota senior elevata; quelli in alto a destra hanno domanda senior ma anche concorrenza superiore. La dimensione della bolla indica i residenti, il colore l'opportunity score.</p>
  <img src="{img_b64('scatter_pressure_senior.png')}" alt="Scatter tra residenti per farmacia e quota over 65">

  <h2>Composizione del mercato</h2>
  <p>La maggior parte dei NIL ricade in pochi archetipi ricorrenti: e la base per impacchettare offerte commerciali standard per ogni tipologia di zona.</p>
  <img src="{img_b64('archetipi.png')}" alt="Distribuzione dei NIL per archetipo">
  <img src="{img_b64('municipi.png')}" alt="Farmacie e parafarmacie per municipio">

  <h2>Tre schede demo (una per archetipo)</h2>
  <p><strong>Servono per vendere il prodotto senza chiedere subito dati contabili.</strong> Una zona ad alto potenziale, una molto satura, una a forte componente senior.</p>
  {build_demo_cards(nil)}

  <h2>Recommended Next Steps</h2>
  <ol>
    <li><strong>Arricchire le schede.</strong> Aggiungere a ogni farmacia orari, servizi, recensioni, sito/e-commerce, consegna, telemedicina, CUP, dermocosmesi e presenza social.</li>
    <li><strong>Creare il modulo commercialisti.</strong> Inserire metriche anonime di bilancio: ricavi, margine lordo, costo personale, rotazione magazzino, EBITDA. Il confronto chiave diventa bilancio vs potenziale territoriale.</li>
    <li><strong>Aggiornare in automatico.</strong> Ricollegare la pipeline agli open data per rigenerare report e schede a ogni nuova release del Comune/Regione.</li>
  </ol>

  <h2>Fonti</h2>
  <table>
    <thead><tr><th>Fonte</th><th>Dataset</th><th>Aggiornamento</th></tr></thead>
    <tbody>{fonti_rows}</tbody>
  </table>

  <h2>Caveats And Assumptions</h2>
  <p class="note">Lo score e un prototipo: non usa ancora ricavi, affitti, flussi pedonali, orari, servizi, recensioni o dati di bilancio. Le parafarmacie sono filtrate per validita aperta. Report rigenerato dalla pipeline <code>scripts/build_report.py</code>.</p>
</main>
</body>
</html>
""".replace(f"{residenti:,}", f"{residenti:,}".replace(",", "."))


def main() -> None:
    data = load_data()
    nil = data["nil"]
    chart_top_opportunity(nil)
    chart_top_saturation(nil)
    chart_scatter_pressure_senior(nil)
    chart_archetipi(nil)
    chart_municipi(nil)
    html = build_html(data)
    REPORT_HTML.write_text(html, encoding="utf-8")
    print(f"OK - report scritto in {REPORT_HTML.relative_to(ROOT)}")
    print(f"     grafici in {CHARTS.relative_to(ROOT)}/")
    _write_pdf(html)


def _write_pdf(html: str) -> None:
    """Genera il PDF dal report. Richiede weasyprint (vedi requirements.txt)."""
    pdf_path = REPORT_HTML.with_suffix(".pdf")
    try:
        from weasyprint import HTML
    except ImportError:
        print("     PDF saltato: installa weasyprint (pip install weasyprint)")
        return
    HTML(string=html, base_url=str(ROOT)).write_pdf(str(pdf_path))
    print(f"     PDF scritto in {pdf_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
