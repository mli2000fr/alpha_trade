"""Sprint 13-A2: evidence BaoStock des distributions, sans mutation canonique.

Le facteur seul ne prouve jamais la nature d'une action. Les réponses brutes
sont gardées par symbole/année afin qu'un long backfill soit reprenable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

from database.router import get_market_engine
from modelFactory.cn_economic_preflight import (
    DEFAULT_CONFIG,
    POLICIES,
    SAFE_COLUMNS,
    audit_exposure,
    load_protocol,
    select_policies,
)
from modelFactory.cn_feature_panel import ROOT
from modelFactory.cn_global_ranking_aggregate import _find_run
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_CONFIG as RANK_CONFIG
from modelFactory.cn_global_ranking_walk_forward import DEFAULT_OUTPUT as RANK_OUTPUT
from modelFactory.cn_global_ranking_walk_forward import _sha
from modelFactory.cn_oracle_walk_forward import AUDIT_PATH
from service.baostock.client import BaoStockClient

OUTPUT = ROOT / "artifacts" / "cn" / "corporate_actions" / "sprint13a2"
TOLERANCE = Decimal("0.001")  # erreur relative maximale du rapprochement du facteur


def _decimal(value: Any) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def _day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _sha_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, default=str).encode()).hexdigest()


def classify(event: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Ex-date exacte + droits chiffrés + facteur réconcilié au cours brut.

    Une réponse vide, ambiguë, incomplète ou contradictoire reste UNRESOLVED.
    Les rights issues ne sont pas couverts par query_dividend_data.
    """
    base = {
        "corporate_action_id": event["corporate_action_id"],
        "instrument_id": event["instrument_id"],
        "ex_date": str(event["ex_date"]),
        "source_payload_hash": event["source_payload_hash"],
        "status": "UNRESOLVED",
        "reason": "no_exact_ex_date",
    }
    matches = [row for row in rows if _day(row.get("dividOperateDate")) == event["ex_date"]]
    if len(matches) != 1:
        base["reason"] = "ambiguous_ex_date" if matches else "no_exact_ex_date"
        return base
    row = matches[0]
    base["dividend_source_sha256"] = _sha_json(row)
    if row.get("code") != event["provider_symbol"]:
        base["reason"] = "symbol_mismatch"
        return base
    plan = _day(row.get("dividPlanDate"))
    record = _day(row.get("dividRegistDate"))
    pay = _day(row.get("dividPayDate"))
    if (
        plan is None
        or plan > event["ex_date"]
        or record is None
        or record >= event["ex_date"]
        or (pay and pay < event["ex_date"])
    ):
        base["reason"] = "invalid_event_dates"
        return base
    cash = _decimal(row.get("dividCashPsBeforeTax"))
    stock = _decimal(row.get("dividStocksPs"))
    reserve = _decimal(row.get("dividReserveToStockPs"))
    description = str(row.get("dividCashStock") or "")
    # BaoStock laisse le cash vide sur certains transferts exclusivement
    # en actions. Zéro est défendable seulement si les deux ratios d'actions
    # sont explicites, positifs ensemble, et le plan ne mentionne aucun cash.
    if (cash is None and stock is not None and reserve is not None
            and stock + reserve > 0 and "转" in description
            and "派" not in description and "元" not in description):
        cash = Decimal(0)
    # BaoStock omet souvent la réserve pour les distributions cash-only.
    # Ne convertir ce vide en zéro que lorsque le texte décrit uniquement
    # un cash dividend et que le ratio d'actions explicite vaut zéro.
    if (
        reserve is None
        and stock == 0
        and cash is not None
        and cash > 0
        and "派" in description
        and not any(token in description for token in ("送", "转"))
    ):
        reserve = Decimal(0)
    if any(value is None for value in (cash, stock)) or any(
        value is not None and value < 0 for value in (cash, stock, reserve)
    ):
        base["reason"] = "invalid_economic_terms"
        return base
    # Une réserve vide est traitée comme inconnue, jamais comme zéro.
    if reserve is None:
        base["reason"] = "reserve_ratio_missing"
        return base
    share = stock + reserve
    if cash == 0 and share == 0:
        base["reason"] = "zero_distribution"
        return base
    prior = _decimal(event.get("previous_close"))
    old_factor = _decimal(event.get("previous_factor_value"))
    new_factor = _decimal(event.get("factor_value"))
    if any(value is None or value <= 0 for value in (prior, old_factor, new_factor)) or prior <= cash:
        base["reason"] = "missing_or_invalid_price_factor"
        return base
    # Prix théorique ex-droit pour cash + actions gratuites/transfert.
    expected = prior * (Decimal(1) + share) / (prior - cash)
    observed = new_factor / old_factor
    error = abs(expected - observed) / expected
    base.update(
        {
            "cash_per_share_before_tax": str(cash),
            "share_ratio": str(share),
            "plan_date": str(plan),
            "record_date": str(record),
            "payment_date": str(pay) if pay else None,
            "prior_raw_close": str(prior),
            "expected_factor_ratio": str(expected),
            "observed_factor_ratio": str(observed),
            "factor_relative_error": str(error),
        }
    )
    if error > TOLERANCE:
        base["reason"] = "factor_terms_mismatch"
        return base
    base["status"] = "EVIDENCED_DISTRIBUTION"
    base["reason"] = "exact_ex_date_terms_and_factor_reconciled"
    base["kind"] = (
        "CASH_AND_SHARES" if cash > 0 and share > 0 else "CASH_DIVIDEND" if cash > 0 else "BONUS_OR_TRANSFER_SHARES"
    )
    # Ne pas prétendre que la donnée était observée historiquement par nous.
    return base


def load_events() -> tuple[list[dict[str, Any]], list[date], dict[int, date | None]]:
    engine = get_market_engine("CN_A", database_alias="cn_primary")
    try:
        with engine.connect() as conn:
            if conn.execute(text("SELECT DATABASE()")).scalar_one() != "alpha_trade_cn":
                raise RuntimeError("Sprint 13-A2 interdit hors alpha_trade_cn")
            rows = (
                conn.execute(
                    text("""
                SELECT a.corporate_action_id,a.instrument_id,a.ex_date,
                       a.factor_value,a.previous_factor_value,a.source_payload_hash,
                       p.provider_symbol,
                       (SELECT b.`close` FROM stock_bars_daily b
                        WHERE b.instrument_id=a.instrument_id AND b.market_code='CN_A'
                          AND b.`date`<a.ex_date ORDER BY b.`date` DESC LIMIT 1) previous_close
                FROM cn_corporate_actions a
                JOIN instrument_provider_symbols p ON p.instrument_id=a.instrument_id
                  AND p.provider='baostock' AND p.valid_from<=a.ex_date
                  AND (p.valid_to IS NULL OR p.valid_to>=a.ex_date)
                WHERE a.ex_date BETWEEN '2022-01-01' AND '2025-12-31'
                  AND a.classification_status='UNCLASSIFIED_FACTOR_EVENT'
                ORDER BY a.instrument_id,a.ex_date,a.corporate_action_id
            """)
                )
                .mappings()
                .all()
            )
            sessions = list(
                conn.execute(
                    text("""
                SELECT session_date FROM market_sessions WHERE market_code='CN_A'
                  AND session_status IN ('open','half_day','special')
                  AND session_date BETWEEN '2022-01-01' AND '2025-12-31'
                ORDER BY session_date
            """)
                ).scalars()
            )
            delistings = {
                int(key): value
                for key, value in conn.execute(
                    text("SELECT instrument_id,delisting_date FROM instruments WHERE market_code='CN_A'")
                )
            }
            expected = int(
                conn.execute(
                    text("""
                SELECT COUNT(*) FROM cn_corporate_actions WHERE ex_date BETWEEN
                  '2022-01-01' AND '2025-12-31' AND classification_status='UNCLASSIFIED_FACTOR_EVENT'
            """)
                ).scalar_one()
            )
    finally:
        engine.dispose()
    if len(rows) != expected or len({r["corporate_action_id"] for r in rows}) != expected:
        raise RuntimeError("Mapping BaoStock manquant/ambigu sur des événements CN")
    return [dict(row) for row in rows], sessions, delistings


def _cache_file(root: Path, symbol: str, year: int) -> Path:
    return root / "queries" / f"{symbol.replace('.', '_')}-{year}.json"


def _write_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def collect(
    *,
    root: Path = OUTPUT,
    max_new_groups: int | None = None,
    shard_index: int = 0,
    shard_count: int = 1,
    finalize_only: bool = False,
) -> dict[str, Any]:
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("Shard A2 invalide")
    events, sessions, delistings = load_events()
    groups = sorted({(str(e["provider_symbol"]), e["ex_date"].year) for e in events})
    fetched = 0
    selected_groups = [group for index, group in enumerate(groups) if index % shard_count == shard_index]
    if not finalize_only:
        with BaoStockClient() as client:
            for symbol, year in selected_groups:
                path = _cache_file(root, symbol, year)
                if path.exists():
                    continue
                if max_new_groups is not None and fetched >= max_new_groups:
                    break
                page = client.dividend_data(symbol, year)
                _write_atomic(
                    path,
                    {
                        "request": page.request_payload,
                        "retrieved_at": datetime.now(UTC).isoformat(),
                        "fields": page.fields,
                        "rows": page.rows,
                    },
                )
                fetched += 1
                if fetched % 100 == 0:
                    print(f"Sprint 13-A2: {fetched} nouvelles requêtes, {symbol}/{year}", flush=True)
    available = sum(_cache_file(root, symbol, year).exists() for symbol, year in groups)
    result: dict[str, Any] = {
        "event_count": len(events),
        "groups_total": len(groups),
        "groups_cached": available,
        "groups_new": fetched,
        "shard_index": shard_index,
        "shard_count": shard_count,
        "complete": available == len(groups),
        "source": "baostock.query_dividend_data(yearType=operate)",
        "read_only_cn_database": True,
        "serving_enabled": False,
    }
    if not result["complete"] or (shard_count > 1 and not finalize_only):
        progress_name = (
            "progress.json" if shard_count == 1 else
            f"progress-shard-{shard_index}-of-{shard_count}.json"
        )
        _write_atomic(root / progress_name, result)
        return result
    cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for symbol, year in groups:
        payload = json.loads(_cache_file(root, symbol, year).read_text(encoding="utf-8"))
        if payload.get("request") != {
            "method": "query_dividend_data",
            "symbol": symbol,
            "year": year,
            "yearType": "operate",
        }:
            raise RuntimeError(f"Cache BaoStock invalide: {symbol}/{year}")
        cache[(symbol, year)] = payload["rows"]
    evidence = [classify(event, cache[(event["provider_symbol"], event["ex_date"].year)]) for event in events]
    counts = Counter(item["status"] for item in evidence)
    reasons = Counter(item["reason"] for item in evidence)
    result.update(
        {
            "statuses": dict(counts),
            "reasons": dict(reasons),
            "factor_tolerance_relative": str(TOLERANCE),
            "evidence_sha256": _sha_json(evidence),
            "unresolved_events": counts["UNRESOLVED"],
            "resolved_events": counts["EVIDENCED_DISTRIBUTION"],
        }
    )
    # Le gate de 5 % n'est recalculé que sur une collecte exhaustive.
    unresolved_ids = {item["corporate_action_id"] for item in evidence if item["status"] == "UNRESOLVED"}
    dates: dict[int, list[date]] = defaultdict(list)
    for event in events:
        if event["corporate_action_id"] in unresolved_ids:
            dates[int(event["instrument_id"])].append(event["ex_date"])
    result["preflight"] = _audit_gate(dates, sessions, delistings)
    _write_atomic(root / "evidence.json", evidence)
    _write_atomic(root / "report.json", result)
    return result


def _audit_gate(
    dates: dict[int, list[date]], sessions: list[date], delistings: dict[int, date | None]
) -> dict[str, Any]:
    protocol = load_protocol(DEFAULT_CONFIG)
    from modelFactory import cn_global_ranking_walk_forward as runner

    rank_config_sha = _sha(RANK_CONFIG)
    rank_code_sha = _sha(Path(runner.__file__))
    audit_sha = _sha(AUDIT_PATH)
    totals = {name: {"full": 0, "unresolved_exposed": 0} for name in POLICIES}
    provenance = []
    for semester in protocol["test_semesters"]:
        item = _find_run(
            RANK_OUTPUT,
            horizon=20,
            semester=semester,
            model="lightgbm",
            config_sha=rank_config_sha,
            code_sha=rank_code_sha,
            audit_sha=audit_sha,
        )
        if item is None:
            raise RuntimeError(f"Prédictions OOS verrouillées absentes: {semester}")
        path, source = item
        frame = pd.read_parquet(path, columns=SAFE_COLUMNS)
        pool, masks = select_policies(frame, minimum=protocol["portfolio"]["min_oracle_pool_per_session"])
        provenance.append({"semester": semester, "predictions_sha256": source["predictions_sha256"]})
        for policy in POLICIES:
            selected = pool.loc[masks[policy], ["session_date", "instrument_id"]]
            audit = audit_exposure(selected, sessions=sessions, action_dates=dates, delistings=delistings)
            totals[policy]["full"] += audit["full_scheduled_path"]
            totals[policy]["unresolved_exposed"] += audit["action_exposed"]
    gate = protocol["preflight_gate"]["max_unclassified_action_exposure_fraction"]
    for values in totals.values():
        values["fraction"] = round(values["unresolved_exposed"] / values["full"], 6) if values["full"] else None
        values["pass_5pct"] = values["fraction"] is not None and values["fraction"] <= gate
    return {
        "gate_unchanged": gate,
        "policies": totals,
        "all_policies_pass": all(item["pass_5pct"] for item in totals.values()),
        "provenance": provenance,
        "candidate_level_not_filled_portfolio": True,
        "economic_go_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sprint 13-A2 : preuves distributions CN")
    parser.add_argument("--output-root", type=Path, default=OUTPUT)
    parser.add_argument("--max-new-groups", type=int)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--finalize-only", action="store_true")
    args = parser.parse_args()
    if args.max_new_groups is not None and args.max_new_groups < 1:
        parser.error("--max-new-groups doit être positif")
    result = collect(
        root=args.output_root,
        max_new_groups=args.max_new_groups,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
        finalize_only=args.finalize_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
