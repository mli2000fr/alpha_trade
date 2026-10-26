# P06 — protéger50 % du gain observé après+10 % : protocole figé

22 octobre 2026. Recherche hors production, protocole avant résultats.
Le bilan P02 est consigné dans `experiences_done.md` avant ce nouveau GO.

## Une seule règle nouvelle

Même entrée Winner : deux clôtures régulières5m au-dessus du plus haut brut de
la veille après franchissement frais, entrée à l'open contigu suivant.
Même SL7 %, demi-cible, pas de renforcement, vente à l'open21 après vingt séances
depuis entrée incluse. Deux bras :

- **WINNER** : stop dur7 % et trailing15 % du sommet, contrat existant.
- **P06** : garder le stop dur ; **remplacer** le trailing15 % par la protection
  d'une fraction du gain, sans vente partielle ni TP en prix.

Avec E=prix réellement exécuté et P=maximum connu de l'entrée et des highs des
barres régulières **déjà terminées** :

1. Avant P≥`round(E*(1+0,10),2)` : uniquement `round(E*(1-0,07),2)`.
2. Après activation : `max(stop_dur, round(E+0,50*(P-E),2))`.
3. P ne redescend jamais : le stop ne peut donc pas être desserré. L'échéance
   ne redémarre pas à l'activation ; toutes les actions restent détenues.

Exemple E100/P120 : stop110, pas102comme TR15. Activation arrondie au cent pour
éviter que la représentation flottante de100×1,1 fasse manquer une cotation110.
SL initial : expression exacte du contrat existant `(1-0,07)`, pas substitution
par0,93 susceptible de différer d'un cent sur une borne demi-cent.

Le high d'une bougie ne peut pas protéger rétroactivement son low. Résoudre
d'abord le stop antérieur, puis observer le sommet en fin de bougie ; nouveau
stop applicable **au plus tôt à la suivante**. Un saut d'ouverture sous le stop
se traite au prix exécutable, pas au seuil garanti. L'ouverture future n'est pas
utilisée pour décider si le signal ou l'activation était admissible.

10 % et50 % sont figés, pas optimisés ; pas de P01, P02 ou autre filtre combiné.

## Périmètre, compte et coûts

Réutiliser les200entrées Winner/69titres de P01v2, validées et reproduites dans
P02. Les13réserves communes de couverture/maturité sont héritées sans sélection
par nouveaux résultats. Cohorte TOP10 CatBoost PATH H20 de recherche,
conditionnelle à des chemins futurs complets et survivants : pas tout le TOP10
quotidien ni le LightGBM de production.

2025 et2026 jusqu'au30septembre sont déjà étudiées, pas de holdout vierge.
2024 non simulée faute de couverture dans cette archive immuable.
Même capital annuel4 000USD, plafond1x, sizing/contraintes/comptabilité natifs,
risque B4DD15 et régime SPY de la veille. Frais8puis25bps parjambe, pas minimums
broker/quotes/fills historiques certifiés. Compte annuel remis à zéro, positions
encore ouvertes valorisées, pas liquidées fictivement.

Les quatre témoins doivent reproduire **octet pour octet** les trades, courbes,
décisions, financement et événements B4 de Winner P01v2. Même formule de sizing,
pas garantie des mêmes quantités après divergence d'equity/admissions.

## Vérifications

Moteur commun inchangé ; seules les fabriques locales de classe/résolveur sont
substituées pendant le rejeu série, puis restaurées même en cas d'erreur.
Aucun fichier source historique ou configuration de production réécrit.

Sorties reconstruites par un résolveur scalaire distinct de `gain_stop`, puis
cash/valorisations/frais et chaque snapshot d'ouverture B4 revérifiés par
l'auditeur existant. Traces d'activation avec premier instant d'observation,
sommet, stop et échéance ; vérifier disponibilité et absence de high futur.
Tests : activation pile+10 %, seuil demi-cent, ratchet, absence de vente partielle,
collision stop avant activation, effet au prochainbar, gaps et horizon inchangé.
Même assistant, pas revue humaine indépendante, pas parité live complète d'ordres
remplacés ; latence réelle de remplacement et ordre des ticks non qualifiés.

## Mesures et critères

Huit cas année×bras×friction. Publier rendement/capital final, DD, taux gagnants,
gains/pertes moyens, durée, exposition, positions ouvertes et activations.
Rendements unitaires appariés sur mêmes entrées, puis non-chevauchement conservateur
OracleJ+40. Grouper les unités parannée Oracle et les portefeuilles parannée
d'entrée, avec les rares reports de décembre→janvier déjà présents.

Nécessaire pour justifier seulement une confirmation ultérieure :30occasions
non chevauchantes et10activations parannée ; surplus de portefeuille positif
en2025/2026 aux deux frictions ; DDnon dégradé chaque année aux frais normaux ;
surplus unitaire aux frais stressés positif les deux années ; borne basse95 %
du bootstrap mensuel >0 (minimum6mois,2 000tirages,graine731).

Sinon `NO_GO_P06_NOT_CONFIRMED` ou `INSUFFICIENT_P06_SAMPLE`. Pas d'ajustement
des seuils après résultat ni de choix rétrospectif du bras selon l'année.
Même si tous passent, pas de promotion automatique sur deux années déjà vues.

## Suivi

Programmes `scripts/research/us_oracle_gain_lock_p06.py` et
`scripts/research/us_oracle_gain_lock_p06_audit.py`.
Dossier `artifacts/research/us_oracle_gain_lock_p06/20261022-v1` : protocole,
progression, signaux, sorties unitaires, `annual-summary.csv`, `report.json`,
`final-audit.json`, trades/courbes/risque et `gain-lock-activations.json` parcas.
Aucun accès SQL, fournisseur, LLM, entraînement, ordre, activation live ou
modification de modèle, batch ou configuration de production.
