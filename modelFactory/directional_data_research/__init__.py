"""modelFactory/directional_data_research — Recherche de données directionnelles.

Clôture : GlobalDirection V1/V2 = **NO-GO** (182 features actuelles : la direction
n'est pas observable — IC_décile max 0.033, AUC_direction max 0.515).

Ce module recherche de NOUVELLES familles de données **signées** capables de
séparer les futurs mauvais longs (D1-D5) des bons longs (D6-D10) dans le pool
Oracle TOP20%.

Discipline (avant tout modèle) :
  1. IC(feature, décile futur) ;
  2. AUC(D1-D5 vs D6-D10) et AUC(D1-D3 vs D8-D10) ;
  3. par fold / année / régime ;
  4. stabilité du signe par fold ;
  5. direction_separability vs amplitude_separability (ne pas réapprendre Oracle).

Une famille ne passe au modèle multivarié que si PLUSIEURS features montrent un
signal directionnel OOS stable.

Priorité : estimate/earnings revisions → news sentiment → options skew →
short interest / analyst revisions / insiders → premarket/flux directionnels PIT.

Modules :
- ``harness.py`` : harnais de séparabilité réutilisable (pool Oracle + métriques).
- ``earnings_revisions.py`` : première famille — estimate/earnings revisions.
"""
