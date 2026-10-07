"""Sprint 7-A : panel France price-only de recherche, sans écriture canonique.

Fenêtres en séances XPAR, masques explicites et disponibilité conservatrice J+1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from common.market_calendar import get_market_calendar
from service.fr.universe_contract_6a import ROOT, _atomic_json, _fingerprint, _sha256
from service.fr.universe_liquidity_6b import _iter_manifest, _load_symbol_bars
from service.fr.universe_reference_6c import resolve_path

LOGGER = logging.getLogger(__name__)
RETURN_HORIZONS = (1, 3, 5, 10, 20, 60)
FEATURE_SPECS = {
    **{
        f"return_{h}": {
            "formula": f"C(J)/C(J-{h})-1, {h + 1} clôtures consécutives valides",
            "window_sessions": h + 1,
            "unit": "ratio",
        }
        for h in RETURN_HORIZONS
    },
    **{
        f"sma{w}_distance": {"formula": f"C(J)/moyenne(C,{w})-1", "window_sessions": w, "unit": "ratio"}
        for w in (20, 50, 200)
    },
    "atr20_pct": {
        "formula": "moyenne(max(H-L,abs(H-Cprev),abs(L-Cprev)),20)/C",
        "window_sessions": 21,
        "unit": "ratio",
    },
    "realized_vol20": {
        "formula": "écart-type échantillon(rendements quotidiens,20)*sqrt(252)",
        "window_sessions": 21,
        "unit": "annualized_ratio",
    },
    "range20_position": {"formula": "(C-min(L,20))/(max(H,20)-min(L,20))", "window_sessions": 20, "unit": "ratio"},
    "volume_ratio20": {"formula": "V/moyenne(V,20)", "window_sessions": 20, "unit": "ratio"},
    "traded_value_mean20_eur": {"formula": "moyenne(C*V,20), proxy fournisseur", "window_sessions": 20, "unit": "EUR"},
    "overnight_gap": {"formula": "O(J)/C(J-1)-1", "window_sessions": 2, "unit": "ratio"},
    "position_52w": {"formula": "(C-min(L,252))/(max(H,252)-min(L,252))", "window_sessions": 252, "unit": "ratio"},
    "intraday_return": {"formula": "C/O-1", "window_sessions": 1, "unit": "ratio"},
    "intraday_range": {"formula": "(H-L)/C", "window_sessions": 1, "unit": "ratio"},
}
NUMERIC_FEATURES = tuple(FEATURE_SPECS)
CORE20_FEATURES = (
    "return_20",
    "atr20_pct",
    "realized_vol20",
    "range20_position",
    "volume_ratio20",
    "traded_value_mean20_eur",
    "overnight_gap",
)


def load_profile(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if (raw.get("schema_version"), raw.get("profile"), raw.get("market_code"), raw.get("database_alias")) != (
        1,
        "fr_price_v1",
        "FR_EQ",
        "fr_primary",
    ):
        raise ValueError("Profil FR price-only incompatible")
    if tuple(raw.get("return_horizons", [])) != RETURN_HORIZONS:
        raise ValueError("Horizons FR non conformes")
    if (
        raw.get("availability_basis") != "RESEARCH_J1_XPAR_OPEN"
        or raw.get("price_adjustment_mode") != "raw_sprint5_split_histories_excluded"
    ):
        raise ValueError("Disponibilité ou prix FR non conformes")
    if any(
        raw.get(key)
        for key in (
            "benchmark_features_enabled",
            "sector_features_enabled",
            "fundamental_features_enabled",
            "sentiment_features_enabled",
            "canonical_writes_enabled",
        )
    ):
        raise ValueError("7-A n'accepte que le profil prix sans écriture canonique")
    if int(raw.get("min_cross_section", 0)) < 20 or int(raw.get("min_ready_rows", 0)) < 1000:
        raise ValueError("Gates du panel FR insuffisants")
    return raw


def compute_symbol_features(bars: pd.DataFrame, sessions: list[date]) -> pd.DataFrame:
    """Reindexation officielle : aucun pont au-dessus d'une séance absente."""
    required = {"source_session_date", "open", "high", "low", "close", "volume"}
    if required - set(bars):
        raise ValueError("Barres FR incomplètes")
    frame = bars.copy()
    frame["source_session_date"] = pd.to_datetime(frame["source_session_date"])
    if frame["source_session_date"].duplicated().any():
        raise ValueError("Barre FR dupliquée")
    index = pd.DatetimeIndex(sessions, name="source_session_date")
    if not frame["source_session_date"].isin(index).all():
        raise ValueError("Barre FR hors calendrier XPAR")
    frame = frame.set_index("source_session_date").reindex(index)
    fields = ["open", "high", "low", "close", "volume"]
    values = frame[fields].apply(pd.to_numeric, errors="coerce")
    present = values.notna().any(axis=1)
    valid = np.isfinite(values).all(axis=1) & values.gt(0).all(axis=1)
    valid &= values["high"].ge(values[["open", "close"]].max(axis=1)) & values["low"].le(
        values[["open", "close"]].min(axis=1)
    )
    if (present & ~valid).any():
        raise ValueError("Barre invalide malgré admission Sprint 5/6-B")
    values = values.where(valid)
    opened, high, low, close, volume = (values[name] for name in fields)
    result = pd.DataFrame(index=index)
    previous = close.shift(1)
    daily_return = close / previous - 1
    for h in RETURN_HORIZONS:
        complete = valid.rolling(h + 1, min_periods=h + 1).sum().eq(h + 1)
        result[f"return_{h}"] = (close / close.shift(h) - 1).where(complete)
    for window in (20, 50, 200):
        result[f"sma{window}_distance"] = close / close.rolling(window, min_periods=window).mean() - 1
    true_range = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1).max(
        axis=1, skipna=False
    )
    result["atr20_pct"] = true_range.rolling(20, min_periods=20).mean() / close
    result["realized_vol20"] = daily_return.rolling(20, min_periods=20).std(ddof=1) * np.sqrt(252)
    for window, name in ((20, "range20_position"), (252, "position_52w")):
        bottom = low.rolling(window, min_periods=window).min()
        width = high.rolling(window, min_periods=window).max() - bottom
        result[name] = (close - bottom) / width.replace(0, np.nan)
    result["volume_ratio20"] = volume / volume.rolling(20, min_periods=20).mean()
    result["traded_value_mean20_eur"] = (close * volume).rolling(20, min_periods=20).mean()
    result["overnight_gap"] = opened / previous - 1
    result["intraday_return"] = close / opened - 1
    result["intraday_range"] = (high - low) / close
    return result[list(NUMERIC_FEATURES)].replace([np.inf, -np.inf], np.nan).reset_index()


def assemble_panel(
    candidates: pd.DataFrame, features: pd.DataFrame, identities: dict, session_times: dict, profile: dict
) -> pd.DataFrame:
    panel = candidates.merge(features, on=["provider_symbol", "source_session_date"], how="left", validate="one_to_one")
    panel["research_uid"] = panel["provider_symbol"].map(lambda s: identities.get(s, {}).get("research_uid"))
    if panel["research_uid"].isna().any():
        raise ValueError("Identité de recherche absente")
    panel["source_available_at"] = panel["decision_session_date"].map(lambda d: session_times[d]["open"])
    panel["decision_at"] = panel["source_available_at"]
    panel["max_input_available_at"] = panel["source_available_at"]
    if not (panel["source_session_date"] < panel["decision_session_date"]).all():
        raise ValueError("Fuite PIT : barre courante ou future")
    if any(session_times[r.decision_session_date]["previous"] != r.source_session_date for r in panel.itertuples()):
        raise ValueError("La disponibilité FR doit être la prochaine séance XPAR")
    panel["market_code"] = "FR_EQ"
    panel["availability_basis"] = "RESEARCH_J1_HYPOTHESIS_NOT_VERIFIED_PUBLICATION"
    panel["sector_state"] = "UNKNOWN"
    panel["instrument_id"] = pd.Series(pd.NA, index=panel.index, dtype="Int64")
    for feature in NUMERIC_FEATURES:
        panel[f"{feature}_missing"] = panel[feature].isna().astype("int8")
    panel["mask_price20"] = panel[list(CORE20_FEATURES)].notna().all(axis=1)
    panel["mask_all_features"] = panel[list(NUMERIC_FEATURES)].notna().all(axis=1)
    panel["cross_section_count"] = panel.groupby("decision_session_date")["provider_symbol"].transform("size")
    panel["feature_complete_count"] = panel.groupby("decision_session_date")["mask_all_features"].transform("sum")
    panel["mask_cross_section"] = panel["feature_complete_count"] >= int(profile["min_cross_section"])
    panel["research_ready"] = panel["mask_all_features"] & panel["mask_cross_section"]
    panel = panel.sort_values(["decision_session_date", "research_uid", "provider_symbol"], kind="stable").reset_index(
        drop=True
    )
    if panel.duplicated(["decision_session_date", "research_uid"]).any():
        raise ValueError("Identité dupliquée dans la cross-section FR")
    return panel


def _coverage(frame: pd.DataFrame) -> dict:
    return {
        name: {
            "known": int(frame[name].notna().sum()),
            "missing": int(frame[name].isna().sum()),
            "missing_fraction": round(float(frame[name].isna().mean()), 8),
        }
        for name in NUMERIC_FEATURES
    }


def build_panel(*, start: date, end: date, profile_path: Path, output_root: Path) -> dict:
    if end < start or start < date(2018, 1, 1):
        raise ValueError("Période de recherche FR invalide")
    profile = load_profile(profile_path)
    liquidity_path = resolve_path(profile["source_liquidity_report"])
    reference_path = resolve_path(profile["source_reference_report"])
    liquidity = json.loads(liquidity_path.read_text(encoding="utf-8"))
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    if (
        liquidity["verdict"] != "GO_6B_TRAINING_UNIVERSE"
        or reference["verdict"] != "GO_6C_RESEARCH_PRICE_ONLY"
        or reference["liquidity_run_id"] != liquidity["liquidity_run_id"]
    ):
        raise ValueError("Sources 6-B/6-C incompatibles")
    if reference.get("canonical_writes_performed") is not False:
        raise ValueError("Source de recherche incompatible")
    snapshot_path = resolve_path(liquidity["snapshot_path"])
    identity_path = Path(reference["files"]["identities"]["path"])
    if (
        _sha256(snapshot_path) != liquidity["snapshot_sha256"]
        or _sha256(identity_path) != reference["files"]["identities"]["sha256"]
    ):
        raise ValueError("Hash source FR divergent")
    snapshots = list(_iter_manifest(snapshot_path))
    if len(snapshots) != int(liquidity["snapshot_count"]):
        raise ValueError("Nombre de snapshots 6-B divergent")
    expected_reference_source = _fingerprint(
        {
            "manifest": liquidity["source_manifest_sha256"],
            "snapshots": liquidity["snapshot_sha256"],
            "identity": reference["source_hashes"]["identity_history"],
        }
    )
    if expected_reference_source != reference["source_fingerprint"]:
        raise ValueError("Les snapshots 6-B ne correspondent pas au run 6-C")
    identities = {
        r["provider_symbol"]: r for r in _iter_manifest(identity_path) if r["identity_state"] == "VERIFIED_RESEARCH"
    }
    selected = [
        r
        for r in snapshots
        if r["training_state"] == "ELIGIBLE" and start.isoformat() <= r["decision_session_date"] <= end.isoformat()
    ]
    if not selected:
        raise ValueError("Aucun candidat FR entraînable")
    symbols = sorted({r["provider_symbol"] for r in selected})
    grouped = defaultdict(list)
    for row in snapshots:
        if row["provider_symbol"] in symbols and row["decision_session_date"] <= end.isoformat():
            grouped[row["provider_symbol"]].append(row)
    first_source = min(date.fromisoformat(r["source_session_date"]) for rows in grouped.values() for r in rows)
    calendar_rows = [s for s in get_market_calendar("FR_EQ").sessions(first_source, end) if s.is_open]
    sessions = [s.session_date for s in calendar_rows]
    session_times = {
        s.session_date.isoformat(): {
            "open": s.open_at_utc.isoformat(),
            "previous": sessions[i - 1].isoformat() if i else None,
        }
        for i, s in enumerate(calendar_rows)
    }
    pieces = []
    archive_payload_hashes = {}
    for number, symbol in enumerate(symbols, 1):
        archived = _load_symbol_bars(resolve_path(liquidity["archive_root"]), symbol)
        key = hashlib.sha256(symbol.encode("utf-8")).hexdigest()[:16]
        metadata = json.loads(
            (resolve_path(liquidity["archive_root"]) / "symbols" / f"{key}.json").read_text(encoding="utf-8")
        )
        archive_payload_hashes[symbol] = metadata["payloads"]["eod"]["sha256"]
        rows = []
        for r in grouped[symbol]:
            day = r["source_session_date"]
            bar = archived.get(day)
            if not bar:
                raise ValueError(f"Barre source absente {symbol}/{day}")
            if abs(float(bar["close"]) - float(r["last_close_eur"])) > 1e-8:
                raise ValueError(f"Clôture source 6-B divergente {symbol}/{day}")
            rows.append({"source_session_date": day, **{k: bar[k] for k in ("open", "high", "low", "close", "volume")}})
        feature = compute_symbol_features(pd.DataFrame(rows), sessions)
        feature["source_session_date"] = feature["source_session_date"].dt.strftime("%Y-%m-%d")
        feature["provider_symbol"] = symbol
        pieces.append(feature)
        if number % 25 == 0 or number == len(symbols):
            LOGGER.info("7-A features calculées=%s/%s", number, len(symbols))
    candidate_columns = ["provider_symbol", "mic", "source_session_date", "decision_session_date", "training_state"]
    candidates = pd.DataFrame(selected)[candidate_columns]
    panel = assemble_panel(candidates, pd.concat(pieces, ignore_index=True), identities, session_times, profile)
    source_hash = _fingerprint(
        {
            "snapshots": liquidity["snapshot_sha256"],
            "identities": reference["files"]["identities"]["sha256"],
            "archive_payload_hashes": archive_payload_hashes,
        }
    )
    implementation_sha = _sha256(Path(__file__))
    fingerprint = _fingerprint(
        {"profile": profile, "source": source_hash, "implementation": implementation_sha, "start": start, "end": end}
    )
    destination = output_root / f"fr-feature-{start:%Y%m%d}-{end:%Y%m%d}-{fingerprint[:12]}"
    destination.mkdir(parents=True, exist_ok=True)
    temp = destination / "panel.tmp.parquet"
    panel.to_parquet(temp, index=False, engine="pyarrow", compression="zstd")
    panel_hash = _sha256(temp)
    final = destination / "panel.parquet"
    if final.exists():
        if _sha256(final) != panel_hash:
            raise RuntimeError("Panel FR existant divergent : artefact conservé, vérifier les sources")
        temp.unlink()
    else:
        temp.replace(final)
    dictionary = {
        "profile": profile["profile"],
        "market_code": "FR_EQ",
        "feature_count": len(NUMERIC_FEATURES),
        "features": {
            k: {
                **v,
                "source": "EODHD_RAW_SPRINT5_ADMISSIBLE",
                "available_at": "NEXT_XPAR_SESSION_OPEN_RESEARCH_HYPOTHESIS",
                "missing_policy": "NULL_NO_FILL_WITH_EXPLICIT_MASK",
                "gap_policy": "CONSECUTIVE_XPAR_SESSIONS_REQUIRED",
                "corporate_actions": "SPLIT_HISTORIES_EXCLUDED_BY_SPRINT5_DIVIDENDS_NOT_ADJUSTED",
            }
            for k, v in FEATURE_SPECS.items()
        },
    }
    _atomic_json(destination / "feature_dictionary.json", dictionary)
    by_year = {}
    for year, group in panel.groupby(panel["decision_session_date"].str[:4], sort=True):
        by_year[year] = {
            "rows": len(group),
            "symbols": int(group["provider_symbol"].nunique()),
            "research_ready_rows": int(group["research_ready"].sum()),
            "features": _coverage(group),
        }
    ready = int(panel["research_ready"].sum())
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "verdict": "GO_7A_RESEARCH_PANEL"
        if ready >= int(profile["min_ready_rows"])
        else "BLOCKED_7A_INSUFFICIENT_COMPLETE_ROWS",
        "market_code": "FR_EQ",
        "profile": profile["profile"],
        "start": start.isoformat(),
        "end": end.isoformat(),
        "rows": len(panel),
        "symbols": len(symbols),
        "sessions": int(panel["decision_session_date"].nunique()),
        "feature_count": len(NUMERIC_FEATURES),
        "features": _coverage(panel),
        "by_decision_year": by_year,
        "quality": {
            "duplicate_keys": 0,
            "late_source_rows": 0,
            "research_ready_rows": ready,
            "price20_rows": int(panel["mask_price20"].sum()),
            "full_feature_rows": int(panel["mask_all_features"].sum()),
            "identity_used_as_feature": False,
            "missing_values_imputed": False,
        },
        "source_fingerprint": source_hash,
        "source_archive_payload_hashes": archive_payload_hashes,
        "input_fingerprint": fingerprint,
        "implementation_sha256": implementation_sha,
        "liquidity_run_id": liquidity["liquidity_run_id"],
        "reference_run_id": reference["run_id"],
        "source_report_hashes": {"liquidity": _sha256(liquidity_path), "reference": _sha256(reference_path)},
        "panel_path": str(final.resolve()),
        "panel_sha256": panel_hash,
        "dictionary_path": str((destination / "feature_dictionary.json").resolve()),
        "dictionary_sha256": _sha256(destination / "feature_dictionary.json"),
        "reconstruction_identical": False,
        "database_writes_performed": False,
        "canonical_writes_performed": False,
        "availability_basis": "RESEARCH_J1_HYPOTHESIS_NOT_VERIFIED_PUBLICATION",
        "sector_enabled": False,
        "benchmark_enabled": False,
        "tradable_enabled": False,
        "next_gate": "SPRINT_7B_PRICE_BENCHMARK_RESEARCH_CONTRACT",
    }
    _atomic_json(destination / "report.json", report)
    LOGGER.info("7-A terminé lignes=%s prêtes=%s hash=%s", len(panel), ready, panel_hash)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2018, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 2))
    parser.add_argument("--profile", type=Path, default=ROOT / "config/features_fr/fr_price_v1.yaml")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/fr/features/fr_price_v1")
    parser.add_argument("--verify-rebuild", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    kwargs = {"start": args.start, "end": args.end, "profile_path": args.profile, "output_root": args.output_root}
    report = build_panel(**kwargs)
    if args.verify_rebuild:
        second = build_panel(**kwargs)
        if (
            report["panel_sha256"] != second["panel_sha256"]
            or report["dictionary_sha256"] != second["dictionary_sha256"]
        ):
            raise RuntimeError("Reconstruction FR divergente")
        report["reconstruction_identical"] = True
        _atomic_json(Path(report["panel_path"]).parent / "report.json", report)
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "verdict",
                    "rows",
                    "symbols",
                    "feature_count",
                    "quality",
                    "reconstruction_identical",
                    "panel_path",
                )
            },
            ensure_ascii=False,
        )
    )
    if report["verdict"] != "GO_7A_RESEARCH_PANEL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
