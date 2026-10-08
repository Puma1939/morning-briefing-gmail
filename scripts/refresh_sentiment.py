#!/usr/bin/env python3
"""Valida e ricalcola doomsday/sentiment.json (layer narrativa AI-crisis).

PERCHE' NON E' AUTOMATICO
    Il sub-punteggio sentiment nasce da ricerche sul connettore Bigdata.com
    (https://bigdata.com), che vive solo in una sessione Claude e NON e
    richiamabile da uno script Python nella pipeline GitHub Actions. Il flusso e:

      1. una sessione Claude esegue le ricerche qui sotto su Bigdata.com;
      2. assegna a ogni tema un punteggio 0-100 (alto = la narrativa conferma la tesi);
      3. aggiorna doomsday/sentiment.json (temi, punteggi, pesi, evidenze, asof);
      4. committa il file: la pipeline lo legge e lo combina con i 6 componenti di mercato.

    Questo script non chiama Bigdata.com: valida lo schema del file, ricalcola il
    sub-punteggio dai temi e lo riscrive con asof di oggi. Serve a tenere il file
    coerente e a documentare il metodo.

QUERY BIGDATA.COM (una per tema, finestra ~30 giorni, smart mode)
    ai_labor       "AI-driven white-collar job cuts and workforce reductions ... in the last month"
    software       "Software company layoffs and weakening demand for custom software development ..."
    private_credit "Private credit and BDC stress, rising defaults and NAV markdowns ..."
    payments       "Payment processors facing slowing consumer transaction volumes and credit losses ..."
    logistics      "Delivery and logistics companies cutting jobs amid weakening consumer demand ..."

    Per ogni tema: valutare volume + tono negativo + severita/escalation del
    linguaggio, pesando i contrappesi (smentite, dati macro che non confermano).

USO
    python scripts/refresh_sentiment.py            # valida + ricalcola, stampa il riepilogo
    python scripts/refresh_sentiment.py --set-today # aggiorna anche il campo asof a oggi
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from doomsday import config
from doomsday.sentiment import composite_from_themes

REQUIRED_THEME_KEYS = {"key", "label", "weight", "score"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set-today", action="store_true", help="imposta asof alla data odierna")
    ap.add_argument("--file", default=str(config.SENTIMENT_FILE), help="percorso del JSON")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"ERRORE: {path} non trovato", file=sys.stderr)
        return 1

    data = json.loads(path.read_text(encoding="utf-8"))
    themes = data.get("themes") or []
    if not themes:
        print("ERRORE: nessun tema nel file", file=sys.stderr)
        return 1

    errors = []
    for i, t in enumerate(themes):
        missing = REQUIRED_THEME_KEYS - set(t)
        if missing:
            errors.append(f"tema #{i} ({t.get('key','?')}): campi mancanti {sorted(missing)}")
        if "score" in t and not (0 <= float(t["score"]) <= 100):
            errors.append(f"tema {t.get('key','?')}: score fuori range 0-100")
    if errors:
        print("VALIDAZIONE FALLITA:", file=sys.stderr)
        for e in errors:
            print("  -", e, file=sys.stderr)
        return 1

    subscore = composite_from_themes(themes)
    data["subscore"] = subscore
    if args.set_today:
        data["asof"] = date.today().isoformat()

    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"OK - sentiment sub-punteggio {subscore:.1f}/100 · asof {data.get('asof')}")
    for t in sorted(themes, key=lambda x: -float(x["score"])):
        print(f"    {float(t['score']):5.0f}  peso {float(t['weight']):.0%}  {t['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
