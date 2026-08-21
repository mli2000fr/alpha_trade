"""Backfill global_rank_history pour B25 sur une fenêtre OOS (extension au-delà de mai 2026).

Usage:
    f:/projets/.venv/Scripts/python.exe -u scripts/backfill_global_rank_oos.py [START] [END]

Défaut : 2026-06-01 → 2026-07-10 (max barres dispo). Smoke test : start == end sur 1 jour.
"""
import sys
from pathlib import Path

# Garantir que la racine du projet est dans sys.path (scripts/ n'est pas la racine)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from modelFactory.predictor import predict_global_rank_history
from database.connection import get_sqlalchemy_engine

BATCH = "model-factory-20260811223551-ef2cd0"
# predict_global_rank attend le répertoire DU BATCH (avec _global_ranking_features.json)
ARTIFACTS_DIR = Path(r"F:\projets\artifacts\models") / BATCH


def main() -> None:
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-06-01"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-07-10"
    print(f"=== Backfill global_rank_history B25 [{start} → {end}] ===")
    engine = get_sqlalchemy_engine()
    results = predict_global_rank_history(
        start,
        end,
        BATCH,
        artifacts_dir=ARTIFACTS_DIR,
        engine=engine,
    )
    print("=== Résultats par date ===")
    for d, n in sorted(results.items()):
        print(f"  {d}: {n}")
    ok = {d: n for d, n in results.items() if n > 0}
    print(f"=== DONE: {len(ok)}/{len(results)} dates avec rangs, {sum(ok.values())} lignes totales ===")


if __name__ == "__main__":
    main()
