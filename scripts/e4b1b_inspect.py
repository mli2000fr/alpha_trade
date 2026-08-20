"""E4-B1b — inspection des colonnes du dataset O1 pour la population Extreme."""
from __future__ import annotations

import pandas as pd


def main() -> None:
    ds = pd.read_parquet("artifacts/models/oracle/e2_feature_dataset.parquet")
    print("e2_feature_dataset shape:", ds.shape)
    cols = [c for c in ds.columns if any(k in c.lower() for k in ["date", "symbol", "oracle", "future", "extreme", "rank", "return"])]
    print("colonnes cibles:", cols)
    print(ds[cols].head(3).to_string())
    oos = pd.read_parquet("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
    print("\noos_predictions shape:", oos.shape, "cols:", list(oos.columns))


if __name__ == "__main__":
    main()
