"""Generazione delle schede per singola farmacia.

Ogni scheda fonde i tre livelli del prodotto:
  1. Territorio  - benchmark del NIL (opportunity, saturazione, domanda)
  2. Arricchimento - orari, servizi, canali, reputazione
  3. Bilancio    - confronto bilancio vs potenziale territoriale (commercialisti)

E' il "prodotto vendibile": una scheda per farmacia, esportabile in HTML e PDF.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import enrichment as enr
from . import financials as fin

INK = "#1F2430"
MUTED = "#6F768A"
GRID = "#E6E8F0"
GREEN = "#2Fae7d"
WARM = "#E0703A"
BLUE = "#2F6FED"


def _euro(v) -> str:
    if pd.isna(v):
        return "n.d."
    return f"€ {int(round(v)):,}".replace(",", ".")


def _pct(v, dec=1) -> str:
    return "n.d." if pd.isna(v) else f"{v:.{dec}f}%"


def _num(v, dec=0) -> str:
    if pd.isna(v):
        return "n.d."
    return f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _delta_chip(value, unit="pp", good_high=True) -> str:
    if pd.isna(value):
        return '<span class="chip neutral">n.d.</span>'
    positive = value >= 0
    good = positive if good_high else not positive
    color = GREEN if good else WARM
    sign = "+" if positive else ""
    return f'<span class="chip" style="background:{color}">{sign}{value:.1f} {unit}</span>'


def _bar(pct, color) -> str:
    pct = max(0, min(100, float(pct)))
    return (
        f'<div class="bar"><div class="bar-fill" style="width:{pct:.0f}%;background:{color}"></div></div>'
    )


def _services(value) -> str:
    items = enr.as_list(value)
    if not items:
        return '<span class="muted">nessun servizio censito</span>'
    return "".join(f'<span class="badge">{s}</span>' for s in items)


def _yesno(value) -> str:
    return "Sì" if enr.is_true(value) else "No"


def build_scheda(
    farm: pd.Series,
    e: pd.Series,
    f: pd.Series | None,
    medians: dict,
) -> str:
    """Costruisce l'HTML di una scheda. `f` puo essere None se manca il bilancio."""
    nome = farm["DESCRIZIONE_FARMACIA"]
    indirizzo = farm["INDIRIZZO"]
    nil = farm["NIL"]
    arche = farm["archetipo"]
    opp = farm["opportunity_score"]
    sat = farm["saturation_index"]

    # blocco bilancio (solo se presente)
    if f is not None and not pd.isna(f.get("ricavi")):
        giudizio = str(f["giudizio_potenziale"])
        alto_flusso = "alto flusso" in giudizio
        giudizio_color = (
            GREEN if "sopra" in giudizio
            else WARM if "sotto" in giudizio
            else BLUE
        )
        ratio_pct = (f["performance_ratio"] * 100) if not pd.isna(f["performance_ratio"]) else 0
        perf_display = "n.d." if alto_flusso else f"{ratio_pct:.0f}%"
        bilancio_html = f"""
      <h2>Bilancio vs potenziale territoriale</h2>
      <p class="muted">Confronto tra il fatturato dichiarato e i ricavi teorici stimati dalla sola domanda del NIL
      (assunzioni: € {fin.SPESA_PROCAPITE_ANNUA:.0f}/anno per residente, x{fin.MOLTIPLICATORE_SENIOR} per gli over 65).</p>
      <div class="grid3">
        <div class="kpi"><span>Ricavi {int(f['anno'])}</span><strong>{_euro(f['ricavi'])}</strong></div>
        <div class="kpi"><span>Ricavi attesi (territorio)</span><strong>{_euro(f['ricavi_attesi'])}</strong></div>
        <div class="kpi"><span>Performance</span><strong style="color:{giudizio_color}">{perf_display}</strong></div>
      </div>
      <p class="verdict" style="border-color:{giudizio_color};color:{giudizio_color}">{giudizio.capitalize()}</p>
      <table>
        <thead><tr><th>Indicatore</th><th>Farmacia</th><th>Benchmark settore</th><th>Scostamento</th></tr></thead>
        <tbody>
          <tr><td>Margine lordo</td><td>{_pct(f['margine_lordo_pct'])}</td><td>{fin.BENCH_MARGINE_LORDO_PCT:.1f}%</td><td>{_delta_chip(f['delta_margine_pp'])}</td></tr>
          <tr><td>EBITDA</td><td>{_pct(f['ebitda_pct'])}</td><td>{fin.BENCH_EBITDA_PCT:.1f}%</td><td>{_delta_chip(f['delta_ebitda_pp'])}</td></tr>
          <tr><td>Rotazione magazzino</td><td>{_num(f['rotazione_magazzino'],1)}x</td><td>{fin.BENCH_ROTAZIONE:.1f}x</td><td>{_delta_chip(f['delta_rotazione'],'x')}</td></tr>
          <tr><td>Costo personale</td><td>{_pct(f['costo_personale_pct'])}</td><td class="muted">-</td><td class="muted">-</td></tr>
        </tbody>
      </table>"""
    else:
        bilancio_html = """
      <h2>Bilancio vs potenziale territoriale</h2>
      <p class="muted">Dati di bilancio non disponibili. Inseriscili in <code>data/financials_farmacie.csv</code>
      per attivare il confronto bilancio vs potenziale.</p>"""

    rating = e.get("rating")
    rating_html = (
        f'{_num(rating,1)}/5 <span class="muted">({_num(e.get("recensioni_n"))} recensioni)</span>'
        if not pd.isna(rating) else '<span class="muted">non censito</span>'
    )
    social = []
    if not pd.isna(e.get("instagram")) and str(e.get("instagram")).strip():
        social.append(f"Instagram {e['instagram']}")
    if not pd.isna(e.get("facebook")) and str(e.get("facebook")).strip():
        social.append(f"Facebook {e['facebook']}")
    social_html = " · ".join(social) if social else '<span class="muted">non censiti</span>'
    sito = e.get("sito_web")
    sito_html = f'<a href="{sito}">{sito}</a>' if not pd.isna(sito) and str(sito).strip() else '<span class="muted">non censito</span>'

    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scheda - {nome}</title>
<style>
  body {{ margin:0; background:#FCFCFD; color:{INK}; font-family:Inter,Aptos,'Segoe UI',Arial,sans-serif; }}
  main {{ max-width:820px; margin:0 auto; padding:40px 24px 64px; }}
  h1 {{ font-size:26px; margin:0 0 4px; }}
  .addr {{ color:{MUTED}; margin:0 0 4px; }}
  .arche {{ display:inline-block; background:{BLUE}; color:#fff; font-size:12px; font-weight:600; padding:3px 10px; border-radius:99px; }}
  h2 {{ font-size:18px; margin:30px 0 10px; border-bottom:1px solid {GRID}; padding-bottom:6px; }}
  .grid3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin:10px 0; }}
  .kpi {{ background:#fff; border:1px solid {GRID}; border-radius:8px; padding:12px; }}
  .kpi span {{ display:block; color:{MUTED}; font-size:12px; margin-bottom:4px; }}
  .kpi strong {{ font-size:20px; }}
  .bar {{ background:{GRID}; border-radius:99px; height:8px; margin:6px 0 14px; overflow:hidden; }}
  .bar-fill {{ height:100%; }}
  .row {{ display:flex; justify-content:space-between; font-size:13px; color:{MUTED}; }}
  table {{ width:100%; border-collapse:collapse; margin:10px 0; background:#fff; border:1px solid {GRID}; }}
  th,td {{ padding:9px 11px; border-bottom:1px solid {GRID}; text-align:left; font-size:13.5px; }}
  th {{ background:#F4F5F7; color:#464C55; }}
  .badge {{ display:inline-block; background:#EEF2FB; color:{BLUE}; font-size:12px; padding:3px 9px; border-radius:6px; margin:0 5px 5px 0; }}
  .chip {{ display:inline-block; color:#fff; font-size:12px; font-weight:600; padding:2px 8px; border-radius:6px; }}
  .chip.neutral {{ background:{MUTED}; }}
  .muted {{ color:{MUTED}; }}
  .verdict {{ display:inline-block; border:1px solid; border-radius:8px; padding:6px 12px; font-weight:600; margin:6px 0 12px; }}
  dl {{ display:grid; grid-template-columns:160px 1fr; gap:6px 16px; margin:8px 0; font-size:14px; }}
  dt {{ color:{MUTED}; }}
  a {{ color:{BLUE}; }}
  @page {{ size:A4; margin:14mm; }}
  @media print {{ main {{ padding:0; }} h2,table,.grid3 {{ break-inside:avoid; }} }}
</style></head>
<body><main>
  <h1>{nome}</h1>
  <p class="addr">{indirizzo} · NIL {nil}</p>
  <span class="arche">{arche}</span>

  <h2>Profilo territoriale del NIL</h2>
  <div class="row"><span>Opportunity score</span><span><strong>{opp:.1f}</strong>/100</span></div>
  {_bar(opp, GREEN)}
  <div class="row"><span>Saturazione competitiva</span><span><strong>{sat:.1f}</strong>/100</span></div>
  {_bar(sat, WARM)}
  <table>
    <tbody>
      <tr><td>Residenti per farmacia (NIL)</td><td>{_num(farm['pop_per_farmacia'])}</td><td class="muted">mediana città {_num(medians['pop_per_farmacia'])}</td></tr>
      <tr><td>Quota over 65 (NIL)</td><td>{_pct(farm['quota_over65_pct'])}</td><td class="muted">mediana città {_pct(medians['quota_over65_pct'])}</td></tr>
      <tr><td>Concorrente più vicino</td><td>{_num(farm.get('nearest_pharmacy_m'))} m</td><td class="muted">mediana città {_num(medians['nearest_pharmacy_m'])} m</td></tr>
    </tbody>
  </table>

  <h2>Servizi e reputazione</h2>
  <dl>
    <dt>Catena</dt><dd>{e.get('catena') if not pd.isna(e.get('catena')) else '<span class="muted">indipendente / n.d.</span>'}</dd>
    <dt>Orari</dt><dd>{e.get('orari') if not pd.isna(e.get('orari')) else '<span class="muted">non censiti</span>'}{' · <strong>H24</strong>' if enr.is_true(e.get('aperta_24h')) else ''}</dd>
    <dt>Servizi</dt><dd>{_services(e.get('servizi'))}</dd>
    <dt>Canali</dt><dd>Sito: {sito_html} · E-commerce: {_yesno(e.get('ecommerce'))} · Consegna: {_yesno(e.get('consegna_domicilio'))} · Telemedicina: {_yesno(e.get('telemedicina'))} · CUP: {_yesno(e.get('cup'))}</dd>
    <dt>Reputazione</dt><dd>{rating_html}</dd>
    <dt>Social</dt><dd>{social_html}</dd>
  </dl>
  <p class="muted" style="font-size:12.5px">Completezza dati di arricchimento: {_num(e.get('completezza_pct'))}%</p>
  {bilancio_html}

  <p class="muted" style="font-size:12px;margin-top:24px">Generato da Pharma Milano Intelligence. Lo score territoriale usa open data del Comune/Regione; i benchmark di bilancio sono assunzioni dichiarate, da tarare su fonti di settore.</p>
</main></body></html>"""


def build_index(farmacie_scored: pd.DataFrame, codici: list[str], out_dir: Path) -> Path:
    """Pagina indice con ricerca client-side che linka tutte le schede generate."""
    fs = farmacie_scored.copy()
    fs["CODICE_FARMACIA"] = fs["CODICE_FARMACIA"].astype(str)
    sub = fs[fs["CODICE_FARMACIA"].isin(codici)].sort_values("opportunity_score", ascending=False)
    rows = "\n".join(
        f'<tr><td><a href="scheda_{r.CODICE_FARMACIA}.html">{r.CODICE_FARMACIA}</a></td>'
        f"<td>{r.DESCRIZIONE_FARMACIA}</td><td>{r.NIL}</td>"
        f"<td>{r.archetipo}</td><td>{r.opportunity_score:.1f}</td>"
        f"<td>{r.saturation_index:.1f}</td></tr>"
        for r in sub.itertuples()
    )
    html = f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Schede farmacie - indice</title>
<style>
  body {{ font-family:Inter,Aptos,'Segoe UI',Arial,sans-serif; color:{INK}; margin:0; background:#FCFCFD; }}
  main {{ max-width:1000px; margin:0 auto; padding:40px 24px; }}
  h1 {{ font-size:26px; margin:0 0 6px; }}
  p {{ color:{MUTED}; }}
  input {{ width:100%; padding:10px 12px; font-size:15px; border:1px solid {GRID}; border-radius:8px; margin:14px 0; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid {GRID}; }}
  th,td {{ padding:9px 11px; border-bottom:1px solid {GRID}; text-align:left; font-size:13.5px; }}
  th {{ background:#F4F5F7; color:#464C55; }}
  a {{ color:{BLUE}; text-decoration:none; }}
</style></head><body><main>
  <h1>Schede farmacie - Milano</h1>
  <p>{len(sub)} schede. Filtra per nome, NIL o archetipo.</p>
  <input id="q" placeholder="Cerca..." onkeyup="filtra()">
  <table id="t">
    <thead><tr><th>Codice</th><th>Farmacia</th><th>NIL</th><th>Archetipo</th><th>Opportunity</th><th>Saturazione</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <script>
    function filtra() {{
      var q = document.getElementById('q').value.toLowerCase();
      document.querySelectorAll('#t tbody tr').forEach(function(tr) {{
        tr.style.display = tr.textContent.toLowerCase().indexOf(q) > -1 ? '' : 'none';
      }});
    }}
  </script>
</main></body></html>"""
    path = out_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def build_all(
    farmacie_scored: pd.DataFrame,
    enrichment: pd.DataFrame,
    financials_computed: pd.DataFrame | None,
    out_dir: Path,
    codici: list[str] | None = None,
    pdf: bool = True,
) -> list[Path]:
    """Genera le schede per i codici indicati (default: quelli arricchiti)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    medians = {
        "pop_per_farmacia": farmacie_scored["pop_per_farmacia"].median(),
        "quota_over65_pct": farmacie_scored["quota_over65_pct"].median(),
        "nearest_pharmacy_m": farmacie_scored["nearest_pharmacy_m"].median(),
    }
    enr_idx = enrichment.set_index("codice_farmacia")
    fin_idx = (
        financials_computed.set_index("codice_farmacia")
        if financials_computed is not None else None
    )
    if codici is None:
        # farmacie con almeno un dato di arricchimento
        codici = enrichment.loc[enrichment["completezza_pct"] > 0, "codice_farmacia"].tolist()

    written: list[Path] = []
    try:
        from weasyprint import HTML as WeasyHTML
        have_pdf = pdf
    except ImportError:
        have_pdf = False

    fs = farmacie_scored.copy()
    fs["CODICE_FARMACIA"] = fs["CODICE_FARMACIA"].astype(str)
    for codice in codici:
        rows = fs[fs["CODICE_FARMACIA"] == codice]
        if rows.empty:
            continue
        farm = rows.iloc[0]
        e = enr_idx.loc[codice] if codice in enr_idx.index else pd.Series(dtype=object)
        f = (
            fin_idx.loc[codice]
            if fin_idx is not None and codice in fin_idx.index else None
        )
        html = build_scheda(farm, e, f, medians)
        html_path = out_dir / f"scheda_{codice}.html"
        html_path.write_text(html, encoding="utf-8")
        written.append(html_path)
        if have_pdf:
            WeasyHTML(string=html).write_pdf(str(out_dir / f"scheda_{codice}.pdf"))
    return written
