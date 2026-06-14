# Pharma Milano Intelligence

Osservatorio territoriale su **farmacie e parafarmacie del Comune di Milano**.
A partire dagli open data di Comune e Regione Lombardia, il progetto profila ogni
NIL (Nucleo di Identità Locale / quartiere) e ogni farmacia con indicatori di
**opportunità** e **saturazione competitiva**, e genera un report HTML pronto da
presentare.

## Cosa contiene

```
data/                         export CSV (input della pipeline)
  farmacie.csv                422 farmacie con scoring per NIL
  parafarmacie_attive.csv     95 parafarmacie attive
  nil_scoring.csv             69 NIL con metriche e archetipo
  fonti.csv                   dataset e date di aggiornamento
scripts/build_report.py       pipeline: legge i CSV -> grafici -> report HTML
report/
  pharma_milano_intelligence.html   report autoconsistente (grafici in base64)
  charts/                     i grafici in PNG
```

## Come rigenerare il report

```bash
pip install -r requirements.txt
python scripts/build_report.py
```

Il comando ricrea i grafici in `report/charts/` e riscrive
`report/pharma_milano_intelligence.html`. Le immagini sono incorporate nel file
HTML in base64, quindi il report resta visualizzabile anche se spostato da solo.

## Le metriche

Ogni NIL viene descritto da indicatori derivati dai dati pubblici:

| Indicatore | Significato |
|---|---|
| `opportunity_score` | quanto la zona sembra espandibile (molti residenti per farmacia, alta quota over 65, bassa pressione parafarmacie) |
| `saturation_index` | quanto la concorrenza è compressa (densità farmacie + vicinanza tra loro + parafarmacie) |
| `pop_per_farmacia` | residenti 2025 per farmacia presente nel NIL |
| `quota_over65_pct` | quota di popolazione over 65 (domanda sanitaria) |
| `archetipo` | classificazione sintetica della zona |

## Fonti

- Comune di Milano / Regione Lombardia — *Farmacie nel Comune di Milano* (19-05-2026)
- Comune di Milano — *Popolazione residenti per cittadinanza e quartiere* (31-03-2026)
- Comune di Milano — *Parafarmacie* (01-09-2025)

## Note

Lo score è un prototipo: **non** usa ancora ricavi, affitti, flussi pedonali,
orari, servizi, recensioni o dati di bilancio. È pensato come base per un
osservatorio commerciale da arricchire (vedi *Recommended Next Steps* nel report).
