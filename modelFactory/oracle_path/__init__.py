"""Independent path-amplitude Oracle; legacy constants keep H20 callers compatible."""

TARGET = "oracle_path_extreme20"
SCORE = "proba_path_extreme"
MODE = "oracle_path_h20"
HORIZON = 20
HORIZONS = (10, 15, 20)


def validate_horizon(horizon):
    if type(horizon) is not int or horizon not in HORIZONS:
        raise ValueError('Oracle parcours : horizon 10, 15 ou 20 séances requis')
    return horizon


def target_name(horizon=HORIZON):
    return f'oracle_path_extreme{validate_horizon(horizon)}'


def mode_name(horizon=HORIZON):
    return f'oracle_path_h{validate_horizon(horizon)}'
