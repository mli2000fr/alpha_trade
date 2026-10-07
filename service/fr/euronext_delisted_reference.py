"""Collecte et audite l'historique public Euronext de titres radiés récents.

La page publique limite actuellement la période à environ deux ans. Le module
ne contourne pas cette limite : il reproduit la requête du navigateur, déchiffre
la réponse avec la clé publiée dans la page et compare les OHLC aux archives
EODHD. Aucun résultat n'est écrit dans les tables canoniques.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from service.fr.eodhd_backfill import _atomic_json

BASE_URL = "https://live.euronext.com"
DEFAULT_KEY = "24ayqVo7yJma"
FIELDS = ("open", "high", "low", "close")
MIC_CANDIDATES = ("XPAR", "ALXP", "XMLI")


def _evp_bytes_to_key(password: bytes, salt: bytes, length: int = 48) -> bytes:
    derived = b""
    previous = b""
    while len(derived) < length:
        previous = hashlib.md5(previous + password + salt).digest()  # noqa: S324
        derived += previous
    return derived[:length]


def decrypt_ajax(payload: dict[str, str], password: str) -> Any:
    """Déchiffre le format JSON CryptoJS AES employé par le site."""
    salt = bytes.fromhex(payload["s"])
    material = _evp_bytes_to_key(password.encode("ascii"), salt)
    decryptor = Cipher(
        algorithms.AES(material[:32]), modes.CBC(material[32:48])
    ).decryptor()
    clear = decryptor.update(base64.b64decode(payload["ct"])) + decryptor.finalize()
    padding = clear[-1]
    if not 1 <= padding <= 16 or clear[-padding:] != bytes([padding]) * padding:
        raise ValueError("padding AES Euronext invalide")
    return json.loads(clear[:-padding].decode("utf-8"))


def parse_page_settings(html: str, isin: str) -> dict[str, str]:
    matches = re.findall(
        r'<script type="application/json" data-drupal-selector="drupal-settings-json">(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not matches:
        raise ValueError("configuration Drupal Euronext absente")
    settings = json.loads(matches[-1])
    instrument = settings.get("custom", {}).get("instrument", {})
    if instrument.get("isin") != isin:
        raise ValueError(f"instrument Euronext inattendu pour {isin}")
    return {
        "product_data": instrument["product_data"],
        "mic": instrument["mic"],
        "name": instrument.get("name") or "",
        "key": settings.get("ajax_secure", {}).get("kye") or DEFAULT_KEY,
        "date_restriction": settings.get("custom", {}).get("date_restriction") or "",
    }


def discover_instrument(session: requests.Session, isin: str) -> dict[str, str]:
    errors = []
    for mic in MIC_CANDIDATES:
        url = f"{BASE_URL}/en/product/equities/{isin}-{mic}"
        response = session.get(url, timeout=60)
        if response.status_code != 200:
            errors.append(f"{mic}:HTTP_{response.status_code}")
            continue
        try:
            return {**parse_page_settings(response.text, isin), "page_url": response.url}
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{mic}:{exc}")
    raise ValueError(f"instrument Euronext introuvable {isin}: {'; '.join(errors)}")


def _number(value: str | None) -> float | None:
    if value is None:
        return None
    normalized = value.replace("\u00a0", "").replace(" ", "").replace(",", ".").strip()
    if not normalized or normalized == "-":
        return None
    if normalized.count(".") > 1:
        integer, decimal = normalized.rsplit(".", 1)
        normalized = integer.replace(".", "") + "." + decimal
    return float(normalized)


def parse_historical_html(html: str) -> dict[str, dict[str, float | int | None]]:
    """Lit les lignes du tableau HTML retourné par Euronext."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#AwlHistoricalPriceTable")
    if table is None:
        raise ValueError("table historique Euronext absente")
    records = {}
    for row in table.select("tbody tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.select("td")]
        if len(cells) < 6:
            continue
        parsed_day = datetime.strptime(cells[0], "%d/%m/%Y").date().isoformat()
        records[parsed_day] = {
            "open": _number(cells[1]),
            "high": _number(cells[2]),
            "low": _number(cells[3]),
            "close": _number(cells[4]),
            "volume": int(_number(cells[5]) or 0),
        }
    return records


def fetch_history(
    session: requests.Session,
    instrument: dict[str, str],
    *,
    start: str,
    end: str,
    maximum_sessions: int = 800,
) -> tuple[dict[str, dict], str]:
    url = f"{BASE_URL}/en/ajax/getHistoricalPricePopup/{instrument['product_data']}"
    response = session.post(
        url,
        data={"adjusted": "Y", "startdate": start, "enddate": end,
              "nbSession": str(maximum_sessions)},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "*/*"},
        timeout=90,
    )
    response.raise_for_status()
    encrypted = response.json()
    html = decrypt_ajax(encrypted, instrument["key"])
    if not isinstance(html, str):
        raise ValueError("réponse historique Euronext non textuelle")
    return parse_historical_html(html), hashlib.sha256(response.content).hexdigest()


def read_eodhd(path: Path) -> dict[str, dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return {row["date"]: row for row in json.load(stream)}


def audit_rows(reference: dict[str, dict], provider: dict[str, dict], *,
               tolerance_ratio: float = 0.001) -> dict:
    common = sorted(reference.keys() & provider.keys())
    exact_dates = []
    differences = []
    for day in common:
        reference_row = reference[day]
        provider_row = provider[day]
        day_differences = []
        for field in FIELDS:
            expected = reference_row.get(field)
            actual = provider_row.get(field)
            if expected is None or actual is None:
                day_differences.append({"field": field, "reason": "missing"})
                continue
            denominator = max(abs(float(expected)), 1e-12)
            ratio = abs(float(actual) - float(expected)) / denominator
            if ratio > tolerance_ratio:
                day_differences.append({"field": field, "euronext": expected,
                                        "eodhd": actual, "relative_difference": ratio})
        if day_differences:
            differences.append({"date": day, "fields": day_differences})
        else:
            exact_dates.append(day)
    return {
        "reference_rows": len(reference),
        "provider_rows": len(provider),
        "overlap_rows": len(common),
        "first_overlap": common[0] if common else None,
        "last_overlap": common[-1] if common else None,
        "corroborated_dates": exact_dates,
        "corroborated_rows": len(exact_dates),
        "difference_days": len(differences),
        "difference_examples": differences[:20],
        "tolerance_ratio": tolerance_ratio,
    }


def _write_normalized(path: Path, *, symbol: str, isin: str,
                      instrument: dict[str, str], rows: dict[str, dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = {
        "source": "EURONEXT_PUBLIC_HISTORICAL_PRICE",
        "symbol": symbol,
        "isin": isin,
        "instrument": instrument,
        "rows": [{"date": day, **values} for day, values in sorted(rows.items())],
    }
    with gzip.open(temporary, "wt", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
    temporary.replace(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_path(archive_root: Path, symbol: str) -> Path:
    key = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:16]
    metadata = json.loads((archive_root / "symbols" / f"{key}.json").read_text(encoding="utf-8"))
    return archive_root / metadata["payloads"]["eod"]["file"]


def collect(*, subset_path: Path, archive_root: Path, output: Path,
            cutoff: str | None = None, minimum_rows: int = 1,
            verify_tls: bool = True) -> dict:
    subset = json.loads(subset_path.read_text(encoding="utf-8"))
    end = date.today()
    default_start = end - timedelta(days=730)
    cutoff = cutoff or default_start.isoformat()
    candidates = [
        row for row in subset["symbols"]
        if row.get("provider_status_current") == "delisted"
        and row.get("status") == "CANDIDATE_REQUIRES_EXTERNAL_PROOFS"
        and row.get("isin_reported")
        and row.get("last_valid")
        and row["last_valid"] >= cutoff
    ]
    session = requests.Session()
    session.headers["User-Agent"] = "alpha-trade-research/1.0 (public Euronext audit)"
    session.verify = verify_tls
    if not verify_tls:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    results = []
    for row in candidates:
        result = {"symbol": row["symbol"], "isin": row["isin_reported"],
                  "provider_status": "delisted", "last_valid": row["last_valid"]}
        try:
            instrument = discover_instrument(session, row["isin_reported"])
            start = max(cutoff, instrument.get("date_restriction") or cutoff)
            reference, payload_hash = fetch_history(
                session, instrument, start=start, end=end.isoformat())
            normalized_path = output.parent / "normalized" / f"{row['symbol']}.json.gz"
            normalized_hash = _write_normalized(
                normalized_path, symbol=row["symbol"], isin=row["isin_reported"],
                instrument=instrument, rows=reference)
            provider = read_eodhd(archive_path(archive_root, row["symbol"]))
            audit = audit_rows(reference, provider)
            result.update({"status": "COMPLETED", "instrument": instrument,
                           "encrypted_payload_sha256": payload_hash,
                           "normalized_archive": str(normalized_path),
                           "normalized_archive_sha256": normalized_hash, **audit})
            if audit["corroborated_rows"] < minimum_rows:
                result["status"] = "INSUFFICIENT_OVERLAP"
        except Exception as exc:  # résultat exhaustif, erreur conservée par titre
            result.update({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
        results.append(result)
    covered = [row for row in results if row["status"] == "COMPLETED"]
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "EURONEXT_PUBLIC_HISTORICAL_PRICE",
        "source_url": f"{BASE_URL}/en/data",
        "tls_verified": verify_tls,
        "period": {"from": cutoff, "to": end.isoformat()},
        "candidate_delisted_symbols": len(candidates),
        "covered_delisted_symbols": len(covered),
        "coverage_ratio_of_candidate_subset": len(covered) / len(candidates) if candidates else 0.0,
        "threshold": {"minimum_delisted_symbols": 20, "minimum_ratio": 0.10},
        "threshold_passed": len(covered) >= 20 and len(covered) / len(candidates) >= 0.10,
        "results": results,
        "canonical_writes_performed": False,
    }
    _atomic_json(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", type=Path, default=Path(
        "artifacts/fr/eodhd/backfill_2016/sprint5_subset_audit.json"))
    parser.add_argument("--archive-root", type=Path, default=Path(
        "artifacts/fr/eodhd/backfill_2016"))
    parser.add_argument("--output", type=Path, default=Path(
        "artifacts/fr/euronext_delisted_reference/report.json"))
    parser.add_argument("--cutoff")
    parser.add_argument("--minimum-rows", type=int, default=1)
    parser.add_argument(
        "--insecure-tls", action="store_true",
        help="POC uniquement : désactive la validation TLS si certifi ne connaît pas la CA locale",
    )
    args = parser.parse_args()
    report = collect(subset_path=args.subset, archive_root=args.archive_root,
                     output=args.output, cutoff=args.cutoff,
                     minimum_rows=args.minimum_rows,
                     verify_tls=not args.insecure_tls)
    print(json.dumps({key: report[key] for key in (
        "candidate_delisted_symbols", "covered_delisted_symbols",
        "coverage_ratio_of_candidate_subset", "threshold_passed")},
        ensure_ascii=False))


if __name__ == "__main__":
    main()





