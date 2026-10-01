# Sprint 15-D7 — Protocole apparié Dragon/Tiger, sans lecture des issues

État au 30 septembre 2026 : **pré-enregistrement et moteur d'appariement outcome-blind livrés**. Aucun entraînement, backtest ou changement de serving D7. La première exécution réelle du préflight est [ici](../../artifacts/research/cn_dragon_tiger_15d7/preflight-20260930/report.json) : une séance prospective exploitable pour l'audit temporel, 64 lignes de motifs, 60 titres distincts. Un export Oracle OOS de recherche existe désormais pour la décision du 8 octobre, mais D7 ne l'apparie pas avant que son cutoff soit passé ; aucun résultat directionnel n'est acquis.

## Audit complémentaire de l'export Oracle 2026

Le [préflight de disponibilité](../../service/market/cn_oracle_export_readiness_15d7.py), exécuté en lecture seule, a produit un [rapport initial](../../artifacts/research/cn_dragon_tiger_15d7/oracle-export-readiness-20260930-v2.json) **avant** le rattrapage : il constatait alors zéro barre 2026. Ce constat n'est plus l'état courant. Le [Sprint 15-D7a](./sprint_15d7a_rattrapage_canonique_2026.md) a ensuite chargé 180 séances ouvertes et 936 103 barres d'actions jusqu'au 29/09/2026. Le [rapport final après rattrapage](../../artifacts/research/cn_dragon_tiger_15d7/oracle-export-readiness-20260930-final.json) ne signale plus que `NO_VALID_2026_PROSPECTIVE_ORACLE_CANDIDATE_EXPORT`. Le [Sprint 15-D8](./sprint_15d8_export_oracle_prospectif.md) implémente désormais cet export pour une future séance, sans rétrodatation ni serving.

Après le premier export D8, le [rapport de prévalidation](../../artifacts/research/cn_dragon_tiger_15d7/oracle-export-readiness-20260930-d8-preview.json) contrôle **1 034 candidats** sans erreur et affiche `WAITING_FOR_DECISION_CUTOFF` pour le 08/10/2026. Cette prévalidation lit un snapshot déjà observé avant le cutoff futur, mais n'apparie aucun événement. Le chargeur utilisé par l'appariement garde le comportement strict : il exclut les cutoffs futurs. Le snapshot officiel du passage D6 avant ouverture à 08:30 Shanghai peut encore modifier la liste ; le dernier snapshot complet observé avant 09:15 fera foi.

Un smoke BaoStock du 29/09/2026, **sans aucune persistance**, a réussi sur cinq titres (16 appels, zéro échec) ; une requête ciblée a retourné une barre du 29/09 pour `sh.600519` et `sz.000001`. Cela confirme une source potentielle de rattrapage, **pas** une couverture complète de l'univers ni une observation avant 09:15 du 30/09. Il serait incorrect de transformer ces données téléchargées après la décision en prédictions prospectives de septembre.

Le chemin de rattrapage a été réalisé séparément en D7a : calendrier officiel 2026 vers `market_sessions`, OHLCV/facteurs/statuts BaoStock 2026 vers le staging puis les tables CN, avec promotion insert-only bornée à 2026. Le canonicaliseur historique Sprint 7-B n'a pas été relancé tel quel : ses `ON DUPLICATE KEY UPDATE` auraient touché des lignes 2018–2025 et leurs horodatages. Cette écriture de masse n'a pas été déclenchée par le moteur d'appariement D7.

Commande de contrôle reproductible, sans écriture métier :

```powershell
python -m service.market.cn_oracle_export_readiness_15d7 --report artifacts/research/cn_dragon_tiger_15d7/readiness-NOUVELLE_DATE.json
```

Le rapport n'est jamais écrasé. Une fois un export candidat produit, `--candidates CHEMIN.parquet` valide son schéma et ses horodatages via le moteur D7 ; un tel résultat resterait soumis à l'audit indépendant du manifeste d'entraînement Oracle, du vrai TOP20 quotidien et des droits de données.

## Question causale et population

Sur les **candidats Oracle H20 TOP20 réellement prédits avant une décision à 09:15 Shanghai**, une présence sur la liste officielle Dragon/Tiger connue avant cette décision apporte-t-elle une information supplémentaire pour (a) écarter un futur D1 et (b) retenir un futur D10 ? Le groupe de comparaison comprend des candidats Oracle TOP20 sans événement dans le **même snapshot officiel complet**. Une date sans snapshot ne devient jamais artificiellement « sans événement ».

L'événement de séance J n'est admissible que pour la **séance ouverte suivante K**, avec une observation de notre collecteur strictement antérieure à 09:15 K. Si deux passages officiels ont eu lieu avant ce seuil, le dernier fait foi : il peut ajouter ou retirer un titre. Une version publiée/observée après 09:15 est exclue. Le collecteur [15-D6](./sprint_15d6_collecte_prospective_dragon_tiger.md) constitue l'unique source du statut événementiel prospectif. Une observation faite avant le seuil n'est pas à elle seule une certification PIT historique ou un droit de réutilisation commerciale.

## Variables permises au moment de la décision

Le fichier de candidats `.parquet` ou `.csv` comporte une ligne par `(decision_date, exchange, code)` et les colonnes suivantes :

| Colonne | Contrat |
| --- | --- |
| `decision_date`, `exchange`, `code`, `board_code` | Séance K, SSE/SZSE, code action à six chiffres, board connu avant 09:15 |
| `oracle_score`, `oracle_top20`, `oracle_oos` | Score Oracle H20, appartenance au TOP20 de l'univers prédictible, prédiction réellement hors entraînement |
| `score_available_at_utc` | Horodatage du score, strictement avant 09:15 K |
| `prior_return_5d`, `prior_return_available_at_utc` | Rendement des cinq séances **déjà terminées**, incluant si applicable le mouvement de J, et son horodatage strictement avant 09:15 K |
| `model_trained_through` | Dernière date couverte par l'entraînement, strictement antérieure à K |

L'exporteur [D8](../../modelFactory/cn_oracle_prospective_15d8.py) a produit un [premier export réel](../../artifacts/research/cn_oracle_prospective_15d8/2026-10-08/oracle_top20.parquet) de 1 034 candidats pour le 8 octobre, horodaté avant son cutoff. Le [contrôle D7 anticipé](../../artifacts/research/cn_dragon_tiger_15d7/oracle-export-readiness-20260930-d8-real.json) le laisse en attente car cette décision est encore future. Les fichiers OOF H20 CN historiques s'arrêtent à 2025H2 et ne peuvent pas être joints au journal qui commence en 2026. Le champ `oracle_oos=true` de D8 dépend d'un artefact gelé, de la date maximale des labels qui ont influencé son entraînement et d'un score effectivement terminé avant 09:15 ; il ne constitue pas une convention pour réétiqueter des prédictions rétroactives. Pour tout futur modèle réentraîné, les labels H20 immatures restent interdits. Les labels, rendements futurs, déciles réalisés et colonnes de cible ne sont pas acceptés par le moteur d'appariement.

## Appariement verrouillé avant les issues

Les paramètres sont figés dans [sprint15d7_dragon_tiger_protocol.yaml](../../config/research_cn/sprint15d7_dragon_tiger_protocol.yaml) et son SHA-256 est inscrit dans chaque rapport. Une ligne avec événement est appariée à au plus trois témoins **sans événement**, le même jour et sur le même board. Le rang relatif du `oracle_score` est calculé **parmi les candidats TOP20 de ce jour**, sans utiliser le décile réalisé. Calipers simultanés : écart de rang ≤ 0,10 et écart absolu de rendement antérieur cinq séances ≤ 0,03. Les témoins ne sont pas réutilisés. Un tri stable par date, board, bourse et code, puis distance normalisée et identité, rend le résultat déterministe. Aucun résultat futur n'intervient dans cette sélection.

Le rapport indique le nombre de séances et de candidats, les exposés, les exposés appariés, les paires et les différences standardisées absolues après appariement. Ces seuils de **préparation**, et non de performance, sont pré-fixés : au moins 60 séances ouvertes, 200 candidats exposés, 80 % d'exposés appariés, deux trimestres calendaires et différences standardisées ≤ 0,10 sur rang Oracle et mouvement antérieur. Si l'une échoue, on ne proclame pas un signal directionnel. Ces nombres ne garantissent aucune puissance statistique ; l'effectif effectif et les intervalles de confiance seront audités avant toute conclusion.

## Analyse des issues prévue, mais non exécutée en D7

La fenêtre primaire sera H20 en **séances de marché**, sans horizon mélangé. On séparera le test `D1_veto` du test `D10_long`, au lieu d'agréger D1 et D10 en une seule précision. La définition doit rester celle de [cn_oracle_labels.py](../../modelFactory/cn_oracle_labels.py) : entrée à l'ouverture de la séance de **décision K** (pas à l'ouverture de J), sortie à la clôture de K+20, rendement ajusté et décile quotidien calculé parmi toute la coupe transversale valide du même jour ; D1 est le décile inférieur, D10 le supérieur. Le label n'est disponible qu'à partir de la séance K+21. Il faudra recalculer cette cible pour K, et **ne pas recycler le label Oracle de la séance événementielle J**. Les labels seront joints seulement après gel des paires, par identifiant `(decision_date, exchange, code)`, après maturité complète du H20 et contrôle des radiations/suspensions/limites de prix. Une paire avec issue invalide sera exclue selon une règle symétrique et reportée dans l'attrition, jamais reclassée en gagnante ou perdante.

Mesures pré-enregistrées : différence de risque D1, différence de précision D10, effectifs et taux de base, intervalles par bootstrap **par séance entière** (1 000 réplications), stabilité par trimestre et par board. Les titres et dates récurrents ne doivent pas être traités comme des observations indépendantes. Comparer au TOP20 Oracle pur et à l'abstention ; les coûts ne sont pertinents que dans une étape économique ultérieure. Aucun seuil, branche LONG/SHORT ou sous-population n'est choisi sur le trimestre de confirmation. Les résultats par trimestre et l'ensemble des règles candidates, y compris les échecs, devront être publiés ensemble.

La recherche est aussi conditionnée aux droits de réutilisation des listes officielles et à la fiabilité prospective du journal. En cas de droits non établis, le résultat demeure descriptif de recherche ; aucun modèle ni trading live n'en dépend.

## Reproduction et contrôles

Préflight sans candidats :

```powershell
python -m service.market.cn_dragon_tiger_matched_15d7 --output artifacts/research/cn_dragon_tiger_15d7/preflight-AAAAMMJJ
```

Lorsque l'export Oracle OOS 2026 est disponible et audité :

```powershell
python -m service.market.cn_dragon_tiger_matched_15d7 --candidates CHEMIN\candidats_oracle_oos_2026.parquet --output artifacts/research/cn_dragon_tiger_15d7/matching-AAAAMMJJ
```

Chaque dossier de sortie doit être neuf : les rapports ne sont pas écrasés. Le moteur [D7](../../service/market/cn_dragon_tiger_matched_15d7.py) vérifie schéma et empreinte des snapshots, les deux provenances officielles, succession réelle des séances selon le calendrier [D6](../../config/research_cn/sprint15d6_cn_calendar_2026.yaml), cutoff, dates et identités, disponibilité des scores et mouvements, absence de colonnes d'issues et unicité des candidats. Il écrit au plus `outcome_blind_matches.parquet` et `report.json`. Les [tests](../../tests/test_cn_dragon_tiger_matched_15d7.py) couvrent notamment retrait d'un événement au second passage, snapshot tardif, fuite de label, score tardif, prédiction non OOS et refus d'écrasement.

### Décision réelle du 8 octobre 2026

Les tâches Windows `AlphaTrade-CnDragonTigerAfterClose` et `AlphaTrade-CnDragonTigerBeforeOpen` sont installées et actives, mais fonctionnent sous une session **Interactive** : si la session Windows n'est pas ouverte au bon moment, le passage peut être manqué. La prévalidation du 30 septembre contrôle déjà les [1 034 candidats D8](../../artifacts/research/cn_oracle_prospective_15d8/2026-10-08/oracle_top20.parquet) et le snapshot après clôture, avec le statut `WAITING_FOR_DECISION_CUTOFF`. Elle ne fige pas encore la liste officielle : le passage du 8 octobre à **08:30 Shanghai** peut publier une révision.

Le 8 octobre, vérifier que `cn_dragon_tiger_before_open` a produit un snapshot complet et réellement observé avant **09:15 Shanghai** (02:30 puis 03:15 à Paris ce jour-là). Si la tâche ne s'est pas déclenchée, une exécution manuelle n'est admissible **que dans cette fenêtre**, jamais rétrodatée :

```powershell
.\.venv\Scripts\python.exe -m service.market.cn_dragon_tiger_schedule_15d6 --batch-name cn_dragon_tiger_before_open --force
```

Après 09:15 Shanghai, sans modifier les candidats ni les snapshots, relancer le contrôle puis l'appariement dans de nouveaux dossiers :

```powershell
.\.venv\Scripts\python.exe -m service.market.cn_oracle_export_readiness_15d7 --candidates artifacts/research/cn_oracle_prospective_15d8/2026-10-08/oracle_top20.parquet --report artifacts/research/cn_dragon_tiger_15d7/oracle-export-readiness-20261008.json
.\.venv\Scripts\python.exe -m service.market.cn_dragon_tiger_matched_15d7 --candidates artifacts/research/cn_oracle_prospective_15d8/2026-10-08/oracle_top20.parquet --output artifacts/research/cn_dragon_tiger_15d7/matching-20261008
```

Ne lancer la seconde commande que si le contrôle ne signale plus `WAITING_FOR_DECISION_CUTOFF` et valide les 1 034 lignes. Le premier rapport d'appariement sera normalement **insuffisant pour conclure** : une séance n'atteint pas les gates de 60 séances, 200 exposés et deux trimestres. Il ne faut ni joindre des issues H20 immatures ni ajuster les calipers sur ce premier résultat.

Le calendrier 2027 n'est pas encore vérifié : la collecte et le préflight échouent fermés en dehors de 2026. Les tâches Windows installées en mode Interactive ne travaillent pas sans la session nécessaire. Ces limites doivent être résolues avant de prétendre à un historique prospectif continu.
