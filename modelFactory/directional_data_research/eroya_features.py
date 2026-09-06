"""POC de séparabilité des données Eroya dans le pool Oracle TOP20.

Ce module ne modifie aucune table et n'entraîne aucun modèle de production.
Il transforme les collectes brutes du POC Eroya en features datées, puis utilise
le harnais directionnel commun (IC, AUC, stabilité par folds).

Deux niveaux de preuve sont volontairement séparés :

* ``strict`` : short volume décalé d'une séance, short interest disponible à la
  date officielle de publication FINRA, actions analystes décalées d'un jour,
  achats/ventes Form 4 disponibles à la séance suivant leur dépôt ;
* ``sensitivity`` : transactions insiders décalées de deux jours ouvrés, faute
  de timestamp de dépôt dans l'endpoint agrégé. Ce résultat ne constitue pas
  une preuve PIT et ne doit pas être sélectionné pour le modèle final.
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
from pathlib import Path
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.harness import (
    analyze_features,
    assemble_pool,
    format_report,
)
from modelFactory.global_direction.dataset import DECILE_COL, RETURN_COL
from modelFactory.oracle.train import roc_auc
from modelFactory.shared_directional import load_forward_return_panel

LOGGER = logging.getLogger(__name__)
DEFAULT_ROOT = Path("artifacts/research/eroya_directional")
FINRA_CALENDAR = Path("artifacts/finra_short_volume/short_interest_400.parquet")


def find_collection(dataset: str, root: Path = DEFAULT_ROOT,
                    *, min_symbols: int = 100) -> Path:
    """Retourne le dernier artefact complet contenant ``dataset``."""
    candidates: list[tuple[str, Path]] = []
    for report_path in root.glob("eroya-collect-*/collection_report.json"):
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if int(report.get("symbols") or 0) < int(min_symbols):
            continue
        for item in report.get("datasets", []):
            if item.get("dataset") != dataset or int(item.get("failures") or 0):
                continue
            artifact = report_path.parent / f"{dataset}.jsonl.gz"
            if artifact.exists():
                candidates.append((report_path.parent.name, artifact))
    if not candidates:
        raise FileNotFoundError(
            f"Aucune collecte Eroya complète pour {dataset!r} ({min_symbols}+ symboles).")
    return sorted(candidates, key=lambda item: item[0])[-1][1]


def assemble_bundle_pool_at_horizon(engine: Any, batch_id: str, *,
                                    start_date: str, end_date: str,
                                    horizon: int) -> pd.DataFrame:
    """Reconstruit H3/H10 lorsque le batch Oracle n'a persisté que sa cible H20."""
    gate_path = Path("artifacts/models") / batch_id / "_oracle_oof_gate.parquet"
    if not gate_path.exists():
        return pd.DataFrame()
    gate = pd.read_parquet(gate_path)
    gate["date"] = pd.to_datetime(gate["date"], errors="coerce").dt.normalize()
    gate["symbol"] = gate["symbol"].astype(str).str.upper()
    gate = gate[(gate["date"] >= pd.Timestamp(start_date)) &
                (gate["date"] <= pd.Timestamp(end_date))]
    if "directional_oracle_eligible" in gate.columns:
        pool = gate[gate["directional_oracle_eligible"].fillna(False)].copy()
    else:
        score = pd.to_numeric(gate["directional_oracle_proba_extreme"], errors="coerce")
        gate["_pct"] = score.groupby(gate["date"]).rank(pct=True)
        pool = gate[gate["_pct"] >= 0.80].copy()
    symbols = sorted(gate["symbol"].dropna().unique().tolist())
    panel, _ = load_forward_return_panel(
        engine, symbols, start_date=start_date, end_date=end_date,
        horizons=[horizon], sector_min_members=5)
    panel = panel[panel["horizon"].eq(int(horizon))].copy()
    panel[RETURN_COL] = pd.to_numeric(panel["future_return"], errors="coerce")
    pct = panel.groupby("date")[RETURN_COL].rank(pct=True, method="average")
    panel[DECILE_COL] = np.ceil(pct * 10.0).clip(1, 10)
    merged = pool.merge(panel[["date", "symbol", RETURN_COL, DECILE_COL]],
                        on=["date", "symbol"], how="inner")
    merged["proba_extreme"] = pd.to_numeric(
        merged.get("directional_oracle_proba_extreme"), errors="coerce")
    merged["fold_start"] = merged["date"].dt.year.astype(str)
    merged["year"] = merged["fold_start"]
    merged["regime"] = "unknown"
    return merged[["date", "symbol", "proba_extreme", DECILE_COL, RETURN_COL,
                   "fold_start", "year", "regime"]].dropna(
                       subset=[DECILE_COL, RETURN_COL])


def iter_payloads(path: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            document = json.loads(line)
            payload = document.get("payload")
            if isinstance(payload, dict):
                yield str(document.get("symbol_requested") or "").upper(), payload


def load_short_volume(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for requested, payload in iter_payloads(path):
        for row in payload.get("results", []):
            if isinstance(row, dict):
                rows.append({**row, "symbol": str(row.get("ticker") or requested).upper()})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    numeric = ["short_volume", "total_volume", "exempt_volume", "short_volume_ratio"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    computed = frame["short_volume"] / frame["total_volume"].replace(0, np.nan)
    frame["short_ratio"] = frame["short_volume_ratio"].where(
        frame["short_volume_ratio"].notna(), computed)
    # Certains fournisseurs expriment le ratio en pourcentage.
    frame.loc[frame["short_ratio"] > 1.5, "short_ratio"] /= 100.0
    frame["short_exempt_ratio"] = (
        frame["exempt_volume"] / frame["total_volume"].replace(0, np.nan))
    frame = frame.dropna(subset=["date", "symbol"]).drop_duplicates(
        subset=["date", "symbol"], keep="last").sort_values(["symbol", "date"])
    grouped = frame.groupby("symbol", group_keys=False)
    frame["eroya_short_ratio_5d"] = grouped["short_ratio"].transform(
        lambda values: values.rolling(5, min_periods=3).mean())
    frame["eroya_short_ratio_20d"] = grouped["short_ratio"].transform(
        lambda values: values.rolling(20, min_periods=10).mean())
    frame["eroya_short_ratio_delta5"] = frame["short_ratio"] - frame["eroya_short_ratio_5d"]
    mean60 = grouped["short_ratio"].transform(lambda values: values.rolling(60, min_periods=20).mean())
    std60 = grouped["short_ratio"].transform(lambda values: values.rolling(60, min_periods=20).std())
    frame["eroya_short_ratio_z60"] = (frame["short_ratio"] - mean60) / std60.replace(0, np.nan)
    return frame.rename(columns={
        "short_ratio": "eroya_short_ratio_1d",
        "short_exempt_ratio": "eroya_short_exempt_ratio",
    })[["symbol", "date", "eroya_short_ratio_1d", "eroya_short_ratio_5d",
        "eroya_short_ratio_20d", "eroya_short_ratio_delta5",
        "eroya_short_ratio_z60", "eroya_short_exempt_ratio"]]


def load_short_interest(path: Path, calendar_path: Path = FINRA_CALENDAR) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for requested, payload in iter_payloads(path):
        for row in payload.get("results", []):
            if isinstance(row, dict):
                rows.append({**row, "symbol": str(row.get("ticker") or requested).upper()})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["settlement_date"] = pd.to_datetime(
        frame["settlement_date"], errors="coerce").dt.normalize()
    for column in ["short_interest", "avg_daily_volume", "days_to_cover"]:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    frame = frame.dropna(subset=["settlement_date", "symbol"]).drop_duplicates(
        subset=["settlement_date", "symbol"], keep="last").sort_values(
            ["symbol", "settlement_date"])
    frame["eroya_short_interest_change"] = frame.groupby("symbol")["short_interest"].pct_change()
    frame["eroya_short_interest_to_adv"] = (
        frame["short_interest"] / frame["avg_daily_volume"].replace(0, np.nan))
    frame["eroya_days_to_cover"] = frame["days_to_cover"]

    # Le settlement_date n'est pas PIT. On ne conserve que les dates pour
    # lesquelles le calendrier FINRA local fournit une publication officielle.
    calendar = pd.read_parquet(calendar_path, columns=["settlement_date", "publication_date"])
    calendar["settlement_date"] = pd.to_datetime(
        calendar["settlement_date"], errors="coerce").dt.normalize()
    calendar["publication_date"] = pd.to_datetime(
        calendar["publication_date"], errors="coerce").dt.normalize()
    calendar = calendar.dropna().drop_duplicates(subset=["settlement_date"])
    frame = frame.merge(calendar, on="settlement_date", how="inner")
    return frame[["symbol", "publication_date", "eroya_short_interest_change",
                  "eroya_short_interest_to_adv", "eroya_days_to_cover"]]


def _nested_history(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    results = payload.get("results")
    if not isinstance(results, dict):
        return []
    rows = results.get(key)
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def load_analyst_events(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for requested, payload in iter_payloads(path):
        for row in _nested_history(payload, "history"):
            action = str(row.get("action") or "").lower()
            signed = 1.0 if action == "up" else -1.0 if action == "down" else 0.0
            current = pd.to_numeric(row.get("currentPriceTarget"), errors="coerce")
            prior = pd.to_numeric(row.get("priorPriceTarget"), errors="coerce")
            target_change = ((current - prior) / abs(prior)
                             if pd.notna(current) and pd.notna(prior) and prior != 0 else np.nan)
            rows.append({"symbol": requested, "event_date": row.get("gradeDate"),
                         "signed": signed, "target_change": target_change})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["event_date", "symbol"])
    # Heure intrajournalière absente : usage possible à partir du jour ouvré suivant.
    frame["available_date"] = frame["event_date"] + pd.offsets.BDay(1)
    return frame


def load_analyst_insights(path: Path, *, strict: bool) -> pd.DataFrame:
    """Charge les ratings Benzinga structurés sans exploiter le texte libre."""
    rows: list[dict[str, Any]] = []
    for requested, payload in iter_payloads(path):
        for row in payload.get("results", []):
            if isinstance(row, dict):
                rows.append({
                    "symbol": str(row.get("ticker") or requested).upper(),
                    "firm": str(row.get("firm") or "UNKNOWN"),
                    "event_date": row.get("date"),
                    "last_updated": row.get("last_updated"),
                    "rating_action": str(row.get("rating_action") or "").lower(),
                    "rating": str(row.get("rating") or "").lower(),
                    "price_target": row.get("price_target"),
                })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce").dt.normalize()
    updated = pd.to_datetime(frame["last_updated"], errors="coerce", utc=True)
    frame["updated_date"] = updated.dt.tz_convert(None).dt.normalize()
    frame = frame.dropna(subset=["event_date", "symbol"])
    action_map = {"upgrades": 1.0, "downgrades": -1.0}
    frame["signed"] = frame["rating_action"].map(action_map).fillna(0.0)
    positive = {"buy", "outperform", "overweight", "market outperform", "strong buy",
                "sector outperform", "positive"}
    negative = {"sell", "underperform", "underweight", "sector underperform"}
    frame["rating_signed"] = np.where(
        frame["rating"].isin(positive), 1.0,
        np.where(frame["rating"].isin(negative), -1.0, 0.0))
    frame["price_target"] = pd.to_numeric(frame["price_target"], errors="coerce")
    frame = frame.sort_values(["symbol", "firm", "event_date", "updated_date"])
    frame["target_change"] = frame.groupby(["symbol", "firm"])["price_target"].pct_change(
        fill_method=None).clip(-2.0, 2.0)
    if strict:
        # Un historique récupéré aujourd'hui ne prouve pas que ses valeurs
        # révisées étaient identiques à event_date. last_updated est donc le
        # minimum strict d'utilisation lorsqu'il est postérieur.
        frame["available_date"] = frame[["event_date", "updated_date"]].max(axis=1)
    else:
        frame["available_date"] = frame["event_date"] + pd.offsets.BDay(1)
    return frame


def load_insider_events(path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for requested, payload in iter_payloads(path):
        for row in _nested_history(payload, "transactions"):
            text = str(row.get("transaction") or "").lower()
            signed = 1.0 if text.startswith("purchase") else -1.0 if text.startswith("sale") else 0.0
            rows.append({"symbol": requested, "event_date": row.get("startDate"),
                         "signed": signed, "shares": row.get("shares"), "value": row.get("value")})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["event_date"] = pd.to_datetime(frame["event_date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["event_date", "symbol"])
    # Sensibilité seulement : la règle SEC est un délai maximal, pas le vrai filedAt.
    frame["available_date"] = frame["event_date"] + pd.offsets.BDay(2)
    return frame


def load_form4_events(path: Path) -> pd.DataFrame:
    """Charge les achats/ventes discrétionnaires Form 4 avec contrat PIT strict.

    Seuls les codes ``P`` (achat au marché) et ``S`` (vente au marché) sont
    directionnels. Les attributions, exercices, cadeaux et retenues fiscales
    sont volontairement exclus. La source ne fournit qu'une date de dépôt,
    sans heure : le signal devient donc utilisable à la séance ouvrée suivante.

    Une déclaration peut contenir plusieurs transactions et une même ligne peut
    être répétée dans la réponse. La clé ci-dessous déduplique une transaction,
    sans réduire toute une déclaration à son accession number.
    """
    rows: list[dict[str, Any]] = []
    for requested, payload in iter_payloads(path):
        for row in payload.get("results", []):
            if not isinstance(row, dict):
                continue
            code = str(row.get("transaction_code") or "").upper().strip()
            if code not in {"P", "S"}:
                continue
            rows.append({
                "symbol": requested,
                "accession_number": row.get("accession_number"),
                "owner_cik": row.get("owner_cik"),
                "security_title": row.get("security_title"),
                "direct_or_indirect": row.get("direct_or_indirect"),
                "transaction_date": row.get("transaction_date"),
                "filing_date": row.get("filing_date"),
                "transaction_code": code,
                "transaction_acquired_disposed": row.get("transaction_acquired_disposed"),
                "shares": row.get("transaction_shares"),
                "price": row.get("transaction_price_per_share"),
                "value": row.get("transaction_value"),
                "is_director": bool(row.get("is_director")),
                "is_officer": bool(row.get("is_officer")),
                "is_ten_percent_owner": bool(row.get("is_ten_percent_owner")),
                "aff_10b5_one": bool(row.get("aff_10b5_one")),
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    for column in ["transaction_date", "filing_date"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
    for column in ["shares", "price", "value"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    computed_value = frame["shares"].abs() * frame["price"].abs()
    frame["value"] = frame["value"].abs().where(frame["value"].notna(), computed_value)
    frame = frame.dropna(subset=["symbol", "filing_date"])
    transaction_key = [
        "symbol", "accession_number", "owner_cik", "security_title",
        "direct_or_indirect", "transaction_date", "filing_date",
        "transaction_code", "transaction_acquired_disposed", "shares", "price",
    ]
    frame = frame.drop_duplicates(subset=transaction_key, keep="last")
    frame["signed"] = np.where(frame["transaction_code"].eq("P"), 1.0, -1.0)
    frame["signed_value"] = frame["signed"] * frame["value"].fillna(0.0)
    frame["available_date"] = frame["filing_date"] + pd.offsets.BDay(1)
    return frame.sort_values(["symbol", "available_date", "filing_date"])


def build_form4_features(pool: pd.DataFrame, events: pd.DataFrame,
                         *, prefix: str = "eroya_form4") -> pd.DataFrame:
    """Agrège les Form 4 connus à chaque date Oracle, sans regard vers le futur."""
    keys = pool[["date", "symbol"]].drop_duplicates().copy()
    value_columns = [
        f"{prefix}_net_count_30d", f"{prefix}_net_count_90d",
        f"{prefix}_buy_count_90d", f"{prefix}_sell_count_90d",
        f"{prefix}_net_value_30d", f"{prefix}_net_value_90d",
        f"{prefix}_buy_value_share_90d", f"{prefix}_days_since",
        f"{prefix}_net_count_90d_no10b5", f"{prefix}_net_value_90d_no10b5",
        f"{prefix}_officer_net_count_90d", f"{prefix}_director_net_count_90d",
    ]
    output: list[pd.DataFrame] = []
    for symbol, dates_part in keys.groupby("symbol"):
        part = dates_part.sort_values("date").copy()
        event = events[events["symbol"].eq(symbol)].sort_values("available_date")
        if event.empty:
            for column in value_columns:
                part[column] = np.nan if column.endswith("days_since") else 0.0
            output.append(part)
            continue
        dates = part["date"].to_numpy(dtype="datetime64[ns]")
        event_dates = event["available_date"].to_numpy(dtype="datetime64[ns]")
        hi = np.searchsorted(event_dates, dates, side="right")
        lo30 = np.searchsorted(event_dates, dates - np.timedelta64(30, "D"), side="left")
        lo90 = np.searchsorted(event_dates, dates - np.timedelta64(90, "D"), side="left")

        def rolling_sum(values: np.ndarray, lower: np.ndarray) -> np.ndarray:
            cumulative = np.r_[0.0, np.cumsum(np.nan_to_num(values.astype(float)))]
            return cumulative[hi] - cumulative[lower]

        signed = event["signed"].to_numpy(float)
        signed_value = event["signed_value"].to_numpy(float)
        buys = event["transaction_code"].eq("P").to_numpy(float)
        sells = event["transaction_code"].eq("S").to_numpy(float)
        absolute_value = event["value"].fillna(0.0).to_numpy(float)
        no10b5 = (~event["aff_10b5_one"]).to_numpy(float)
        officer = event["is_officer"].to_numpy(float)
        director = event["is_director"].to_numpy(float)
        part[f"{prefix}_net_count_30d"] = rolling_sum(signed, lo30)
        part[f"{prefix}_net_count_90d"] = rolling_sum(signed, lo90)
        part[f"{prefix}_buy_count_90d"] = rolling_sum(buys, lo90)
        part[f"{prefix}_sell_count_90d"] = rolling_sum(sells, lo90)
        part[f"{prefix}_net_value_30d"] = rolling_sum(signed_value, lo30)
        part[f"{prefix}_net_value_90d"] = rolling_sum(signed_value, lo90)
        buy_value = rolling_sum(absolute_value * buys, lo90)
        total_value = rolling_sum(absolute_value * (buys + sells), lo90)
        part[f"{prefix}_buy_value_share_90d"] = np.divide(
            buy_value, total_value, out=np.full(len(part), np.nan), where=total_value > 0)
        part[f"{prefix}_net_count_90d_no10b5"] = rolling_sum(signed * no10b5, lo90)
        part[f"{prefix}_net_value_90d_no10b5"] = rolling_sum(signed_value * no10b5, lo90)
        part[f"{prefix}_officer_net_count_90d"] = rolling_sum(signed * officer, lo90)
        part[f"{prefix}_director_net_count_90d"] = rolling_sum(signed * director, lo90)
        latest = hi - 1
        valid = latest >= 0
        days_since = np.full(len(part), np.nan)
        days_since[valid] = (dates[valid] - event_dates[latest[valid]]).astype(
            "timedelta64[D]").astype(float)
        part[f"{prefix}_days_since"] = days_since
        output.append(part)
    return pd.concat(output, ignore_index=True) if output else keys


def build_event_features(pool: pd.DataFrame, events: pd.DataFrame,
                         *, prefix: str) -> pd.DataFrame:
    keys = pool[["date", "symbol"]].drop_duplicates().copy()
    output: list[pd.DataFrame] = []
    for symbol, dates_part in keys.groupby("symbol"):
        part = dates_part.sort_values("date").copy()
        event = events[events["symbol"] == symbol].sort_values("available_date")
        dates = part["date"].to_numpy(dtype="datetime64[ns]")
        if event.empty:
            part[f"{prefix}_signed_30d"] = 0.0
            part[f"{prefix}_signed_90d"] = 0.0
            part[f"{prefix}_count_30d"] = 0.0
            part[f"{prefix}_net_share_90d"] = 0.0
            part[f"{prefix}_days_since"] = np.nan
            if "target_change" in events.columns:
                part[f"{prefix}_target_change_last"] = np.nan
            output.append(part)
            continue
        event_dates = event["available_date"].to_numpy(dtype="datetime64[ns]")
        signed = pd.to_numeric(event["signed"], errors="coerce").fillna(0).to_numpy(float)
        prefix_signed = np.r_[0.0, np.cumsum(signed)]
        prefix_count = np.arange(len(event_dates) + 1, dtype=float)
        hi = np.searchsorted(event_dates, dates, side="right")
        lo30 = np.searchsorted(event_dates, dates - np.timedelta64(30, "D"), side="left")
        lo90 = np.searchsorted(event_dates, dates - np.timedelta64(90, "D"), side="left")
        signed30 = prefix_signed[hi] - prefix_signed[lo30]
        signed90 = prefix_signed[hi] - prefix_signed[lo90]
        count30 = prefix_count[hi] - prefix_count[lo30]
        count90 = prefix_count[hi] - prefix_count[lo90]
        part[f"{prefix}_signed_30d"] = signed30
        part[f"{prefix}_signed_90d"] = signed90
        part[f"{prefix}_count_30d"] = count30
        part[f"{prefix}_net_share_90d"] = signed90 / np.where(count90 == 0, 1.0, count90)
        latest = hi - 1
        valid = latest >= 0
        days_since = np.full(len(part), np.nan)
        days_since[valid] = (dates[valid] - event_dates[latest[valid]]).astype(
            "timedelta64[D]").astype(float)
        part[f"{prefix}_days_since"] = days_since
        if "target_change" in event.columns:
            values = pd.to_numeric(event["target_change"], errors="coerce").to_numpy(float)
            last_value = np.full(len(part), np.nan)
            # Dernière valeur non nulle connue, pas simplement le dernier événement.
            good_pos = np.flatnonzero(np.isfinite(values))
            if len(good_pos):
                good_dates = event_dates[good_pos]
                value_pos = np.searchsorted(good_dates, dates, side="right") - 1
                mask = value_pos >= 0
                last_value[mask] = values[good_pos[value_pos[mask]]]
            part[f"{prefix}_target_change_last"] = last_value
        output.append(part)
    return pd.concat(output, ignore_index=True) if output else keys


def merge_asof_by_symbol(pool: pd.DataFrame, features: pd.DataFrame,
                         *, right_date: str, allow_exact: bool,
                         max_age_days: int | None = None) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    value_columns = [c for c in features.columns if c not in {"symbol", right_date}]
    for symbol, part in pool[["date", "symbol"]].drop_duplicates().groupby("symbol"):
        right = features[features["symbol"] == symbol].drop(columns="symbol").sort_values(right_date)
        left = part.sort_values("date")
        if right.empty:
            merged = left.copy()
            for column in value_columns:
                merged[column] = np.nan
        else:
            merged = pd.merge_asof(left, right, left_on="date", right_on=right_date,
                                   direction="backward", allow_exact_matches=allow_exact)
            if max_age_days is not None:
                age = (merged["date"] - merged[right_date]).dt.days
                merged.loc[age > max_age_days, value_columns] = np.nan
        pieces.append(merged[["date", "symbol", *value_columns]])
    return pd.concat(pieces, ignore_index=True)


def analyze_complete_cases(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    results: list[pd.DataFrame] = []
    for column in columns:
        valid = frame.dropna(subset=[column]).copy()
        if len(valid) < 100 or valid[column].nunique() < 2:
            continue
        result = analyze_features(valid, [column])
        valid["_daily_rank"] = valid.groupby("date")[column].rank(pct=True)
        direction = (valid[DECILE_COL].astype(int) >= 6).astype(float)
        result["daily_rank_auc_direction"] = roc_auc(
            direction.to_numpy(), valid["_daily_rank"].to_numpy(float))
        long_selected = valid["_daily_rank"] >= 0.80
        short_selected = valid["_daily_rank"] <= 0.20
        long_enough = int(long_selected.sum()) >= 100
        short_enough = int(short_selected.sum()) >= 100
        true_long = valid[DECILE_COL].astype(int) >= 8
        true_short = valid[DECILE_COL].astype(int) <= 3
        baseline_long = float(true_long.mean())
        baseline_short = float(true_short.mean())
        baseline_return = float(valid[RETURN_COL].mean())
        long_precision = float(true_long[long_selected].mean()) if long_enough else np.nan
        short_precision = float(true_short[short_selected].mean()) if short_enough else np.nan
        result["long_precision_d8_d10_top20"] = long_precision
        result["long_precision_lift"] = long_precision - baseline_long
        result["long_mean_return_top20"] = (
            float(valid.loc[long_selected, RETURN_COL].mean()) if long_enough else np.nan)
        result["long_return_lift"] = result["long_mean_return_top20"] - baseline_return
        result["long_n"] = int(long_selected.sum())
        result["short_precision_d1_d3_bottom20"] = short_precision
        result["short_precision_lift"] = short_precision - baseline_short
        result["short_mean_pnl_bottom20"] = (
            float(-valid.loc[short_selected, RETURN_COL].mean()) if short_enough else np.nan)
        result["short_pnl_lift"] = result["short_mean_pnl_bottom20"] + baseline_return
        result["short_n"] = int(short_selected.sum())
        result["coverage_ratio"] = len(valid) / len(frame)
        result["date_min"] = valid["date"].min()
        result["date_max"] = valid["date"].max()
        results.append(result)
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def evaluate_policy_by_fold(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Mesure les tris top/bottom 20 % par feature et par fold temporel."""
    rows: list[dict[str, Any]] = []
    for column in columns:
        valid = frame.dropna(subset=[column]).copy()
        if len(valid) < 100 or valid[column].nunique() < 2:
            continue
        valid["_daily_rank"] = valid.groupby("date")[column].rank(pct=True)
        for fold, part in valid.groupby("fold_start"):
            long_selected = part["_daily_rank"] >= 0.80
            short_selected = part["_daily_rank"] <= 0.20
            baseline_return = float(part[RETURN_COL].mean())
            long_return = float(part.loc[long_selected, RETURN_COL].mean()) if long_selected.any() else np.nan
            short_pnl = float(-part.loc[short_selected, RETURN_COL].mean()) if short_selected.any() else np.nan
            rows.append({
                "feature": column,
                "fold": str(fold),
                "n_obs": len(part),
                "long_n": int(long_selected.sum()),
                "long_precision_d8_d10": float((part.loc[long_selected, DECILE_COL] >= 8).mean()) if long_selected.any() else np.nan,
                "long_mean_return": long_return,
                "long_return_lift": long_return - baseline_return,
                "short_n": int(short_selected.sum()),
                "short_precision_d1_d3": float((part.loc[short_selected, DECILE_COL] <= 3).mean()) if short_selected.any() else np.nan,
                "short_mean_pnl": short_pnl,
                "short_pnl_lift": short_pnl + baseline_return,
            })
    return pd.DataFrame(rows)


def evaluate_form4_signed_rules(frame: pd.DataFrame) -> pd.DataFrame:
    """Évalue des règles Form 4 explicites, adaptées aux nombreuses valeurs nulles.

    Cette lecture complète le classement cross-sectionnel générique. Elle évite
    de transformer tous les zéros ex aequo en pseudo top/bottom 20 %.
    """
    rule_masks = {
        "net_count_90d": (
            frame["eroya_form4_net_count_90d"] > 0,
            frame["eroya_form4_net_count_90d"] < 0),
        "net_value_90d": (
            frame["eroya_form4_net_value_90d"] > 0,
            frame["eroya_form4_net_value_90d"] < 0),
        "net_count_90d_no10b5": (
            frame["eroya_form4_net_count_90d_no10b5"] > 0,
            frame["eroya_form4_net_count_90d_no10b5"] < 0),
        "net_value_90d_no10b5": (
            frame["eroya_form4_net_value_90d_no10b5"] > 0,
            frame["eroya_form4_net_value_90d_no10b5"] < 0),
        "officer_net_count_90d": (
            frame["eroya_form4_officer_net_count_90d"] > 0,
            frame["eroya_form4_officer_net_count_90d"] < 0),
        "director_net_count_90d": (
            frame["eroya_form4_director_net_count_90d"] > 0,
            frame["eroya_form4_director_net_count_90d"] < 0),
        "exclusive_buy_vs_sell_90d": (
            (frame["eroya_form4_buy_count_90d"] > 0) &
            (frame["eroya_form4_sell_count_90d"] == 0),
            (frame["eroya_form4_sell_count_90d"] > 0) &
            (frame["eroya_form4_buy_count_90d"] == 0)),
    }
    rows: list[dict[str, Any]] = []
    groups: list[tuple[str, pd.DataFrame]] = [("ALL", frame)]
    groups.extend((str(fold), part) for fold, part in frame.groupby("fold_start"))
    for fold, part in groups:
        baseline_return = float(part[RETURN_COL].mean())
        baseline_long = float((part[DECILE_COL] >= 8).mean())
        baseline_short = float((part[DECILE_COL] <= 3).mean())
        for rule, (long_mask_all, short_mask_all) in rule_masks.items():
            long_mask = long_mask_all.reindex(part.index, fill_value=False)
            short_mask = short_mask_all.reindex(part.index, fill_value=False)
            for side, mask in (("LONG", long_mask), ("SHORT", short_mask)):
                selected = part.loc[mask]
                if selected.empty:
                    continue
                if side == "LONG":
                    precision = float((selected[DECILE_COL] >= 8).mean())
                    realized = float(selected[RETURN_COL].mean())
                    lift = realized - baseline_return
                    precision_lift = precision - baseline_long
                else:
                    precision = float((selected[DECILE_COL] <= 3).mean())
                    realized = float(-selected[RETURN_COL].mean())
                    lift = realized + baseline_return
                    precision_lift = precision - baseline_short
                rows.append({
                    "rule": rule, "side": side, "fold": fold,
                    "n": len(selected), "coverage_ratio": len(selected) / len(part),
                    "precision_d1d3_or_d8d10": precision,
                    "precision_lift": precision_lift,
                    "mean_realized_pnl": realized, "pnl_lift": lift,
                    "baseline_return": baseline_return,
                })
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--oracle-run")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    paths = {name: find_collection(name, args.root) for name in (
        "short_volume", "short_interest", "upgrades_downgrades",
        "insider_transactions", "analyst_insights", "form4_raw")}
    engine = get_sqlalchemy_engine()
    pool = assemble_pool(engine, args.batch_id,
                         start_date=args.start_date, end_date=args.end_date,
                         horizon=args.horizon, oracle_run=args.oracle_run)
    if pool.empty:
        pool = assemble_bundle_pool_at_horizon(
            engine, args.batch_id, start_date=args.start_date,
            end_date=args.end_date, horizon=args.horizon)
    if pool.empty:
        raise SystemExit("Pool Oracle TOP20 vide.")
    LOGGER.info("Pool Oracle TOP20: %d lignes, %d dates, %d symboles",
                len(pool), pool["date"].nunique(), pool["symbol"].nunique())

    daily = load_short_volume(paths["short_volume"])
    short_daily = merge_asof_by_symbol(pool, daily, right_date="date",
                                       allow_exact=False, max_age_days=5)
    interest = load_short_interest(paths["short_interest"])
    short_interest = merge_asof_by_symbol(pool, interest, right_date="publication_date",
                                          allow_exact=True, max_age_days=45)
    analyst = build_event_features(pool, load_analyst_events(paths["upgrades_downgrades"]),
                                   prefix="eroya_analyst")
    insights_raw = load_analyst_insights(paths["analyst_insights"], strict=True)
    insights_action = build_event_features(
        pool, insights_raw, prefix="eroya_insight_action")
    insights_rating_events = insights_raw.copy()
    insights_rating_events["signed"] = insights_rating_events["rating_signed"]
    insights_rating = build_event_features(
        pool, insights_rating_events, prefix="eroya_insight_rating")
    form4_raw = load_form4_events(paths["form4_raw"])
    form4 = build_form4_features(pool, form4_raw)
    strict = pool.merge(short_daily, on=["date", "symbol"], how="left")
    strict = strict.merge(short_interest, on=["date", "symbol"], how="left")
    strict = strict.merge(analyst, on=["date", "symbol"], how="left")
    strict = strict.merge(insights_action, on=["date", "symbol"], how="left")
    strict = strict.merge(insights_rating, on=["date", "symbol"], how="left")
    strict = strict.merge(form4, on=["date", "symbol"], how="left")
    strict_columns = [column for column in strict if column.startswith("eroya_")]
    strict_result = analyze_complete_cases(strict, strict_columns)
    strict_by_fold = evaluate_policy_by_fold(strict, strict_columns)
    form4_signed_rules = evaluate_form4_signed_rules(strict)

    insider = build_event_features(pool, load_insider_events(paths["insider_transactions"]),
                                   prefix="eroya_insider_sensitivity")
    sensitivity = pool.merge(insider, on=["date", "symbol"], how="left")
    insights_eventdate_raw = load_analyst_insights(paths["analyst_insights"], strict=False)
    insights_eventdate = build_event_features(
        pool, insights_eventdate_raw, prefix="eroya_insight_eventdate_sensitivity")
    sensitivity = sensitivity.merge(insights_eventdate, on=["date", "symbol"], how="left")
    sensitivity_columns = [
        column for column in sensitivity
        if (column.startswith("eroya_insider_sensitivity") or
            column.startswith("eroya_insight_eventdate_sensitivity"))
    ]
    sensitivity_result = analyze_complete_cases(sensitivity, sensitivity_columns)

    output = args.output or args.root / (
        f"evaluation-{pd.Timestamp.utcnow():%Y%m%d%H%M%S%f}-h{args.horizon}-{args.batch_id[-6:]}")
    output.mkdir(parents=True, exist_ok=False)
    strict_result.to_csv(output / "strict_separability.csv", index=False)
    strict_by_fold.to_csv(output / "strict_policy_by_fold.csv", index=False)
    form4_signed_rules.to_csv(output / "form4_signed_rules.csv", index=False)
    sensitivity_result.to_csv(output / "insider_sensitivity_not_pit.csv", index=False)
    strict[["date", "symbol", *strict_columns]].to_parquet(
        output / "strict_features_oracle_top20.parquet", index=False)
    report = {
        "batch_id": args.batch_id,
        "period": [args.start_date, args.end_date],
        "horizon": args.horizon,
        "pool_rows": len(pool),
        "pool_symbols": int(pool["symbol"].nunique()),
        "sources": {name: str(path.resolve()) for name, path in paths.items()},
        "strict_feature_count": len(strict_columns),
        "sensitivity_feature_count": len(sensitivity_columns),
        "pit_contract": {
            "short_volume": "previous_observation_only; max age 5 calendar days",
            "short_interest": "official FINRA publication_date only; max age 45 days",
            "analyst": "gradeDate plus one business day (time absent)",
            "form4": "P/S only; filing_date plus one business day (time absent)",
            "insider": "NOT PIT: transaction date plus two business days sensitivity only",
        },
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report_text = format_report(strict_result) if not strict_result.empty else "Aucun résultat strict."
    (output / "strict_report.txt").write_text(report_text, encoding="utf-8")
    print(report_text)
    print(f"Artefacts évaluation Eroya : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
