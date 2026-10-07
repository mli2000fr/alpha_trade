"""Qualifie séparément règles fiscales, données CA et coûts FR, sans promotion."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
from bs4 import BeautifulSoup

from common.market_calendar import get_market_calendar
from modelFactory.fr_fold7_rebuild import sha, write_json
from service.fr.corporate_actions_audit import _rows
from service.fr.execution_costs import load_cost_profile
from service.fr.universe_contract_6a import ROOT
from service.fr.universe_liquidity_6b import _load_symbol_bars
from service.fr.yahoo_price_reference_pilot import verified_tls_context

SOURCES = {
    "tax_rates_pre_april_2025": "https://bofip.impots.gouv.fr/bofip/7575-PGP.html/identifiant=BOI-TCA-FIN-10-30-20170503",
    "tax_rates_from_april_2025": "https://bofip.impots.gouv.fr/bofip/7575-PGP.html/identifiant=BOI-TCA-FIN-10-30-20250528",
    "issuer_list_2024": "https://bofip.impots.gouv.fr/bofip/9789-PGP.html/identifiant=BOI-ANNX-000467-20231220",
    "issuer_list_2025": "https://bofip.impots.gouv.fr/bofip/9789-PGP.html/identifiant=BOI-ANNX-000467-20241223",
}


def ttf_rate(acquisition_settlement_date: date) -> Decimal:
    """Scope limited to the historical comparison 2024/2025, not current law."""
    if not date(2024, 1, 1) <= acquisition_settlement_date <= date(2025, 12, 31):
        raise ValueError("Calendrier fiscal hors périmètre qualifié 2024/2025")
    return Decimal("0.003") if acquisition_settlement_date < date(2025, 4, 1) else Decimal("0.004")


def ttf_accrual(settlement_date: date, net_acquired_quantity: int, average_purchase_price: Decimal,
                *, issuer_liability: bool | None) -> Decimal:
    """Unrounded model accrual, NOT broker's aggregated statutory declaration.

    Caller supplies net quantity per client/PSI/ISIN/settlement group, excluding
    exempt trades. Average acquisition price is rounded upward to one cent.
    """
    rate = ttf_rate(settlement_date)
    if type(net_acquired_quantity) is not int or net_acquired_quantity < 0:
        raise ValueError("Quantité nette entière non négative attendue")
    if not average_purchase_price.is_finite() or average_purchase_price <= 0:
        raise ValueError("Prix moyen hors frais invalide")
    if issuer_liability is not True and issuer_liability is not False:
        raise ValueError("Assujettissement inconnu : taxe non imputable")
    if issuer_liability is False:
        return Decimal(0)
    return Decimal(net_acquired_quantity) * average_purchase_price.quantize(Decimal("0.01"), rounding=ROUND_CEILING) * rate


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in value if not unicodedata.combining(c)))


def parse_issuer_list(html: str) -> list[str]:
    body = BeautifulSoup(html, "html.parser").select_one("article.bofip-content .field--name-body")
    if body is None:
        raise ValueError("Corps BOFiP introuvable")
    names = [li.get_text(" ", strip=True) for li in body.select("ul > li")]
    if not 50 <= len(names) <= 200 or len(set(map(normalize_name, names))) != len(names):
        raise ValueError("Liste fiscale absente, ambiguë ou format inattendu")
    return names


def dividend_check(event: dict) -> list[str]:
    reasons = []
    amount = event.get("unadjustedValue")
    try:
        if amount is None or not math.isfinite(float(amount)) or float(amount) < 0:
            reasons.append("UNADJUSTED_AMOUNT_INVALID_OR_MISSING")
    except (TypeError, ValueError):
        reasons.append("UNADJUSTED_AMOUNT_INVALID_OR_MISSING")
    if event.get("currency") != "EUR":
        reasons.append("CURRENCY_UNKNOWN_OR_FX_REQUIRED")
    payment = event.get("paymentDate")
    try:
        if not payment or date.fromisoformat(payment) < date.fromisoformat(event["date"]):
            reasons.append("PAYMENT_DATE_MISSING_OR_BEFORE_EX_DATE")
    except (ValueError, TypeError):
        reasons.append("PAYMENT_DATE_INVALID")
    # Declaration availability is required for predictive features, not for
    # retrospective realized cash accounting; do not invent it when absent.
    return reasons


def run(preflight: Path, output: Path, *, fetch_tax_sources: bool = True) -> dict:
    preflight, output = preflight.resolve(), output.resolve()
    previous = json.loads((preflight / "report.json").read_text(encoding="utf-8"))
    score_path = preflight / "decision_candidates_scored.parquet"
    if sha(score_path) != previous["causal_research_rescoring"]["scores_sha256"]:
        raise ValueError("Candidats modifiés depuis le préflight")
    candidates = pd.read_parquet(score_path)
    if candidates.decision_session_date.gt("2025-12-31").any():
        raise ValueError("2026 est réservée")
    output.mkdir(parents=True, exist_ok=False)
    observed_at = datetime.now(UTC).isoformat()
    evidence_sources, lists = {}, {}
    if fetch_tax_sources:
        context = verified_tls_context()
        for name, url in SOURCES.items():
            with urlopen(url, context=context, timeout=45) as response:
                if response.status != 200:
                    raise ValueError(f"Source fiscale inaccessible {name}")
                raw = response.read()
            path = output / f"{name}.html"
            path.write_bytes(raw)
            text = raw.decode("utf-8")
            if "BOI-" not in text or "transactions" not in text.lower():
                raise ValueError("Source fiscale inattendue")
            if name.startswith("issuer_list"):
                lists[int(name[-4:])] = parse_issuer_list(text)
            evidence_sources[name] = {"url": url, "sha256": sha(path), "observed_at": observed_at,
                                     "historical_publication_backdated": False}
        old = BeautifulSoup((output / "tax_rates_pre_april_2025.html").read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
        new = BeautifulSoup((output / "tax_rates_from_april_2025.html").read_text(encoding="utf-8"), "html.parser").get_text(" ", strip=True)
        if not re.search(r"0,3\s*%", old) or not re.search(r"0,4\s*%", new) or not re.search(r"avril\s+2025", new):
            raise ValueError("Taux/date fiscaux non retrouvés dans les preuves")

    archive = ROOT / "artifacts/fr/eodhd/backfill_2016"
    calendar = get_market_calendar("FR_EQ")
    end = date.fromisoformat(candidates.decision_session_date.max()) + timedelta(days=30)
    sessions = [s.session_date.isoformat() for s in calendar.sessions(date.fromisoformat(candidates.decision_session_date.min()), end) if s.is_open]
    indices = {day: i for i, day in enumerate(sessions)}
    records, tax_links, event_records, payload_hashes = [], [], [], {}
    for symbol, frame in candidates.groupby("provider_symbol", sort=True):
        import hashlib
        key = hashlib.sha256(symbol.encode()).hexdigest()[:16]
        meta_path = archive / "symbols" / f"{key}.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["status"] != "COMPLETED" or meta["window"][1] < sessions[-1]:
            raise ValueError(f"Archive insuffisante {symbol}")
        bars = _load_symbol_bars(archive, symbol)
        dividends, splits = _rows(archive, meta, "div"), _rows(archive, meta, "splits")
        payload_hashes[symbol] = {kind: meta["payloads"][kind]["sha256"] for kind in ("eod", "div", "splits")}
        for year in sorted({int(d[:4]) for d in frame.decision_session_date}):
            name = meta["record"]["Name"]
            matches = [n for n in lists.get(year, []) if normalize_name(n) == normalize_name(name)]
            tax_links.append({"symbol": symbol, "isin": meta["record"].get("Isin"), "year": year, "provider_name": name,
                              "matched_official_name": matches[0] if len(matches) == 1 else None,
                              "status": "NAME_MATCH_REQUIRES_ISIN_AND_LEGAL_SCOPE_REVIEW" if len(matches) == 1 else "UNKNOWN_NOT_TAX_EXEMPT",
                              "issuer_liability": None})
        for kind, events in (("DIVIDEND", dividends), ("SPLIT", splits)):
            for event in events:
                if frame.decision_session_date.min() <= event["date"] <= sessions[-1]:
                    event_records.append({"symbol": symbol, "kind": kind, "event": event,
                                          "provider_checks": dividend_check(event) if kind == "DIVIDEND" else ["SPLIT_REQUIRES_OFFICIAL_RECONCILIATION"],
                                          "official_verified": False})
        for row in frame.itertuples():
            i = indices[row.decision_session_date]
            exit_day = sessions[i + 5]
            path_days = sessions[i:i + 6]
            missing = [day for day in path_days if day not in bars or bars[day]["volume"] <= 0
                       or any(not math.isfinite(bars[day][f]) or bars[day][f] <= 0 for f in ("open", "high", "low", "close"))]
            # Holding starts AFTER opening on the entry ex-date: no dividend
            # entitlement for that date. Holding includes exit day before close.
            divs = [d for d in dividends if row.decision_session_date < d["date"] <= exit_day]
            split_events = [s for s in splits if row.decision_session_date < s["date"] <= exit_day]
            invalid = [reason for d in divs for reason in dividend_check(d)]
            state = "BLOCKED_PRICE_PATH" if missing else "BLOCKED_SPLIT" if split_events else "BLOCKED_DIVIDEND_FIELDS" if invalid else "PROVIDER_EVENT_FIELDS_COMPLETE_REQUIRES_OFFICIAL_REVIEW" if divs else "NO_PROVIDER_EVENT_DECLARED_NOT_PROOF_OF_ABSENCE"
            records.append({"fold": row.fold, "research_uid": row.research_uid, "symbol": symbol,
                            "entry_session": row.decision_session_date, "exit_session": exit_day,
                            "missing_price_days": missing, "dividend_events": len(divs), "split_events": len(split_events),
                            "dividend_field_reasons": invalid, "provider_state": state,
                            "economic_return_ready": False, "historical_pit_verified": False})
    pd.DataFrame(records).to_parquet(output / "holding_path_qualification.parquet", index=False)
    pd.DataFrame(tax_links).to_parquet(output / "tax_issuer_candidates.parquet", index=False)
    write_json(output / "corporate_events.json", {"events": event_records})
    result = {"observed_at": observed_at, "scope": "FR_EQ_2024_2025_LONG_ONLY", "candidate_paths": len(records),
              "symbols": int(candidates.provider_symbol.nunique()), "path_states": dict(Counter(r["provider_state"] for r in records)),
              "tax_matching_states": dict(Counter(r["status"] for r in tax_links)),
              "tax_rule_state": "OFFICIAL_RATE_RULES_ARCHIVED" if fetch_tax_sources else "NOT_COLLECTED",
              "tax_rates": [{"from": "2024-01-01", "to": "2025-03-31", "rate": "0.003"}, {"from": "2025-04-01", "to": "2025-12-31", "rate": "0.004"}],
              "tax_rate_date_basis": "acquisition_settlement_date_not_signal_date",
              "tax_instrument_scope_state": "UNQUALIFIED_NAME_LINKS_ONLY",
              "commission_state": "BLOCKED_BROKER_TARIFF_NOT_SELECTED", "spread_slippage_state": "NO_HISTORICAL_QUOTES_OR_FILLS_EVIDENCE",
              "corporate_actions_state": "PROVIDER_CHECKS_ONLY_NOT_OFFICIAL_ECONOMIC_QUALIFICATION",
              "sources": evidence_sources, "archive_payload_hashes": payload_hashes,
              "preflight_report_sha256": sha(preflight / "report.json"), "implementation_sha256": sha(Path(__file__)),
              "verdict": "PARTIAL_QUALIFICATION_ECONOMIC_REPLAY_STILL_BLOCKED", "net_pnl": None,
              "canonical_writes": False, "models_refit": 0, "confirmation_2026_evaluated": False}
    cost_path = ROOT / "config/markets/fr_execution_research_v1.yaml"
    if cost_path.exists():
        cost_profile = load_cost_profile(cost_path)
        result.update(commission_state="USER_CONFIGURED_GENERIC_ASSUMPTION_NOT_BROKER_TARIFF",
                      spread_slippage_state="CONFIGURABLE_ASSUMPTIONS_NO_QUOTES_OR_FILLS",
                      cost_scenario_state="READY_FOR_ASSUMED_RESEARCH_NOT_EMPIRICALLY_QUALIFIED",
                      cost_profile={"path": str(cost_path), "sha256": sha(cost_path), "parameters": cost_profile})
    write_json(output / "report.json", result)
    return result
