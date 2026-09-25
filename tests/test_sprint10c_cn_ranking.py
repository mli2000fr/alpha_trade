from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.cn_global_ranking_aggregate import _monthly_bootstrap
from modelFactory.cn_global_ranking_walk_forward import (
    DEFAULT_CONFIG,
    RankingProtocol,
    _attach_oracle_pool,
    _tails,
    fold_metrics,
    ranking_metrics,
)


def _frame(days: int = 65) -> pd.DataFrame:
    rows = []
    for day in pd.bdate_range("2022-01-03", periods=days):
        for instrument in range(20):
            decile = 10 if instrument < 2 else 1 if instrument >= 18 else 5
            rows.append({
                "market_code": "CN_A", "session_date": day, "instrument_id": instrument,
                "target_quality_valid": True, "oracle_decile": decile,
                "future_return": float(decile - 5) / 10,
                "rank_score": 20 - instrument,
                "baseline_score": float(instrument),
                "oracle_top20": instrument in {0, 1, 18, 19},
                "board_code": "SH_MAIN", "cn_breadth_1": 0.45,
                "execution_data_eligible": True,
            })
    return pd.DataFrame(rows)


def test_protocol_rejects_other_market(tmp_path: Path) -> None:
    assert RankingProtocol.load(DEFAULT_CONFIG).raw["horizons"] == [5, 10, 15, 20]
    path = tmp_path / "invalid.yaml"
    path.write_text(DEFAULT_CONFIG.read_text(encoding="utf-8").replace(
        "market_code: CN_A", "market_code: US"
    ), encoding="utf-8")
    with pytest.raises(ValueError, match="ranking CN"):
        RankingProtocol.load(path)


def test_signed_tails_and_ic_are_oriented_correctly() -> None:
    frame = _frame()
    top, bottom = _tails(frame, "rank_score", 0.10)
    assert top["oracle_decile"].eq(10).all()
    assert bottom["oracle_decile"].eq(1).all()
    metrics = ranking_metrics(frame, score="rank_score", tail_pct=0.10)
    assert metrics["d10_top_precision"] == 1.0
    assert metrics["d1_bottom_precision"] == 1.0
    assert metrics["wrong_d1_in_top"] == 0.0
    assert metrics["long_short_spread"] > 0


def test_conditional_metrics_use_oracle_pool_and_paired_population() -> None:
    frame = _frame()
    frame.loc[frame["instrument_id"].eq(10), "baseline_score"] = np.nan
    metrics = fold_metrics(frame, RankingProtocol.load(DEFAULT_CONFIG))
    assert metrics["global"]["model"]["rows"] == 65 * 19
    assert metrics["oracle_top20"]["model"]["rows"] == 65 * 4
    assert metrics["oracle_top20"]["tail_precision_uplift"] > 0
    ci = _monthly_bootstrap(frame, tail_pct=0.20, repetitions=100,
                            alpha=0.05 / 8, seed=7)
    assert ci["months"] > 1
    assert ci["lower_fwer_bound"] > 0


def test_oracle_top20_is_selected_before_labels(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from modelFactory import cn_global_ranking_walk_forward as module

    candidate = pd.DataFrame({
        "session_date": [pd.Timestamp("2022-01-03")] * 20,
        "instrument_id": range(20),
        "target_quality_valid": [False] * 4 + [True] * 16,
    })
    paths = {}
    for model in ("lightgbm", "catboost"):
        path = tmp_path / f"{model}.parquet"
        pd.DataFrame({
            "session_date": candidate["session_date"],
            "instrument_id": candidate["instrument_id"],
            "market_code": "CN_A",
            "target_quality_valid": candidate["target_quality_valid"],
            "oracle_score": np.arange(20, 0, -1) / 20,
        }).to_parquet(path)
        paths[model] = path
    monkeypatch.setattr(module, "_find_run", lambda root, **kwargs: (
        paths[kwargs["model"]], {"predictions_sha256": "test"}
    ))
    result, _ = _attach_oracle_pool(candidate, horizon=5, semester="2022H1")
    assert result["oracle_top20"].sum() == 4
    assert result.loc[result["oracle_top20"], "target_quality_valid"].eq(False).all()
