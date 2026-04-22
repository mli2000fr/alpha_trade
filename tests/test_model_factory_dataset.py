import pandas as pd

from modelFactory import dataset

def test_dataset_importable():
    assert hasattr(dataset, "__doc__")


def test_generate_walk_forward_splits_is_chronological() -> None:
    df = pd.DataFrame({"i": range(900)})

    splits = dataset.generate_walk_forward_splits(
        df,
        min_train_size=400,
        val_size=100,
        test_size=100,
        step_size=100,
        max_splits=3,
    )

    assert len(splits) == 3
    assert splits[0].train["i"].iloc[0] == 0
    assert splits[0].train["i"].iloc[-1] == 399
    assert splits[0].val["i"].iloc[0] == 400
    assert splits[0].test["i"].iloc[0] == 500
    assert splits[1].train["i"].iloc[-1] == 499
    assert splits[2].test["i"].iloc[-1] == 799


