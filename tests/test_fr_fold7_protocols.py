from pathlib import Path

import pytest
import yaml

from modelFactory.fr_direction_h5_shared import load_config as direction_config
from modelFactory.fr_oracle_h5_pilot import load_config as oracle_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name,loader,field,profile", [
    ("oracle_h5_pilot_v1", oracle_config, "folds", "fr_oracle_h5_fold7_repaired_v1"),
    ("direction_h5_shared_v1", direction_config, "outer_folds", "fr_direction_h5_fold7_repaired_v1"),
])
def test_versioned_extension_only(tmp_path, name, loader, field, profile):
    value = yaml.safe_load((ROOT / f"config/research_fr/{name}.yaml").read_text(encoding="utf-8"))
    path = tmp_path / "config.yaml"
    value[field] = [4, 5, 6, 7]
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    with pytest.raises(ValueError):
        loader(path)
    value["profile"] = profile
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    assert loader(path)[field] == [4, 5, 6, 7]
    value["seed"] = 999
    path.write_text(yaml.safe_dump(value), encoding="utf-8")
    with pytest.raises(ValueError):
        loader(path)
