#!/usr/bin/env python3
"""Aggiornamento dati e ricalcolo dello scoring.

Scarica i dataset open data del Comune di Milano, normalizza le colonne,
ricalcola tutte le metriche con `pharma.scoring` e riscrive i CSV in data/.
Se la rete non e disponibile, ricade sui dati locali e ricalcola comunque lo
scoring (utile per verificare la riproducibilita della metodologia).

Uso:
    python scripts/refresh_data.py            # prova remoto, fallback locale
    python scripts/refresh_data.py --local    # forza ricalcolo dai dati locali
    python scripts/refresh_data.py --out /tmp/x   # scrive altrove (test)

NOTA: gli endpoint sotto sono del portale CKAN del Comune di Milano. Gli ID delle
risorse vanno confermati alla prima esecuzione con rete attiva (il portale puo
ripubblicare le risorse con nuovi id). Sono centralizzati qui per facilitarlo.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pharma import DATA, scoring

# Portale open data del Comune di Milano (CKAN datastore -> dump CSV per risorsa)
CKAN = "https://dati.comune.milano.it/dataset"
DATASETS = {
    # nome_logico: (pagina_dataset, url_csv_risorsa_da_confermare)
    "farmacie": f"{CKAN}/ds634-economia-farmacie-attivita",
    "parafarmacie": f"{CKAN}/parafarmacie",
    "popolazione": f"{CKAN}/popolazione-residente-per-nil",
}


def _download_csv(url: str, timeout: int = 30) -> pd.DataFrame:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "pharma-milano/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return pd.read_csv(resp)


def fetch_remote() -> dict[str, pd.DataFrame]:
    """Scarica e normalizza i dataset remoti. Solleva su qualsiasi errore."""
    raise NotImplementedError(
        "Risorse CSV remote da confermare: aprire le pagine in DATASETS con rete "
        "attiva, copiare l'URL della risorsa CSV e completare _download_csv()."
    )


def load_local() -> dict[str, pd.DataFrame]:
    """Sorgenti locali per il ricalcolo. La popolazione per NIL e estratta dal
    dataset NIL esistente (in produzione arriva dal dataset popolazione)."""
    farmacie = pd.read_csv(DATA / "farmacie.csv")
    para = pd.read_csv(DATA / "parafarmacie_attive.csv")
    nil = pd.read_csv(DATA / "nil_scoring.csv")
    popolazione = nil[["id_nil", "residenti_2025", "residenti_over65"]].copy()
    return {
        "farmacie": farmacie[["CODICE_FARMACIA", "DESCRIZIONE_FARMACIA", "INDIRIZZO",
                              "id_nil", "nil", "municipio", "lon", "lat"]].rename(
            columns={"nil": "nil_name"}),
        "parafarmacie": para[["id_nil"]],
        "popolazione": popolazione,
    }


def recompute(src: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    f = src["farmacie"].rename(columns={"nil_name": "nil"})
    nil_scoring = scoring.compute_nil_scoring(
        f[["id_nil", "nil", "municipio", "lon", "lat"]],
        src["parafarmacie"][["id_nil"]],
        src["popolazione"],
    )
    farmacie_scored = scoring.attach_farmacia_scores(f, nil_scoring)
    return nil_scoring, farmacie_scored


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="forza i dati locali")
    ap.add_argument("--out", default=str(DATA), help="cartella di output")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    source = "locale"
    if not args.local:
        try:
            src = fetch_remote()
            source = "remoto (open data)"
        except Exception as exc:  # noqa: BLE001
            print(f"[i] sorgente remota non disponibile ({type(exc).__name__}): uso i dati locali")
            src = load_local()
    else:
        src = load_local()

    nil_scoring, farmacie_scored = recompute(src)
    (out / "nil_scoring.csv").write_text(nil_scoring.to_csv(index=False), encoding="utf-8")
    farmacie_scored.to_csv(out / "farmacie_scored.csv", index=False)
    print(f"OK - sorgente: {source}")
    print(f"     {len(nil_scoring)} NIL e {len(farmacie_scored)} farmacie ricalcolati")
    print(f"     scritti in {out}/nil_scoring.csv e farmacie_scored.csv")


if __name__ == "__main__":
    main()
