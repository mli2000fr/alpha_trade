"""Job ML pour un batch per-sector (cascade rank-driven) — live quotidien + backfill backtest.

Pour les batches **per_sector** (sans modèles per-symbol), la cascade
(Global Rank × proba per-symbol) est dérivée des rangs eux-mêmes :
    proba_long  = global_rank_{best_h}
    proba_short = 1 - global_rank_{best_h}

Séquence :
1. predict_global_rank_history(plage, batch) → global_rank_history
   (rangs H3/H5/H10/H15/H20 du modèle global du batch)
2. synthesize(batch, best_h) → model_predictions (run `{batch}_globalrank_synth`)
3. Smoke test : RiskRepository.load_predictions_asof (serving batch)

⚠️ Ne PAS utiliser pour un batch per-symbol : ses prédictions viennent des
vrais modèles per-symbol via l'étape 10 (ML Predict).

Usage :
    python -m modelFactory.predict_per_sector                       # batch B25, dernière barre (univers tradable + garde-fou)
    python -m modelFactory.predict_per_sector 2026-07-10            # B25, une date
    python -m modelFactory.predict_per_sector 2025-01-02 2025-12-31  # B25, plage (backfill, univers ticket par défaut)
    python -m modelFactory.predict_per_sector --batch-id model-factory-xxx --best-h 10 --universe ticket 2025-01-02 2025-12-31
"""
import sys
from datetime import date

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s -- %(message)s")

DEFAULT_BATCH_ID = "model-factory-20260811223551-ef2cd0"  # B25 champion promu 2026-08-13


def _last_bar_date() -> date | None:
    from sqlalchemy import create_engine, text

    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT MAX(date) FROM stock_bars_daily WHERE data_source='eodhd_eod'")
        ).fetchone()
    return row[0] if row and row[0] else None


def _parse_args(argv: list[str]) -> tuple[str, int, str, date | None, date | None]:
    batch_id = DEFAULT_BATCH_ID
    best_h = 10
    universe = ""  # vide → tradable en live, ticket en backfill
    dates: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--batch-id":
            batch_id = argv[i + 1]
            i += 2
            continue
        if arg == "--best-h":
            best_h = int(argv[i + 1])
            i += 2
            continue
        if arg == "--universe":
            universe = argv[i + 1].strip().lower()
            if universe not in ("tradable", "ticket"):
                raise SystemExit(f"--universe inconnu : {universe} (attendu tradable|ticket)")
            i += 2
            continue
        dates.append(arg)
        i += 1
    if len(dates) == 0:
        end = _last_bar_date()
        return batch_id, best_h, universe or "tradable", end, end
    if len(dates) == 1:
        d = date.fromisoformat(dates[0])
        return batch_id, best_h, universe or "tradable", d, d
    return batch_id, best_h, universe or "ticket", date.fromisoformat(dates[0]), date.fromisoformat(dates[1])


def main() -> None:
    batch_id, best_h, universe, start_date, end_date = _parse_args(sys.argv[1:])
    if end_date is None:
        raise SystemExit("Aucune barre eodhd disponible — ingestion à vérifier.")
    start_day, end_day = start_date.isoformat(), end_date.isoformat()

    # ── Garde-fou breadth (usage live quotidien uniquement) ──
    from modelFactory.universe_guard import current_universe_size, enforce_min_universe_breadth

    if start_date == end_date:
        from database.connection import get_sqlalchemy_engine

        _size = current_universe_size(get_sqlalchemy_engine(), end_date)
        try:
            enforce_min_universe_breadth(_size, trade_date=end_date, batch_id=batch_id)
        except RuntimeError as exc:
            print(f"[X] {exc}")
            raise SystemExit(1) from exc

    from modelFactory.predictor import predict_global_rank_history

    _symbols = None
    if universe == "ticket":
        from modelFactory.db_registry import _load_ticket_recherche_symbols

        _symbols = _load_ticket_recherche_symbols()
        print(f"[0/3] univers ticket : {len(_symbols)} symboles")
    ranks = predict_global_rank_history(start_day, end_day, batch_id, symbols=_symbols)
    n_days = sum(1 for v in ranks.values() if v and v > 0)
    print(f"[1/3] global ranks [{start_day} -> {end_day}] batch={batch_id} universe={universe}: "
          f"{n_days} jours avec données, total {sum(ranks.values())} lignes")
    if start_date != end_date:
        from modelFactory.universe_guard import load_min_universe_breadth

        _min = load_min_universe_breadth()
        _small = [d for d, n in ranks.items() if n and int(n) < _min]
        if _small:
            print(f"[!] {len(_small)} dates sous le seuil breadth ({_min}) - ex. {_small[:5]}")

    from modelFactory.synthesize_global_rank_predictions import synthesize

    out = synthesize(batch_id, best_h=best_h)
    print(f"[2/3] synthèse: {out}")

    # [3/3] smoke test consommation via serving batch (sur la date de fin)
    from sqlalchemy import create_engine, text

    from risk_management.db_io import RiskRepository

    engine = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True, pool_pre_ping=True)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT symbol FROM global_rank_history WHERE batch_id=:b AND date=:d"),
            {"b": batch_id, "d": end_date},
        ).fetchall()
    symbols = sorted({str(r[0]) for r in rows})
    preds = RiskRepository(engine=engine).load_predictions_asof(symbols, end_date)
    n_live = sum(1 for p in preds.values() if p.prediction_date == end_date)
    n_sig = sum(1 for p in preds.values() if p.predicted_side in ("long", "short"))
    print(f"[3/3] smoke: {len(preds)} symboles consommés, {n_live} datés {end_day}, {n_sig} signaux long/short")
    if n_live == 0:
        raise SystemExit("[X] smoke test KO - aucune prédiction live consommée.")


if __name__ == "__main__":
    main()
