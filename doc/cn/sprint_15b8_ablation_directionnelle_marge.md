# Sprint 15-B8 — Ablation directionnelle des données de marge SZSE

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

29 septembre 2026. Suite du [préflight B7](./sprint_15b7_jointures_2021_preflight_directionnel.md), suivant le [protocole B6 pré-enregistré](./sprint_15b6_calendrier_et_extension_oracle_oof.md).

## Objet et limites

Cette campagne teste si deux familles de variables de financement sur marge apportent un signal **directionnel incrémental** aux variables prix, sur la sous-population de candidats Oracle H20 TOP20 qui peut effectivement être appariée à Shenzhen. Les tâches sont `D1_VS_D10` et `D10_VS_REST`. Le TOP20 Oracle est calculé en amont sur toute la coupe CN, avant toute restriction à Shenzhen, à la marge ou aux labels futurs. Les vrais déciles H20 restent ceux de la coupe CN originale.

Il s'agit exclusivement d'artefacts de recherche. Les archives SZSE ne disposent pas d'une preuve du vintage historiquement accessible au moment de chaque décision ; leur disponibilité utilisée ici est retardée de deux séances **par convention proxy**. Même un gain statistique ne suffit donc ni à certifier un historique PIT strict, ni à activer une décision live.

## Population, variables et modèles

Le [runner B8](../../modelFactory/cn_margin_directional_15b8.py) lit les jointures B7 (2021) et B5 (2022–2025) sans les altérer. Il contrôle les empreintes des rapports, du protocole et de chaque jointure. Le masque commun exige prix valides, les quatre variables de marge valides et un label valide ; une ligne absente d'une extension n'est pas imputée à zéro dans la baseline. Ainsi les quatre bras d'un même fold et d'une même tâche voient **exactement les mêmes lignes train, validation et test**.

| Bras | Entrées supplémentaires aux 33 variables prix et au logarithme du montant moyen historique 20 séances |
|---|---|
| `PRICE_BASELINE` | Aucune |
| `PRICE_MARGIN_FLOW` | `financing_buy_to_amount`, moyenne 5 séances |
| `PRICE_MARGIN_BALANCE` | Variations d'encours 5 et 20 séances |
| `PRICE_MARGIN_COMBINED` | Les quatre variables de marge |

Les paramètres sont ceux des YAML figés B6/B4 : régression logistique L2 (`C=1`, `lbfgs`, 2 000 itérations) avec standardisation **apprise sur train seulement**, ou LightGBM (300 arbres, profondeur 5, taux 0,03, 31 feuilles, minimum 150 lignes par feuille, régularisation L2 1). Pas de pondération de classes, calibration, early stopping ni optimisation de seuil. La validation sert ici au contrat temporel et aux contrôles, pas à choisir un modèle après lecture des résultats.

Chaque fold laisse 20 séances avant la validation et 20 avant le test ; les labels train doivent avoir été disponibles strictement avant la première décision validation, et ceux de validation avant le test. Les modèles sont réentraînés séparément pour chaque tâche, semestre et famille. Quatre semestres test : développement 2024H1/H2, confirmation historique 2025H1/H2. La période 2025 n'est pas un holdout global vierge.

## Métriques et décision

La population test est identique par construction entre la baseline et chaque extension. La comparaison principale est l'AUC agrégée des quatre semestres avec **poids égal par date** : chaque ligne reçoit l'inverse du nombre de candidats de sa séance. La précision TOP20 directionnelle est d'abord calculée au sein de chaque séance, puis moyennée à poids égal par date. Les égalités de score sont départagées par `instrument_id`, jamais par le futur.

Les douze hypothèses principales sont `2 tâches × 2 modèles × 3 extensions`, au retard fixé de deux séances. Pour chacune, un bootstrap de 1 000 tirages de mois calendaires estime l'intervalle bilatéral du gain d'AUC ; le seuil individuel est `0,05 / 12` (Bonferroni). Les mois tirés plusieurs fois conservent leur multiplicité dans les poids. Un signal de recherche ne passe que si **tous** les critères pré-enregistrés sont vrais :

1. gain d'AUC agrégée d'au moins +0,015 ;
2. gain positif dans au moins trois des quatre folds, dont **les deux** folds de confirmation 2025 ;
3. gain de précision TOP20 directionnelle d'au moins +0,02 ;
4. au plus 30 % des vrais positifs du TOP20 de la baseline prix retirés de la nouvelle sélection ;
5. borne inférieure de l'intervalle bootstrap corrigé strictement positive.

Les retards trois et cinq séances sont des sensibilités **descriptives** réservées ; ils ne peuvent pas être choisis après les résultats pour produire un GO. Aucun signal ne sera interprété comme preuve de rendement de portefeuille ou de réduction des pertes sans replay économique distinct.

## Exécution et suivi

La sortie de cette campagne se trouve dans `artifacts/research/cn_margin_lending/sprint15b8_directional_20260929`. Chaque combinaison tâche/modèle/semestre possède un `report.json` et un `predictions.parquet` avec empreinte SHA-256. Le rapport racine est mis à jour après chaque fold ; `completed_folds` vaut 16 une fois les **64 entraînements de bras** terminés. Il reste ensuite le bootstrap des 12 comparaisons. Le statut final attendu du rapport racine est `COMPLETED_RESEARCH_PROXY_ONLY`. Un dossier existant n'est jamais écrasé.

Commande de reproduction, uniquement dans un **nouveau** dossier :

```powershell
python -u -m modelFactory.cn_margin_directional_15b8 --output artifacts/research/cn_margin_lending/sprint15b8_reproduction_nouvelle
```

Les [tests B8](../../tests/test_cn_margin_directional_15b8.py) vérifient notamment la sélection TOP20 quotidienne, le poids égal par date, la multiplicité bootstrap des mois répétés, l'interdiction des variables futures et l'absence d'imputation silencieuse.

Vérification finale : **67 tests ciblés B1–B8 et Oracle 10-B passent** ; style valide. Un contrôle indépendant des 16 dossiers confirme les empreintes des prédictions, l'absence de clés dupliquées et l'identité des populations test et labels entre régression logistique et LightGBM.

## Résultats et verdict

Le [rapport final](../../artifacts/research/cn_margin_lending/sprint15b8_directional_20260929/report.json) porte le statut `COMPLETED_RESEARCH_PROXY_ONLY` ; les 16 dossiers tâche × modèle × fold ont chacun une prédiction OOF et une empreinte vérifiée. Les quatre variantes de chaque dossier ont été ajustées, soit **64 entraînements**. Les 12 comparaisons incrémentales concluent toutes `NO_GO_INCREMENTAL_MARGIN`.

| Tâche | Modèle | Extension | AUC baseline → extension, poids/date | Δ AUC | Δ précision TOP20 | Folds Δ AUC > 0 | Borne inférieure bootstrap corrigée |
|---|---|---|---:|---:|---:|---:|---:|
| D1/D10 | Logistique | Flux | 0,6351 → 0,6331 | −0,0020 | −0,0008 | 3/4 | −0,0135 |
| D1/D10 | Logistique | Encours | 0,6351 → 0,6362 | +0,0011 | −0,0017 | 2/4 | −0,0020 |
| D1/D10 | Logistique | Combiné | 0,6351 → 0,6345 | −0,0006 | +0,0008 | 2/4 | −0,0112 |
| D1/D10 | LightGBM | Flux | 0,6291 → 0,6270 | −0,0022 | +0,0123 | 1/4 | −0,0087 |
| D1/D10 | LightGBM | Encours | 0,6291 → 0,6282 | −0,0010 | +0,0083 | 2/4 | −0,0055 |
| D1/D10 | LightGBM | Combiné | 0,6291 → 0,6297 | +0,0005 | +0,0102 | 2/4 | −0,0083 |
| D10/reste | Logistique | Flux | 0,5340 → 0,5322 | −0,0018 | ~0,0000 | 2/4 | −0,0089 |
| D10/reste | Logistique | Encours | 0,5340 → 0,5343 | +0,0003 | −0,0004 | 3/4 | −0,0013 |
| D10/reste | Logistique | Combiné | 0,5340 → 0,5329 | −0,0011 | +0,0006 | 3/4 | −0,0063 |
| D10/reste | LightGBM | Flux | 0,5477 → 0,5447 | −0,0030 | −0,0047 | 2/4 | −0,0132 |
| D10/reste | LightGBM | Encours | 0,5477 → 0,5483 | +0,0006 | −0,0012 | 2/4 | −0,0048 |
| D10/reste | LightGBM | Combiné | 0,5477 → 0,5442 | −0,0034 | −0,0063 | 2/4 | −0,0134 |

Le meilleur Δ AUC observé est seulement **+0,0011**, loin du seuil fixé à **+0,015**. Le meilleur uplift de précision est **+0,0123**, sous le seuil de **+0,02**. Les douze bornes inférieures Bonferroni sont négatives. Même les variantes avec deux semestres 2025 positifs restent trop faibles et instables sur les quatre folds. Le veto de perte de vrais positifs du TOP20 baseline n'est, lui, jamais le blocage principal : la fraction retirée reste entre environ 2,5 et 26,5 %, sous le plafond de 30 %.

**Décision : ne pas intégrer ces quatre variables de marge au modèle directionnel CN dans ce cadre.** Ce verdict concerne uniquement la population appariée XSHE, les deux tâches H20, les deux familles de modèles et les paramètres pré-enregistrés. Il ne dit pas que les données de marge sont inutiles pour tous les usages ou horizons. Ne pas chercher un lag ou seuil favorable sur les mêmes données pour renverser ce NO-GO. La certification PIT historique et le serving restent fermés indépendamment du résultat.
