"""modelFactory/global_direction — GlobalDirection H20 (recherche anti-D1).

Objectif : séparer les futurs **D10** (bon long) des futurs **D1** (mauvais
long) dans l'univers Extreme, SANS prédire l'amplitude.

- Labels par date : ``future_return H20`` TOP 10% cross-sectionnel → y=1 (D10) ;
  BOTTOM 10% → y=0 (D1) ; D2-D9 exclus de l'entraînement.
- PIT strict + walk-forward causal identique à l'Oracle.
- ``proba_extreme`` n'est PAS une feature (premier test).
- Sortie : ``direction_score = P(D10 plutôt que D1)``, calculée pour TOUT
  l'univers à l'inférence.

Pipeline de test (``pipeline.py``) : Oracle = gate (top 20% du jour), 
GlobalDirection = ranking (top m24 dans le pool), LONG only.

Modules :
- ``dataset.py`` : features PIT + labels D1/D10 (depuis ``global_oracle_labels``).
- ``walk_forward.py`` : entraîne GlobalDirection par folds causaux + OOS.
- ``pipeline.py`` : A = Oracle pur / B = Oracle+B25 / C = Oracle+GlobalDirection.
"""
