# Sprint 14-B — Registre et diagnostic des campagnes CN_A

<!-- doc-status:start -->
> Statut documentaire au 2026-10-10 — Recherche / preuve datée : protocole et résultats conservés. Implémentation expérimentale ≠ promotion ML/LIVE ; les commandes restent à confronter aux droits et au catalogue actuels. [Référence actuelle](README.md).
<!-- doc-status:end -->

## Périmètre livré

Dans **Diagnostic ML → Marché : CN_A**, l'IHM présente les campagnes de
recherche CN et leur état. Elle n'interroge pas les tables ML US et ne
propose aucun bouton d'entraînement, de prédiction, de backtest opérateur ou
de live. Le sélecteur US reste le défaut ; le changement de marché est
indépendant sur chaque page (contrat du [Sprint 14-A](./sprint_14a_ihm_recherche_isolee.md)).

Le [registre fermé](../../ihm/services/cn_research_registry.py) référence
quatre campagnes, chacune avec son rapport et son protocole pré-enregistré :

| Campagne | Rapport source | Protocole | Statut autorisé |
| --- | --- | --- | --- |
| 10-B Oracle amplitude | `artifacts/cn/oracle/sprint10b/sprint10b_oracle_summary.json` | `config/research_cn/sprint10b_oracle.yaml` | `COMPLETE_RESEARCH_ONLY` |
| 10-C Ranking D1–D10 | `artifacts/cn/ranking/sprint10c/sprint10c_global_ranking_summary.json` | `config/research_cn/sprint10c_global_ranking.yaml` | `COMPLETE_RESEARCH_ONLY` |
| 11-A Diagnostic directionnel | `artifacts/cn/directional/sprint11a/sprint11a-a43c1071751aa8a6/report.json` | `config/research_cn/sprint11a_directional_diagnostic.yaml` | `EXPLORATORY_RESEARCH_ONLY` |
| 11-B Stress de coûts | `artifacts/cn/directional/sprint11b/sprint11b-a4e1a03943871cb2/report.json` | `config/research_cn/sprint11b_veto_economic.yaml` | `INDICATIVE_COST_STRESS_ONLY` |

La décision économique 13-C reste dans le panneau de recherche du Sprint
14-A : elle n'est pas présentée comme un batch ML entraîné. Il ne faut pas
confondre les identifiants de campagne ci-dessus avec des `batch_id` de
production ou supposer qu'un modèle CN est servable.

## Lecture de l'écran

Le tableau initial montre toutes les campagnes connues, y compris celles
dont l'artefact a disparu ou ne passe plus les contrôles. Celles-ci portent
`INDISPONIBLE`, avec la raison, et ne sont pas sélectionnables. Les autres
affichent la période OOS prévue par le protocole (2022H1–2025H2), le
profil de features, les horizons H5/H10/H15/H20, le statut recherche et la
provenance du rapport. Le chemin du protocole et son SHA-256 sont visibles.

Pour **Oracle 10-B**, on peut sélectionner le modèle LightGBM ou CatBoost
et lire par horizon l'AUC, la précision et le lift du TOP20, les sessions
OOS, le nombre de folds, le nombre de semestres positifs et la couverture
minimale des labels mûrs. Le tableau suivant détaille l'uplift de précision
contre la baseline ATR pour chaque semestre. Ce n'est pas une mesure de PnL.

Pour **Ranking 10-C**, on voit l'IC dans le pool Oracle TOP20, la précision
symétrique D1/D10, les erreurs de sens (D1 dans le TOP, D10 dans le BOTTOM),
les sessions/folds et l'uplift par semestre contre la baseline momentum.
Une précision de classement n'est ni une probabilité LONG calibrée ni une
preuve de stratégie rentable.

Pour **11-A**, le tableau compare Oracle seul, veto réversion et veto
LightGBM : effectif évalué, taux D1/D10 et rendement futur moyen par
horizon. Une politique sélectionnée peut ensuite être inspectée semestre
par semestre. Pour **11-B**, les chiffres de rendement net et les lignes
`fillable_proxy` sont des **proxies de recherche** sous hypothèses de coûts ;
ce ne sont pas des fills de portefeuille. Ses folds sont également visibles.

Tous ces OOS 2022–2025 ont déjà été inspectés au cours des sprints de
recherche. Ils ne constituent pas un holdout indépendant supplémentaire.
Le rapport 13-C conclut toujours **NO GO économique** sur les politiques
comparées. Aucun statut `GO_RESEARCH_ONLY` d'un horizon ne contourne cette
décision.

## Invariants de séparation et limites

Le lecteur exige `market_code: CN_A` dans le protocole et le rapport,
l'empreinte SHA-256 exacte du protocole, le statut attendu et
`serving_enabled=false` / `backtest_executed=false`. Les rapports 10-B/10-C
doivent déclarer zéro fold manquant ; les horizons du rapport doivent
correspondre au protocole. Les tableaux par fold refusent les semestres
manquants ou dupliqués. Un rapport US, modifié, incomplet ou devenu servable
est écarté ; aucun fallback US n'est autorisé.

Ce registre est **intentionnellement explicite** : un nouveau rapport CN ne
devient pas automatiquement fiable parce qu'il est apparu sous
`artifacts/cn`. Pour l'ajouter, il faut vérifier son contrat de rapport,
son protocole, son statut et ses métriques, puis étendre le registre et les
[tests 14-B](../../tests/test_sprint14b_cn_campaign_registry.py). La base
`alpha_trade_cn` n'est pas consultée ici ; les informations sont lues dans
des artefacts de recherche figés. Les campagnes de labels/features et les
replays économiques détaillés ne sont pas encore navigables depuis ce
registre ML.

## Suite

Le [Sprint 14-C](./sprint_14c_replay_recherche_ihm.md) définit maintenant
un lancement de replay CN **de recherche** distinct des commandes US,
avec routage explicite vers la base CN et refus avant lancement en cas de
mismatch. Il n'ouvre pas le live CN tant que le gate économique reste
fermé.
