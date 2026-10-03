"""Confirmation historique FR multi-fold sur la reconstruction ciblée du fold 7."""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import yaml

from modelFactory.fr_fold7_rebuild import ROOT, sha, write_json

LOG = logging.getLogger(__name__)


def run(rebuild: Path) -> dict:
    rebuild = rebuild.resolve()
    qualification = json.loads((rebuild / "rebuild_report.json").read_text(encoding="utf-8"))["qualification"]
    original = qualification["results"]["expanding_original"]
    if original["admitted_oracle_folds"] != [4, 5, 6, 7]:
        raise ValueError("Support insuffisant pour le protocole multi-fold réparé")
    frozen = yaml.safe_load((rebuild / "oracle_oof_qualification_v1.yaml").read_text(encoding="utf-8"))
    output = rebuild / "confirmation"
    output.mkdir(exist_ok=False)
    support = {"profile": "fr_fold7_price_only_support_v1", "source_hashes": {"labels": frozen["labels_sha256"], "price": frozen["price_sha256"]},
               "fold_support": original["support"], "complete_data_support_folds": {"price_only": {"5": original["admitted_oracle_folds"]}},
               "qualification_report": qualification["artifact_dir"], "canonical_writes": False, "benchmark_evaluated": False}
    write_json(output / "support.json", support)
    oracle = yaml.safe_load((ROOT / "config/research_fr/oracle_h5_pilot_v1.yaml").read_text(encoding="utf-8"))
    oracle.update({k: frozen[k] for k in ("labels_report", "labels_sha256", "price_panel", "price_sha256")})
    oracle.update(profile="fr_oracle_h5_fold7_repaired_v1", folds=[4, 5, 6, 7], support_report=str(output / "support.json"))
    oracle_path = output / "oracle_profile.yaml"
    oracle_path.write_text(yaml.safe_dump(oracle, sort_keys=False), encoding="utf-8")
    from modelFactory.fr_oracle_h5_pilot import run as oracle_run
    LOG.info("Oracle OOF : folds 4/5/6/7, réglages inchangés, champion VAL")
    oracle_report = oracle_run(oracle_path, output / "oracle")
    direction = yaml.safe_load((ROOT / "config/research_fr/direction_h5_shared_v1.yaml").read_text(encoding="utf-8"))
    direction.update(profile="fr_direction_h5_fold7_repaired_v1", outer_folds=[4, 5, 6, 7],
                     oracle_profile=str(oracle_path), oracle_source=oracle_report["artifact_directory"],
                     oracle_prediction_sha256=oracle_report["prediction_sha256"])
    direction_path = output / "direction_profile.yaml"
    direction_path.write_text(yaml.safe_dump(direction, sort_keys=False), encoding="utf-8")
    from modelFactory.fr_direction_h5_shared import run as direction_run
    LOG.info("Direction D1/middle/D10 : même branche Oracle, mêmes gates, champion VAL")
    direction_report = direction_run(direction_path, output / "direction")
    result = {"oracle": oracle_report, "direction": direction_report, "historical_robustness_not_fresh_oos": True,
              "confirmation_2026_evaluated": False, "canonical_writes": False,
              "rebuild_report_sha256": sha(rebuild / "rebuild_report.json")}
    write_json(output / "report.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = run(args.rebuild)
    print(json.dumps({"direction_verdict": result["direction"]["verdict"], "completed_folds": result["direction"]["completed_folds"]}))
