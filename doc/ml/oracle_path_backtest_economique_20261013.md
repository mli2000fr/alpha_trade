# Oracle parcours H20 — backtest économique LightGBM

## Objet et statut

GO utilisateur du 13 octobre 2026. Lancement local le **13 octobre à 23:24 Paris**,
processus lanceur **34616**. **Neuf cas terminés à 23:34 Paris**, sans échec,
empreintes finales vérifiées. Résultats exploratoires, aucune promotion live.
**66 tests ciblés passent**, dont TP, gap sous SL, expiration et cash du moteur partagé.
Démarrage vérifié : premier cas `2024-TOP10`, 161/273 séances à 23:25 Paris,
huit positions en cours et 90 legs clos ; aucune erreur de lancement.

| Année | TOP10 net | TOP20 net | TOP50 net |
| --- | ---: | ---: | ---: |
| 2024 | −1,07 % | −1,84 % | −1,84 % |
| 2025 | −5,54 % | −4,49 % | −2,98 % |
| 2026 partiel | +9,23 % | +10,44 % | +9,01 % |

Le détail est dans `report.json` et `annual-summary.csv`. L'audit ultérieur
des pertes/trajectoires est documenté dans
[Audit des pertes 2024–2026](oracle_path_audit_pertes_20261013.md).

Le choix LightGBM est le choix opérationnel demandé. Le dernier fold avait
sélectionné **CatBoost sur validation** : ce test ne réécrit pas ce résultat et
ne présente pas LightGBM comme le champion de validation.

## Modèle, données et sélection

- Modèle original LightGBM de `oracle_path_comparison/20261013-v1`, fold
  `2023-01-05`. Dernière disponibilité des labels d'entraînement : 2022-07-06 ;
  de validation : 2023-01-04. Aucun réentraînement pour ce test.
- Scores originaux de `oracle_path_confirmation/20261013-v1/scores.parquet`,
  branche `score_lightgbm`. Les copies tabulaires de la comparaison LSTM
  **ne sont pas utilisées**.
- Univers figé : **1 790 titres**, issu du fichier tradable lors de la comparaison.
  Univers actuel de survivants, pas reconstruction historique sans biais de survie.
- TOP **10 / 20 / 50 titres**, pas pourcentages. Tri par score décroissant puis
  symbole croissant en cas d'égalité, **avant** les contrôles de qualité/risque.
- Pas de sélection sur les rendements futurs ou sur les seules dates dont les
  labels rétrospectifs sont complets ; aucune substitution par le titre suivant.
- Pas d'intersection Oracle × ATR dans cette expérience. L'ATR reste utilisé
  pour le sizing natif et les contrôles d'entrée.
- Force d'allocation : percentile du score sur toute la population scorée à J,
  avant TOP-K. Ce percentile **n'est pas une probabilité de hausse**.
- Politique **LONG-only explicite** : ce modèle apprend l'amplitude maximale
  absolue HIGH/LOW pendant J+1…J20, pas la direction.

## Portefeuille et périodes

Capital initial : **4 000 USD par portefeuille annuel**, neuf cas indépendants,
sans composition du capital d'une année à l'autre. Mêmes moteurs de risque,
ledger, coûts canoniques et lifecycle que les replays précédents, avec leur
configuration de recherche figée : huit positions maximum, sizing ATR,
contraintes de secteur/corrélation, régime et circuit breaker. Ce n'est pas une
affirmation de parité exacte avec tous les paramètres du compte live actuel.

Entrée à l'ouverture J+1 ; **TP 20 % / SL 10 %** du prix réellement exécuté ;
**pas de trailing**. Sans sortie antérieure, vente à l'ouverture après vingt
séances depuis l'entrée (J+21 depuis la décision). Une perte sur gap peut
dépasser 10 % ; elle n'est pas artificiellement plafonnée.

| Cohorte | Dernière décision | Dernière séance de sortie possible |
| --- | --- | --- |
| 2024 | 2024-12-31 | 2025-02-03 |
| 2025 | 2025-12-31 | 2026-02-02 |
| 2026 | **2026-09-02** | **2026-10-02** |

Les dates exactes font foi dans `manifest.json`. Pour 2026, la borne souhaitée
était le 10 septembre avec sorties jusqu'au 9 octobre. Les cinq journées macro
du 5 au 9 octobre manquent aussi en base après lecture SELECT : **réduction
globale de la période**, pas exclusion de jours perdants ni forward-fill.

Prix et événements : archive qualifiée `us_oracle_tp20_sl10_new/20261012-v6`,
avec corrections documentées et continuation d'identité. Identités, OHLCV,
absence de barres remplies et ATR sont vérifiés sur J et les vingt séances
précédentes pour les entrées. Toute anomalie d'une position détenue bloque le
cas ; aucun titre détenu ne disparaît silencieusement du PnL. Une créance
d'opération sur titres non valorisée interdit un résultat économique complet.

## Suivi et fichiers

Dossier : `artifacts/research/us_oracle_path_economic/20261013-v1`.

```powershell
Get-Content F:\projets\artifacts\research\us_oracle_path_economic\20261013-v1\progress.json
Get-Content F:\projets\artifacts\research\us_oracle_path_economic\20261013-v1\stderr.log -Tail 20 -Wait
```

`progress.json` suit les neuf cas ; chaque dossier `2024-TOP10`, etc., possède
sa propre progression par séance. `manifest.json` fige sources, modèle, dates,
risque, exécution et empreintes. Les candidats et rejets de qualité sont archivés.
Les cas terminés sont repris uniquement après vérification de leurs empreintes ;
un verrou empêche deux lanceurs sur le même dossier. Un cas échoué arrête la
campagne et laisse les résultats déjà terminés visibles.

À la fin : `report.json`, `annual-summary.csv`, et pour chaque cas,
`case-report.json`, `trades.parquet`, `daily.parquet`, décisions, régimes et
exécutions. Chiffres : montant gagné/perdu, nombre et pourcentage de positions
gagnantes/perdantes, profit factor, drawdown maximal, capital final, exposition
moyenne/maximale et réconciliation cash. Le capital marqué à la coupe annuelle
est distingué du capital final après liquidation des cohortes.

## Limites et sécurité

Secteurs actuels acceptés mais non PIT ; vintages macro non certifiés ; prix
journaliers ajustés, pas bid/ask/fills broker ; contacts intrabar conservateurs.
Les années ont déjà été explorées et ne sont pas des holdouts vierges.
**Aucun entraînement, aucune écriture SQL, aucun appel courtier ni ordre,
aucune modification des modèles, batchs ou réglages de production.**

Source : `scripts/research/us_oracle_path_economic_replay.py`.
