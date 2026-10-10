# Sprint 15-D1 — Pilote des prévisions de résultats CN sous proxy PIT

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

Réalisé le 29 septembre 2026. **Verdict : faisabilité documentaire confirmée, mais pas de GO pour un entraînement historique ni pour le serving.** Les annonces de prévisions des émetteurs existent dans l'archive officielle CNINFO et une correction a été contrôlée dans son PDF. En revanche, le seul inventaire de masse trouvé est une archive Eastmoney actuelle, pas un journal historique des versions. Le signal récent est rare sur les décisions Oracle TOP20.

Ce pilote n'a modifié ni les tables CN, ni les features, ni les modèles, ni les règles de backtest/live. Il a produit des artefacts de recherche seulement.

## Contrat et périmètre

Population : les quatre fichiers de prédictions OOF H20 LightGBM de `artifacts/cn/oracle/sprint10b`, semestres 2024H1–2025H2. La sélection TOP20 reprend la fonction de référence de `modelFactory/cn_oracle_walk_forward.py` : lignes dont `target_quality_valid` est vrai et `baseline_score` défini, tri quotidien par `oracle_score` décroissant puis `instrument_id`, et plafond de 20 % de l'effectif de chaque séance. Ce n'est **pas** la cohorte réduite de 16 titres de 15-D0.

Inventaire de masse : rapport public `RPT_PUBLIC_OP_NEWPREDICT` d'Eastmoney, onze exercices fiscaux trimestriels de 2023-03-31 à 2025-09-30, pagination complète et contrôle du nombre annoncé. Seuls le code, la date affichée, l'exercice, la métrique et le marché servent à la découverte. Les prévisions numériques, les indicateurs `IS_LATEST` et toute valeur potentiellement révisée **ne sont jamais des features** dans ce pilote.

PDF de vérification : huit documents CNINFO sur `605081`, `300054`, `000603` (quatrième code recherché `600519` : aucune annonce dans la catégorie/période choisie). Fichiers, SHA-256, titres, dates et texte extrait sont conservés dans l'artefact local. Les PDF originaux et corrigés de `605081` avaient été pré-enregistrés comme paire à vérifier.

Jointure : dernière date d'annonce **strictement antérieure** à la date du signal, jamais jour J ni futur ; âges en jours calendaires. Cette règle prudente n'établit pas l'heure réelle de disponibilité et ne transforme pas l'archive en PIT certifié.

## Couverture observée

L'inventaire Eastmoney contient **34 503 lignes** de métriques, soit **12 900 couples code/date** distincts. L'Oracle sélectionne **464 834 observations TOP20**, sur **5 104 titres**. Une ligne avec une vieille annonce n'est pas un nouveau signal : les fenêtres 20 et 90 jours sont les chiffres utiles.

| Population TOP20 | Lignes | Annonce antérieure ≤ 20 j | ≤ 90 j | ≤ 365 j |
| --- | ---: | ---: | ---: | ---: |
| Total | 464 834 | 23 831 (5,13 %) | 114 749 (24,69 %) | 319 365 (68,70 %) |
| 2024H1 | 117 162 | 6 568 (5,61 %) | 37 164 (31,72 %) | 75 889 (64,77 %) |
| 2024H2 | 125 221 | 5 831 (4,66 %) | 22 291 (17,80 %) | 91 880 (73,37 %) |
| 2025H1 | 116 793 | 6 162 (5,28 %) | 36 554 (31,30 %) | 79 407 (67,99 %) |
| 2025H2 | 105 658 | 5 270 (4,99 %) | 18 740 (17,74 %) | 72 189 (68,32 %) |

Par board, une annonce ≤ 20 j concerne 5 221/160 312 observations ChiNext, 6 325/96 907 Shanghai Main, 4 617/107 331 STAR et 7 668/100 284 Shenzhen Main. Par décile réel, D1 : 4 406/109 295 (4,03 %) ; D10 : 3 750/64 632 (5,80 %). **Ce contraste descriptif ne mesure aucune précision directionnelle**, car il n'est ni apparié ni ajusté pour la période, le secteur, la taille et la répétition des mêmes titres.

Le 15-D0 avait 21/279 observations sous 20 jours et 93/279 sous 90 jours dans un **petit échantillon sélectionné pour la marge**. Les taux diffèrent naturellement : univers, population et source de l'inventaire différents. Le présent chiffre est celui de l'Oracle OOF complet, mais demeure une couverture **de métadonnées d'archive**, pas de valeurs financières valides.

## Vérification des PDF et anomalie de version

Les huit PDF se lisent (2 à 4 pages chacun). Sept exercices/périodes ont été reconnus initialement, puis huit après prise en charge des titres `2023年度` sans deuxième caractère `年`. Les huit restent en `QUARANTINED_MANUAL_VALIDATION_REQUIRED` pour les chiffres : l'extracteur reconnaît titre, exercice, période et correction, **pas** encore une série numérique publiable.

Exemple contrôlé visuellement sur la page 2 du [PDF officiel de correction 605081](https://static.cninfo.com.cn/finalpage/2025-04-23/1223214895.PDF), puis confronté au [PDF original](https://static.cninfo.com.cn/finalpage/2025-01-25/1222428933.PDF) :

| Prévision 2024, unité du tableau : 万元 (10 000 CNY) | Originale | Corrigée |
| --- | ---: | ---: |
| Perte nette attribuable aux actionnaires de la société mère, en valeur absolue | 27 100–32 100 | 32 100–35 000 |
| Chiffre d'affaires | 13 000–17 000 | 10 000–12 000 |

Le même PDF de correction rappelle **l'ancienne valeur et la nouvelle** ; sélectionner naïvement la première ou la dernière occurrence d'un nombre produirait une fausse feature. Les signes « perte », les bornes, l'unité et la métrique doivent être conservés ensemble. Le PDF corrigé indique une annonce précédente au **24 janvier 2025**, tandis que le PDF original archivé est daté/signé du **25 janvier 2025** : cette discordance d'un jour doit être arbitrée avant toute décision d'ouverture. Plusieurs notices CNINFO de l'audit 15-D0 portent en outre `00:00:00` comme heure apparente, non une preuve de disponibilité dès minuit.

## Décision et suite éventuelle

**15-D1 = `DOCUMENT_FEASIBLE / HISTORICAL_PIT_NOT_PROVEN / NO_ML_GO`.** L'archive permet une étude de faisabilité mais pas une comparaison OOF honnête « prix seul vs surprise de guidance » à ce stade. Sur tout l'Oracle, environ 95 % des lignes n'ont pas d'annonce même datée dans les 20 jours précédents. Un futur modèle devrait donc être **événementiel avec abstention**, non une feature numérique propagée à toutes les dates.

Avant une expérience directionnelle : (1) certifier l'historique des versions et une règle de disponibilité au plus tôt J+1/J+2 ; (2) vérifier juridiquement/techniquement la collecte de masse ; (3) construire un extracteur à sorties typées métrique, exercice, unité, signe et bornes, avec paires original/correction testées manuellement ; (4) calculer la couverture **des valeurs extraites valides et nouvelles**, puis la puissance statistique D1/D10 par semestre et board ; (5) pré-enregistrer seulement alors une ablation OOF appariée. Ne pas entraîner sur les `PREDICT_HBMEAN` ou autres agrégats de l'archive actuelle.

Reproduction : `service/market/cn_guidance_pilot_15d1.py` crée l'inventaire/rapport ; `scripts/research/cn_guidance_pdf_review_15d1.py` extrait les huit PDF avec un Python contenant `pypdf`. Artefacts : `artifacts/research/cn_guidance_15d1/pilot-20260929/report.json`, `review-v2/pdf_review.json`, métadonnées et PDF locaux. Cinq tests ciblés passent dans `tests/test_cn_guidance_pilot_15d1.py`.
