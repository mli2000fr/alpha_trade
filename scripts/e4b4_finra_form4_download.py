"""E4-B4-A — downloader SEC Form 4 (insider transactions), échantillon 20 symboles.

Flux :
  1. ticker -> CIK (service.sec.clientEdgar.ticker_to_cik)
  2. GET /submissions/CIK{xxxx}.json -> filings.recent (1000 récents) + filings.files (pagination)
  3. Sélectionner les Form 4 / 4-A avec filingDate dans [2022-01-01, 2026-05-29]
  4. Récupérer form4.xml (Archives/edgar/data/{cik}/{accession_nodash}/form4.xml)
  5. Parser les transactions : transactionCode, transactionDate, transactionShares,
     transactionPricePerShare, sharesOwnedFollowingTransaction,
     transactionAcquiredDisposedCode, rptOwnerName

PIT : filingDate (date de dépôt SEC) = date où l'info est publique.

Cache local + reprise : chaque (symbole, accession) traité est sauvegardé ; re-run ne
refait que les absents.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

from service.sec.clientEdgar import ticker_to_cik

SAMPLE = Path("artifacts/models/oracle/e4b4_sample20.txt")
OUT = Path("artifacts/sec_cache/form4_20symbols.parquet")
STATE = Path("artifacts/sec_cache/form4_20symbols_done.json")
CACHE_DIR = Path("artifacts/sec_cache/form4_xml")

WIN_START = "2022-01-01"
WIN_END = "2026-05-29"

UA = {"User-Agent": "AlphaTradeML/1.0 (alphatrade@example.com)"}
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{filename}"
MIN_INTERVAL = 0.16  # ~6 req/s, marge sous la limite SEC 10/s
TIMEOUT = 60
MAX_RETRIES = 5

_session = requests.Session()
_session.headers.update(UA)


def _sleep() -> None:
    time.sleep(MIN_INTERVAL)


def _get(url: str, retries: int = MAX_RETRIES) -> requests.Response:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            r = _session.get(url, timeout=TIMEOUT)
            if r.status_code in (429, 500, 502, 503, 504):
                last_err = RuntimeError(f"HTTP {r.status_code}")
                time.sleep(3.0 * (attempt + 1) + 2.0)
                continue
            return r
        except requests.RequestException as e:
            last_err = e
            time.sleep(3.0 * (attempt + 1) + 2.0)
    raise RuntimeError(f"echec apres {retries} tentatives: {last_err}")


def fetch_submissions(cik: str) -> dict:
    r = _get(SUBMISSIONS_URL.format(cik=cik))
    r.raise_for_status()
    return r.json()


def all_filings(data: dict) -> list[dict]:
    """Concatène les 1000 récents + les fichiers de pagination historiques."""
    rows: list[dict] = []
    rec = data.get("filings", {}).get("recent", {})
    n = len(rec.get("form", []))
    for i in range(n):
        rows.append({
            "form": rec["form"][i],
            "filingDate": rec["filingDate"][i],
            "accessionNumber": rec["accessionNumber"][i],
            "primaryDocument": rec["primaryDocument"][i] if i < len(rec.get("primaryDocument", [])) else None,
        })
    # pagination (fichiers historiques)
    files = data.get("filings", {}).get("files", [])
    for f in files:
        url = f"https://data.sec.gov/submissions/{f['name']}"
        r = _get(url)
        r.raise_for_status()
        fd = r.json()
        fr = fd.get("recent", {})
        m = len(fr.get("form", []))
        for i in range(m):
            rows.append({
                "form": fr["form"][i],
                "filingDate": fr["filingDate"][i],
                "accessionNumber": fr["accessionNumber"][i],
                "primaryDocument": fr["primaryDocument"][i] if i < len(fr.get("primaryDocument", [])) else None,
            })
        _sleep()
    return rows


def fetch_form4_xml(cik: str, accession: str, primary_doc: str | None = None) -> str:
    acc_clean = accession.replace("-", "")
    # essayer d'abord le document primaire (gère wk-form4_*.xml des filers Workiva)
    if primary_doc:
        filename = primary_doc.split("/")[-1]  # garde la fin du chemin (ex: wk-form4_xxx.xml)
        url = ARCHIVE_URL.format(cik=cik, acc=acc_clean, filename=filename)
        r = _get(url)
        if r.status_code == 200 and r.text and not r.text.startswith("<Error>"):
            return r.text
    # fallback: form4.xml standard
    url = ARCHIVE_URL.format(cik=cik, acc=acc_clean, filename="form4.xml")
    r = _get(url)
    if r.status_code == 404:
        return ""
    r.raise_for_status()
    return r.text


def parse_transactions(xml: str) -> list[dict]:
    """Extrait les transactions du form4.xml."""
    if not xml:
        return []
    # nonDerivativeTransactions / derivativeTransactions
    blocks = re.findall(r"<(?:nonDerivative|derivative)Transaction[s]?>(.*?)</(?:nonDerivative|derivative)Transaction[s]?>", xml, re.S)
    out = []
    for blk in blocks:
        def val(tag):
            """Extrait <tag><value>X</value> ou <tag attr>X</tag> (premier contenu utile)."""
            m = re.search(rf"<{tag}[^>]*>\s*<value>(.*?)</value>", blk, re.S)
            if m:
                return m.group(1).strip()
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", blk, re.S)
            if m:
                inner = m.group(1).strip()
                # retire les balises footnoteId imbriquées
                inner = re.sub(r"<[^>]+>", "", inner).strip()
                return inner if inner else None
            return None
        code = val("transactionCode")
        tdate = val("transactionDate")
        shares = val("transactionShares")
        price = val("transactionPricePerShare")
        owned = val("sharesOwnedFollowingTransaction")
        acqdisp = val("transactionAcquiredDisposedCode")
        out.append({
            "transaction_code": code,
            "transaction_date": tdate,
            "shares": _num(shares),
            "price_per_share": _num(price),
            "shares_owned_after": _num(owned),
            "acq_disposed_code": acqdisp,
        })
    return out


def _num(x):
    if x is None:
        return None
    try:
        return float(x.replace(",", ""))
    except ValueError:
        return None


def main() -> None:
    syms = [s.strip().upper() for s in SAMPLE.read_text(encoding="utf-8").splitlines() if s.strip()]
    print(f"échantillon: {len(syms)} symboles")

    done = {}
    if STATE.exists():
        done = json.loads(STATE.read_text(encoding="utf-8"))
    frames = []
    if OUT.exists():
        frames.append(pd.read_parquet(OUT))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    for sym in syms:
        sym_done = done.get(sym, [])
        try:
            cik = ticker_to_cik(sym)
        except Exception as e:
            print(f"  {sym}: CIK erreur {e}")
            continue
        try:
            data = fetch_submissions(cik)
            filings = all_filings(data)
        except Exception as e:
            print(f"  {sym}: submissions erreur {e}")
            continue
        form4 = [f for f in filings if f["form"] in ("4", "4/A")
                 and WIN_START <= f["filingDate"] <= WIN_END]
        print(f"  {sym} (CIK {cik}): {len(form4)} Form 4 dans fenêtre")
        n_new = 0
        for f in form4:
            acc = f["accessionNumber"]
            if acc in sym_done:
                continue
            try:
                xml = fetch_form4_xml(cik, acc, f.get("primaryDocument"))
            except Exception as e:
                print(f"    !! {sym} {acc}: {type(e).__name__} — pause 30s puis abandon du symbole (reprise au prochain run)")
                time.sleep(30)
                break
            txs = parse_transactions(xml)
            for tx in txs:
                all_rows.append({
                    "symbol": sym,
                    "filing_date": f["filingDate"],
                    "accession": acc,
                    **tx,
                })
            sym_done.append(acc)
            n_new += 1
            _sleep()
        done[sym] = sym_done
        STATE.write_text(json.dumps(done), encoding="utf-8")
        if n_new:
            # checkpoint incrémental
            df = pd.DataFrame(all_rows)
            frames.append(df)
            all_rows = []
            combined = pd.concat(frames, ignore_index=True).drop_duplicates(
                ["symbol", "accession", "transaction_date", "shares", "price_per_share"])
            combined.to_parquet(OUT, index=False)
            print(f"    +{n_new} nouveaux -> total {len(combined):,} transactions | {OUT}")
            frames = [combined]

    # final
    if all_rows:
        frames.append(pd.DataFrame(all_rows))
    if frames:
        df = pd.concat(frames, ignore_index=True).drop_duplicates(
            ["symbol", "accession", "transaction_date", "shares", "price_per_share"])
        df.to_parquet(OUT, index=False)
        print(f"\ntotal: {len(df):,} transactions | {df['symbol'].nunique()} symboles | {OUT}")
        print("codes:", df["transaction_code"].value_counts().to_dict())
        print("fenetre filing:", df["filing_date"].min(), "->", df["filing_date"].max())


if __name__ == "__main__":
    main()
