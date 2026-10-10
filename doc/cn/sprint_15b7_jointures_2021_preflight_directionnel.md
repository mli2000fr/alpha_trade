# Sprint 15-B7 — Jointures Oracle 2021 et préflight directionnel réel

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

29 septembre 2026. Suite de [15-B6](./sprint_15b6_calendrier_et_extension_oracle_oof.md). Rapport canonique : [report.json](../../artifacts/research/cn_margin_lending/sprint15b7_preflight_v2/report.json).

**Verdict : `PASS_ACTUAL_FOLD_GATES_PROXY_ONLY`.** Les huit couples semestre × tâche satisfont les gates de population, classes et calendrier. Cela autorise à *étudier* le signal directionnel dans la campagne pré-enregistrée B6 ; cela ne démontre aucun gain de prédiction. Aucun modèle directionnel n'a été entraîné, aucun backtest économique n'a été exécuté, aucune table ni aucun serving n'ont été modifiés. `strict_ml_allowed=false`, `training_ready=false`, `serving_enabled=false`.

## 1. Question et périmètre

B5 avait construit les variables de financement sur marge SZSE et les jointures Oracle OOF de 2022 à 2025. Le protocole directionnel historique à huit folds était impossible : les six premiers folds manquaient d'un passé Oracle OOF suffisamment long. B6 a donc pré-enregistré **une nouvelle campagne**, avec des tests 2024H1/H2 puis 2025H1/H2, et a produit deux folds Oracle OOF H20 supplémentaires en 2021. B7 ne change ni le protocole B4/B5 ni les prédictions 2022–2025. Il répond seulement à deux questions : combien de candidats Oracle 2021 sont réellement appariables à la marge et aux variables prix, et les quatre folds prévus possèdent-ils, après purge, assez d'observations pour chacune des deux cibles ?

Les deux tâches sont `D1_VS_D10` (parmi les deux déciles extrêmes du rendement futur CN H20) et `D10_VS_REST` (D10 contre les autres déciles). Les déciles restent ceux de l'univers CN d'origine : ils ne sont jamais recalculés sur Shenzhen ou sur les seuls titres finançables.

## 2. Sources verrouillées et construction

Le [préflight B7](../../modelFactory/cn_margin_preflight_15b7.py) relit les empreintes SHA-256 du rapport et de l'audit B5, du protocole et de l'audit B6, des prédictions OOF Oracle 2021 et des fichiers de variables de marge. Il exige pour chaque extension 2021 le statut `OOS_RESEARCH_ONLY`, H20/LightGBM, les bonnes bornes de labels et l'absence de serving. Une divergence de source arrête le traitement. Les six nouvelles jointures sont enregistrées dans le dossier B7 ; les sources gelées restent inchangées.

Le chemin logique est :

```text
Tous les scores Oracle OOF CN de chaque séance
  → TOP20 calculé sur cette population CN complète
  → restriction aux instrument_id historiques XSHE
  → jointure prix et label CN H20
  → jointure marge « as-of » aux retards 2, 3 et 5 séances
  → masque commun prix + quatre variables marge + qualité du label
  → cible D1/D10 ou D10/reste, sans imputation
```

Le référentiel XSHE est le snapshot historique B4 **complet**, y compris les titres qui ne furent jamais éligibles au financement sur marge. C'est le dénominateur correct de la couverture. Une première sortie exploratoire dans `sprint15b7_preflight` avait, à tort, restreint ce dénominateur aux titres éligibles à la marge ; elle est **obsolète et ne doit pas être citée**. Le dossier `sprint15b7_preflight_v2` et ses empreintes constituent l'unique résultat B7 de référence.

## 3. Couverture 2021 observée

| Période | Scores Oracle CN | TOP20 CN | TOP20 XSHE | Quatre variables de marge valides, lag 2 | Paires complètes prix/marge/label, lag 2 | Dates | Titres | D1 ou D10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021H1 | 485 335 | 97 115 | 56 781 | 21 374 | 4 978 | 118 | 188 | 1 991 |
| 2021H2 | 548 063 | 109 661 | 64 798 | 21 623 | 5 166 | 125 | 194 | 2 177 |

Le taux de paires complètes rapporté au TOP20 XSHE n'est que **8,77 %** en 2021H1 et **7,97 %** en 2021H2. `Quatre variables de marge valides` et `paires complètes` ne sont pas synonymes : ces dernières exigent aussi les 33 variables prix, le montant moyen logarithmique et un label exploitable. Les candidats exclus ne sont pas remplacés par une valeur imputée ou par une éligibilité connue a posteriori.

Les retards de robustesse sont effectivement produits, pas seulement déclarés : 2021H1 conserve 4 978 paires aux lags 2, 3 et 5 ; 2021H2 en conserve respectivement 5 166, 5 164 et 5 161. Le lag 2 reste le choix principal fixé en B6 ; les lags 3/5 ne doivent pas servir à choisir ex post le meilleur résultat.

## 4. Gates des folds sur les lignes réelles

Les partitions suivent le calendrier de séances CN d'origine : 20 séances entières entre train et validation, fenêtre de validation de 126 séances, puis 20 séances avant le test. Une ligne train n'est retenue que si son label était disponible *strictement avant* la première décision de validation ; même règle pour la validation avant la première décision test. Le contrôle exige après ces purges au moins 504 dates train, 100 dates validation, puis 60 dates, 500 lignes, 20 titres et les deux classes dans chaque test. Les deux classes sont aussi exigées en train et validation.

| Fold et tâche | Dates train | Dates validation | Dates test | Lignes test | Titres test | Classes test 0 / 1 | Gates |
|---|---:|---:|---:|---:|---:|---:|---|
| 2024H1 · D1 vs D10 | 560 | 125 | 117 | 2 832 | 303 | 1 904 / 928 | PASS |
| 2024H1 · D10 vs reste | 560 | 125 | 117 | 8 746 | 417 | 7 818 / 928 | PASS |
| 2024H2 · D1 vs D10 | 677 | 125 | 125 | 6 026 | 332 | 3 364 / 2 662 | PASS |
| 2024H2 · D10 vs reste | 677 | 125 | 125 | 15 142 | 361 | 12 480 / 2 662 | PASS |
| 2025H1 · D1 vs D10 | 802 | 125 | 117 | 4 162 | 318 | 2 723 / 1 439 | PASS |
| 2025H1 · D10 vs reste | 802 | 125 | 117 | 10 392 | 377 | 8 953 / 1 439 | PASS |
| 2025H2 · D1 vs D10 | 919 | 125 | 105 | 4 311 | 336 | 2 774 / 1 537 | PASS |
| 2025H2 · D10 vs reste | 919 | 125 | 105 | 9 778 | 387 | 8 241 / 1 537 | PASS |

Toutes les vérifications explicites du rapport sont vraies et `blockers=[]`. Les comptes train et validation sont calculés sur la population de la tâche après masque commun et purge de disponibilité des labels, non déduits d'une simple borne calendaire. Les 125 dates de validation ne contredisent pas la fenêtre prévue de 126 séances : une séance peut ne produire aucune ligne éligible après filtrage.

## 5. Ce que ce PASS ne signifie pas

- Il ne donne ni AUC, ni précision TOP20, ni PnL, ni comparaison prix seule contre prix + marge. Une taille d'échantillon suffisante ne prouve pas qu'une variable prédit la direction.
- La couverture faible limite toute conclusion future à la sous-population XSHE effectivement finançable, appariée et qualifiée. Elle ne représente ni Shanghai ni l'intégralité du TOP20 Oracle.
- Le retard historique de publication SZSE est encore un **proxy**, pas une preuve du vintage accessible à la date de décision. Le verdict n'ouvre donc pas le ML strict ou le live.
- Les périodes 2025 avaient déjà été examinées dans d'autres recherches CN ; elles servent de confirmation historique au protocole B6, pas de holdout global vierge.
- Le protocole ancien B4 à huit folds reste bloqué. Le PASS concerne uniquement le calendrier B6 à quatre folds, sans réécrire l'histoire expérimentale.

## 6. Reproduction et suite

La sortie canonique est déjà présente. La commande suivante doit utiliser **un dossier de sortie neuf** ; le programme refuse de réécrire un dossier existant :

```powershell
python -u -m modelFactory.cn_margin_preflight_15b7 --output artifacts/research/cn_margin_lending/sprint15b7_reaudit_nouveau
```

Les [tests B7](../../tests/test_cn_margin_preflight_15b7.py) couvrent notamment le dénominateur XSHE historique, la purge des labels, les gaps, les classes et le refus de substituer l'éligibilité marge au référentiel. Avec les tests ciblés B1–B7 et Oracle 10-B, **62 tests passent** ; le contrôle de style et `git diff --check` passent également.

Étape expérimentale désormais **techniquement faisable**, mais non engagée ici : implémenter puis entraîner séparément la baseline prix et les extensions flux/encours/combinées, régression logistique et LightGBM, sur les deux tâches et quatre folds pré-enregistrés en B6. Comparer sur les mêmes lignes, appliquer les critères de stabilité, bootstrap et correction Bonferroni déjà figés. Aucun seuil, lag, fold ou population ne doit être choisi en fonction des résultats. Même une amélioration statistique ne suffira pas à certifier le PIT historique ni à activer le serving.
