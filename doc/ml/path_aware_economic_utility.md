# E3-A2 — Utilité économique path-aware après Oracle Extreme

## Statut et objectif

E3-A2 est une expérience strictement `research_only`. Elle ne modifie ni le
serving, ni les prédictions persistées, ni la cascade du backtest. Elle cherche
à corriger la faiblesse observée dans E3-A : une classification peut prévoir
la probabilité de gagner tout en ignorant la gravité des pertes.

Le run E3-A `shared-path-aware-20260906064548-0802c8` obtenait en LONG une AUC
moyenne de 0,541 sur neuf folds, mais un lift économique de -0,064 point. En
SHORT, l'AUC moyenne était 0,508 et le top 10 % perdait -0,624 %. Les replays
contenaient des pertes allant jusqu'à -86 % en LONG et -311 % en SHORT. Cela
justifie une cible économique, pas une nouvelle recherche de seuil binaire.

## Architecture

E3-A2 conserve le pool TOP20 issu des prédictions Oracle OOF et le contrat de
replay `barrier_race_v1` : entrée à l'open suivant, gap maximal 3 %, stop 2,5
ATR, TP `min(3 ATR, 7 %)`, résolution intrabar conservatrice, sortie H20,
coûts explicites et emprunt SHORT.

Quatre modèles mutualisés sont appris :

```text
Oracle TOP20 OOF
    ├─ LONG : rendement net prédit
    ├─ LONG : P(perte nette <= -20 %)
    ├─ SHORT : rendement net prédit
    └─ SHORT : P(perte nette <= -20 %)

utilité(côté) = rendement net prédit - 0,20 × P(perte extrême)
rang(côté)    = percentile de l'utilité parmi les candidats du même jour
politique     = top 10 % quotidien, séparément pour LONG et SHORT
```

Le score Oracle sert uniquement à construire le pool. Il n'entre jamais dans
les features directionnelles.

## Protection contre les fuites

Les folds sont chronologiques avec purge de 20 séances. Pour chaque fold, les
bornes de winsorisation des rendements sont calculées uniquement sur le train
aux quantiles 1 % et 99 %. Elles sont ensuite appliquées aux cibles de train et
de validation utilisées par CatBoost. Les rendements du test OOS ne sont ni
écrêtés ni transformés dans les métriques économiques.

Les probabilités de perte rare ne sont pas interprétées comme des probabilités
calibrées de production. Le classifieur utilise des poids de classes équilibrés
et sa sortie contribue seulement au classement relatif du même jour.

## Mesures et gates

Le rapport contient, pour LONG et SHORT : rendement net du top 10 %, rendement
du pool aux mêmes dates, lift, taux de succès, IC de Spearman quotidien, taux
de perte <= -20 %, CVaR 5 %, résultats par semestre et concentration du PnL.

Tous les gates suivants doivent passer pour un côté :

- IC quotidien moyen par fold >= 0,03 ;
- IC positif dans au moins sept folds ;
- lift du top 10 % >= 0,25 point ;
- lift positif dans au moins sept folds ;
- rendement positif dans au moins sept folds ;
- taux de perte extrême non supérieur à celui du pool des mêmes dates ;
- CVaR 5 % non dégradée par rapport au pool ;
- premier symbole <= 35 % des contributions positives.

Un GO LONG ne valide pas SHORT. Aucun paramètre ne doit être ajusté après
lecture du résultat de cette première campagne.

## Commande canonique

```powershell
F:\projets\.venv\Scripts\python.exe -u -m modelFactory.path_aware_utility --oracle-batch-id model-factory-20260904192500-0802c8 --start-date 2016-01-01 --end-date 2025-12-31 --stop-atr-mult 2.5 --tp-atr-mult 3.0 --tp-max-pct 0.07 --max-sessions 20 --max-entry-gap-pct 0.03 --spread-bps 5 --commission-bps 1 --slippage-bps 2 --borrow-fee-annual 0.003 --catastrophic-loss-threshold -0.20 --risk-penalty-return 0.20 --target-winsor-lower 0.01 --target-winsor-upper 0.99 --wf-min-train-size 504 --wf-val-size 126 --wf-test-size 126 --wf-step-size 126 --wf-max-splits 12 --iterations 600 --depth 6 --learning-rate 0.03 --context-mode none --log-level INFO
```

## Artefacts

Chaque exécution crée `artifacts/models/shared_directional/shared-path-utility-*`
avec :

- `long_return_model.cbm` et `short_return_model.cbm` ;
- `long_tail_risk_model.cbm` et `short_tail_risk_model.cbm` ;
- `oof_predictions.parquet` avec les quatre prédictions et les rangs quotidiens ;
- `metrics.json` avec folds, semestres, CVaR, concentration et gates ;
- `contract.json` avec période réellement couverte, paramètres et provenance ;
- `feature_profile.json` avec le schéma exact des features.

Même si les gates passent, E3-A2 reste non servable. La suite serait E3-B avec
le lifecycle PROD complet, puis une confirmation sur une période postérieure
réellement intacte.

La campagne de veto dérivée et ses résultats sont documentés dans
[`path_risk_veto.md`](path_risk_veto.md).
