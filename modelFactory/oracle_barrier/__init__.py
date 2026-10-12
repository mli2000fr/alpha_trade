"""Isolated first-touch Oracle research namespace. No terminal Oracle serving."""

MODE = "oracle_tp_before_sl"
TARGETS = {"long": "long_tp_before_sl", "short": "short_tp_before_sl"}
SCORES = {"long": "proba_long_tp_before_sl", "short": "proba_short_tp_before_sl"}
ANY_TARGET = "either_tp_before_sl"
ANY_SCORE = "max_tp_before_sl_score"  # max of two scores, NOT a calibrated union probability
