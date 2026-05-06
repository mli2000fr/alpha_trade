"""Phase C / S15 — Preuves formelles d'invariants critiques.

Modules :

* ``idempotence_corporate_actions`` — clé idempotence CA (Section 5.3.a).
* ``oco_synthetic_bracket`` — exclusivité OCO (TP ⊕ SL).
* ``no_double_execution`` — verrou pipeline ⊥ backtest.

Toutes les preuves utilisent ``z3-solver`` (optionnel : skipif si non
installé).
"""

