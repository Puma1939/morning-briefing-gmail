# Pharma Milano Intelligence

Osservatorio territoriale su **farmacie e parafarmacie del Comune di Milano**.
A partire dagli open data di Comune e Regione Lombardia, il progetto profila ogni
NIL (Nucleo di Identità Locale / quartiere) e ogni farmacia con indicatori di
**opportunità** e **saturazione competitiva**, e genera un report HTML pronto da
presentare.

## Cosa contiene

```
pharma/                       pacchetto di analisi
  scoring.py                  ricostruzione metriche e punteggi dai dati grezzi
  enrichment.py               schema e merge dei dati di arricchimento
  financials.py               modulo commercialisti: bilancio vs potenziale
  schede.py                   schede per singola farmacia (HTML/PDF)
data/                         CSV di input
  farmacie.csv                422 farmacie con scoring per NIL
  parafarmacie_attive.csv     95 parafarmacie attive
  nil_scoring.csv             69 NIL con metriche e archetipo
  fonti.csv                   dataset e date di aggiornamento
  enrichment_farmacie.csv     arricchimento (orari, servizi, social...) - da popolare
  financials_farmacie.csv     dati di bilancio - template da popolare
scripts/
  build_report.py             report territoriale -> HTML + PDF + grafici
  build_schede.py             schede per singola farmacia -> HTML + PDF
  refresh_data.py             scarica open data e ricalcola lo scoring
report/
  pharma_milano_intelligence.{html,pdf}   report territoriale
  charts/                     grafici in PNG
  schede/                     schede per farmacia
.github/workflows/refresh-data.yml   aggiornamento automatico mensile
```

## Comandi

```bash
pip install -r requirements.txt

python scripts/build_report.py     # report territoriale (HTML + PDF + grafici)
python scripts/build_schede.py     # schede farmacia (tutte quelle arricchite)
python scripts/build_schede.py MI2052 MI1440   # solo alcune
python scripts/refresh_data.py     # aggiorna i dati e ricalcola lo scoring
```

Il report incorpora i grafici in base64, quindi l'HTML resta visualizzabile
anche se spostato da solo. Il PDF richiede `weasyprint`.

## I tre moduli (next step)

**1. Arricchimento schede** (`pharma/enrichment.py`) — orari, servizi, recensioni,
sito, e-commerce, social per ogni farmacia. Questi dati **non sono negli open
data**: vanno raccolti da fonti esterne e inseriti in `data/enrichment_farmacie.csv`
(lo schema e gia pronto, con alcune righe di esempio).

**2. Modulo commercialisti** (`pharma/financials.py`) — incrocia il bilancio
(`data/financials_farmacie.csv`, da popolare) con il potenziale territoriale del
NIL e dice se la farmacia rende sopra/sotto le attese della zona, confrontando i
margini con benchmark di settore. Le zone centrali ad alto flusso non residente
vengono riconosciute ed escluse dal verdetto secco. I parametri economici sono
**assunzioni dichiarate** in cima al modulo, da tarare su dati reali.

**3. Aggiornamento automatico** (`scripts/refresh_data.py` + workflow) — ricalcola
tutto dagli open data. La metodologia di scoring e stata validata: ricostruisce i
punteggi originali con errore trascurabile (opportunity maxerr 0.34, saturazione
1.34, archetipi 98.6%). Gli endpoint remoti del portale CKAN vanno confermati alla
prima esecuzione con rete attiva (vedi note nello script).

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
